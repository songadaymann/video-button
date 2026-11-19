import './targets.js';
const HOST = 'com.songaday.video_button';
const terminal = new Set(['complete', 'error', 'cancelled']);
let port = null;
let jobs = {};
let helper = null;
const waiting = new Map();
const ready = chrome.storage.session.get({ jobs: {} }).then(s => { jobs = s.jobs; });

function connect() {
  if (port) return port;
  port = chrome.runtime.connectNative(HOST);
  port.onMessage.addListener(async message => {
    if (message.requestId && waiting.has(message.requestId)) {
      waiting.get(message.requestId)(message); waiting.delete(message.requestId);
    }
    if (message.type === 'hello') helper = message;
    if (message.type !== 'job') return;
    await ready;
    const previous = jobs[message.job.id] || {};
    const job = { ...previous, ...message.job, updatedAt: Date.now() };
    jobs[job.id] = job;
    const entries = Object.values(jobs).sort((a,b) => b.createdAt - a.createdAt);
    jobs = Object.fromEntries(entries.filter((j,i) => !terminal.has(j.status) || i < 30).map(j => [j.id, j]));
    await chrome.storage.session.set({ jobs });
    await badge();
    if (job.tabId) chrome.tabs.sendMessage(job.tabId, { type: 'job', job }, { frameId: job.frameId || 0 }).catch(() => {});
  });
  port.onDisconnect.addListener(async () => {
    const reason = chrome.runtime.lastError?.message || 'The local helper stopped.';
    port = null; helper = null;
    for (const resolve of waiting.values()) resolve({ ok: false, error: reason });
    waiting.clear();
    await ready;
    for (const job of Object.values(jobs)) {
      if (!terminal.has(job.status)) {
        job.status = 'error'; job.error = 'Local helper disconnected. Retry from the video.';
        if (job.tabId) chrome.tabs.sendMessage(job.tabId, {type:'job', job}, {frameId:job.frameId || 0}).catch(() => {});
      }
    }
    await chrome.storage.session.set({ jobs }); await badge();
  });
  return port;
}

async function badge() {
  const n = Object.values(jobs).filter(j => !terminal.has(j.status)).length;
  await chrome.action.setBadgeText({ text: n ? String(n) : '' });
  await chrome.action.setBadgeBackgroundColor({ color: '#246e52' });
}

function request(action, payload = {}) {
  return new Promise(resolve => {
    const requestId = crypto.randomUUID();
    const timeout = setTimeout(() => { waiting.delete(requestId); resolve({ok:false, error:'The helper did not respond. Run Install.command, then retry.'}); }, 10000);
    waiting.set(requestId, result => { clearTimeout(timeout); resolve(result); });
    try { connect().postMessage({ action, requestId, ...payload }); }
    catch (error) { clearTimeout(timeout); waiting.delete(requestId); resolve({ok:false,error:error.message}); }
  });
}

async function download(target, sender = {}) {
  await ready;
  if (!target || !globalThis.VideoButtonTargets.httpUrl(target.url)) return {ok:false,error:'Open a video on an HTTP or HTTPS page first.'};
  const settings = await chrome.storage.local.get({ useCookies: false, chromeProfile: '' });
  const id = crypto.randomUUID();
  const job = { id, title: String(target.title || 'Video').slice(0,180), status:'queued', createdAt:Date.now(), tabId:sender.tab?.id, frameId:sender.frameId || 0 };
  jobs[id] = job;
  await chrome.storage.session.set({ jobs });
  const response = await request('download', { id, target, useCookies:settings.useCookies === true, chromeProfile:settings.chromeProfile });
  if (!response.ok) { job.status='error'; job.error=response.error; await chrome.storage.session.set({jobs}); }
  return { ...response, jobId: id };
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  const isExtensionPage = sender.id === chrome.runtime.id && !sender.tab && sender.url?.startsWith(chrome.runtime.getURL(''));
  // Content scripts may submit a target; settings/file operations are extension-page only.
  let task;
  if (message.type === 'download' && sender.id === chrome.runtime.id) task = download(message.target, sender);
  else if (!isExtensionPage) return false;
  else if (message.type === 'hello') task = request('hello');
  else if (message.type === 'cancel') task = request('cancel', { id:message.id });
  else if (message.type === 'openFolder') task = request('openFolder');
  else if (message.type === 'clearHistory') task = ready.then(async () => { jobs=Object.fromEntries(Object.entries(jobs).filter(([,j])=>!terminal.has(j.status))); await chrome.storage.session.set({jobs}); return {ok:true}; });
  else return false;
  task.then(reply, error => reply({ok:false,error:error.message}));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({id:'video-button-media',title:'Download video — best quality',contexts:['video']});
    chrome.contextMenus.create({id:'video-button-page',title:'Download video from this page',contexts:['page','link']});
  });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.linkUrl || info.frameUrl || tab.url;
  download({url:globalThis.VideoButtonTargets.canonical(url),mediaUrl:info.srcUrl,title:tab.title,itemIndex:1,precise:globalThis.VideoButtonTargets.isPost(url)}, {tab,frameId:info.frameId});
});
