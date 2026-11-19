(() => {
  if (globalThis.__videoButtonLoaded) return;
  globalThis.__videoButtonLoaded = true;
  const { targetFor } = globalThis.VideoButtonTargets;
  const items = new Map();
  const root = document.createElement('div');
  root.setAttribute('data-video-button', '');
  const shadow = root.attachShadow({ mode: 'closed' });
  shadow.innerHTML = `<style>
    :host { all:initial; position:fixed; inset:0; z-index:2147483647; pointer-events:none; }
    button { all:initial; box-sizing:border-box; position:fixed; display:flex; align-items:center;
      gap:7px; padding:9px 12px; border:1px solid #ffffff4d; border-radius:9px; background:#171c24ee;
      color:#fff; font:600 12px/1.25 system-ui,sans-serif; box-shadow:0 2px 12px #0005;
      cursor:pointer; pointer-events:auto; transition:opacity .14s; white-space:nowrap; }
    button:hover { background:#294e43; border-color:#a8f0d0; }
    button:focus-visible { outline:3px solid #a8f0d0; outline-offset:2px; }
    button[data-hidden] { display:none; }
    button[data-state="complete"] { background:#205b45; }
    button[data-state="error"] { background:#782f38; }
  </style>`;
  document.documentElement.append(root);

  let enabled = true;
  chrome.storage.local.get({ showButtons: true }).then(s => { enabled = s.showButtons; schedule(); });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.showButtons) { enabled = changes.showButtons.newValue; schedule(); }
  });

  function scan() {
    document.querySelectorAll('video').forEach(video => {
      if (items.has(video)) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = '↓ Download video';
      button.title = 'Download the best available video and audio';
      const item = { video, button, jobId: null };
      button.addEventListener('click', async event => {
        // Page scripts cannot trigger a native download by dispatching synthetic clicks.
        if (!event.isTrusted) return;
        event.preventDefault(); event.stopPropagation();
        if (item.jobId) return;
        button.textContent = 'Starting…';
        try {
          const result = await chrome.runtime.sendMessage({ type: 'download', target: targetFor(video) });
          if (!result?.ok) throw new Error(result?.error || 'Could not start download');
          item.jobId = result.jobId;
          button.textContent = 'Queued…';
        } catch (error) {
          button.textContent = 'Try again'; button.dataset.state = 'error'; button.title = error.message;
        }
      });
      shadow.append(button); items.set(video, item);
      resize.observe(video);
    });
    for (const [video, item] of items) {
      if (!video.isConnected) { resize.unobserve(video); item.button.remove(); items.delete(video); }
    }
  }

  function position() {
    const fullscreen = document.fullscreenElement;
    // Overlays must be inside the fullscreen subtree to remain visible.
    const mount = fullscreen && fullscreen.tagName !== 'VIDEO' ? fullscreen : document.documentElement;
    if (root.parentElement !== mount) mount.append(root);
    for (const { video, button } of items.values()) {
      const r = video.getBoundingClientRect();
      const style = getComputedStyle(video);
      const shown = enabled && r.width >= 120 && r.height >= 70 && r.bottom > 42 && r.top < innerHeight
        && r.right > 30 && r.left < innerWidth && style.visibility !== 'hidden' && style.display !== 'none'
        && (!fullscreen || fullscreen === video || fullscreen.contains(video));
      button.toggleAttribute('data-hidden', !shown);
      if (shown) {
        button.style.top = `${Math.max(8, r.top + 10)}px`;
        button.style.left = `${Math.max(8, Math.min(innerWidth - 165, r.right - 155))}px`;
      }
    }
  }
  let scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; scan(); position(); });
  }
  const resize = new ResizeObserver(schedule);
  const observer = new MutationObserver(mutations => {
    if (mutations.some(m => !root.contains(m.target))) schedule();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'style', 'class'] });
  addEventListener('scroll', schedule, { capture: true, passive: true });
  addEventListener('resize', schedule, { passive: true });
  document.addEventListener('fullscreenchange', schedule);
  document.addEventListener('play', schedule, true);
  const timer = setInterval(schedule, 1500); // SPA navigation and moving players without DOM changes.
  addEventListener('pagehide', () => clearInterval(timer), { once: true });
  addEventListener('pageshow', schedule);
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (message.type === 'listVideos') {
      reply([...items.values()].filter(({video}) => video.getBoundingClientRect().width > 0).map(({video}) => targetFor(video)));
    }
    if (message.type !== 'job') return;
    for (const item of items.values()) {
      if (item.jobId !== message.job.id) continue;
      const job = message.job;
      item.button.dataset.state = job.status;
      item.button.textContent = job.status === 'complete' ? '✓ Downloaded'
        : job.status === 'error' ? 'Try again'
        : job.status === 'cancelled' ? '↓ Download video'
        : job.status === 'merging' ? 'Combining audio…'
        : job.percent != null ? `Downloading ${Math.round(job.percent)}%` : 'Finding best quality…';
      item.button.title = job.error || job.filename || 'Download the best available video and audio';
      if (['complete', 'error', 'cancelled'].includes(job.status)) {
        item.jobId = null;
        if (job.status === 'complete') setTimeout(() => { item.button.textContent = '↓ Download video'; delete item.button.dataset.state; }, 7000);
      }
    }
  });
  schedule();
})();
