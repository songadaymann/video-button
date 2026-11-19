// Shared by the isolated content script and the background worker.
globalThis.VideoButtonTargets = (() => {
  function httpUrl(value, base) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const url = new URL(value, base);
      return /^https?:$/.test(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function canonical(value) {
    const safe = httpUrl(value);
    if (!safe) return null;
    const url = new URL(safe);
    const host = url.hostname.toLowerCase().replace(/^www\./, '');
    if (host === 'youtu.be') return `https://www.youtube.com/watch?v=${encodeURIComponent(url.pathname.slice(1).split('/')[0])}`;
    if (host === 'youtube.com' || host === 'm.youtube.com') {
      const id = url.searchParams.get('v') || url.pathname.match(/^\/(?:shorts|embed|live)\/([^/]+)/)?.[1];
      if (id) return `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`;
    }
    if (['x.com', 'twitter.com', 'mobile.twitter.com'].includes(host)) {
      const match = url.pathname.match(/^\/([^/]+)\/status\/(\d+)(?:\/video\/(\d+))?/);
      if (match) return `https://x.com/${match[1]}/status/${match[2]}${match[3] ? `/video/${match[3]}` : ''}`;
    }
    if (host === 'instagram.com') {
      const match = url.pathname.match(/^\/(p|reel|reels|tv)\/([^/]+)/);
      if (match) return `https://www.instagram.com/${match[1]}/${match[2]}/`;
    }
    if (host === 'tiktok.com' || host.endsWith('.tiktok.com')) {
      const match = url.pathname.match(/^\/@[^/]+\/video\/\d+/);
      if (match) return `https://www.tiktok.com${match[0]}`;
    }
    url.hash = '';
    return url.href;
  }

  function isPost(value) {
    try {
      const u = new URL(value);
      return /(^|\.)(youtube\.com|youtu\.be|x\.com|twitter\.com|instagram\.com|tiktok\.com)$/.test(u.hostname)
        && /(?:\/status\/\d+|\/video\/\d+|\/(?:p|reel|reels|tv|shorts|embed|live)\/[^/]+|\/watch\?v=)/.test(u.pathname + u.search);
    } catch { return false; }
  }

  function targetFor(video, doc = document) {
    const page = doc.location.href;
    const host = doc.location.hostname;
    let scope = video.closest('article, [data-e2e="recommend-list-item-container"], [data-e2e="feed-video"], [data-e2e="search_top-item"], ytd-reel-video-renderer, ytd-rich-item-renderer');
    const links = scope ? [...scope.querySelectorAll('a[href]')] : [];
    let post = links.map(a => httpUrl(a.href, page)).find(u => u && isPost(u));
    // A watch/reel page is already a precise target. Feed pages need the post link.
    if (!post && isPost(page)) post = page;
    if (!post && /(^|\.)tiktok\.com$/.test(host)) {
      // TikTok sometimes places the permalink next to, rather than inside, the player.
      let parent = video.parentElement;
      for (let i = 0; i < 5 && parent; i++, parent = parent.parentElement) {
        post = [...parent.querySelectorAll('a[href]')].map(a => httpUrl(a.href, page)).find(u => u && isPost(u));
        if (post) { scope = parent; break; }
      }
    }
    const mediaUrl = httpUrl(video.currentSrc || video.src || video.querySelector('source[src]')?.src, page);
    const siblings = [...(scope || doc).querySelectorAll('video')].filter(v => {
      const r = v.getBoundingClientRect();
      return r.width >= 80 && r.height >= 45;
    });
    return {
      url: canonical(post || page),
      mediaUrl,
      title: (video.getAttribute('aria-label') || doc.title || 'Video').slice(0, 180),
      itemIndex: Math.max(1, siblings.indexOf(video) + 1),
      precise: Boolean(post),
    };
  }
  return { httpUrl, canonical, isPost, targetFor };
})();
