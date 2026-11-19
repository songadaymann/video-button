import './targets.js';
const $ = id => document.getElementById(id);
const done = new Set(['complete','error','cancelled']);
let currentTab;
let targets = [];
function el(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function start(target) {
  $('download').disabled = true;
  try {
    const response = await chrome.runtime.sendMessage({type:'download',target});
    if (!response.ok) throw new Error(response.error);
  } catch (e) { $('helper').textContent = e.message; $('helper').classList.add('error'); }
  finally { $('download').disabled = false; }
}
async function renderJobs() {
  const {jobs={}} = await chrome.storage.session.get('jobs');
  const sorted = Object.values(jobs).sort((a,b)=>b.createdAt-a.createdAt);
  const fragment = document.createDocumentFragment();
  for (const job of sorted) {
    const card = el('div','','job');
    if (!done.has(job.status)) {
      const cancel = el('button','Cancel','quiet');
      cancel.addEventListener('click',()=>chrome.runtime.sendMessage({type:'cancel',id:job.id}));
      card.append(cancel);
    }
    card.append(el('div',job.title || 'Video','job-title'));
    let label = job.status === 'complete' ? `Saved${job.audioFilename ? ' MP4 + MP3' : ''} · ${job.quality || 'Best available quality'}`
      : job.status === 'error' ? job.error
      : job.status === 'cancelled' ? 'Cancelled'
      : job.status === 'merging' ? 'Combining the video and audio…'
      : job.status === 'exporting' ? 'Saving MP4 with sound + MP3…'
      : job.status === 'queued' ? 'Queued'
      : job.percent != null ? `Downloading · ${Math.round(job.percent)}%` : 'Finding the best quality…';
    if (job.status === 'complete' && job.filename) label += ` · ${job.filename}`;
    if (job.status === 'complete' && job.audioFilename) label += ` · ${job.audioFilename}`;
    card.append(el('div',label,'job-status' + (job.status === 'error' ? ' error' : '')));
    if (job.status === 'downloading') {
      const progress = document.createElement('progress'); progress.max=100;
      if (job.percent != null) progress.value=job.percent;
      card.append(progress);
    }
    fragment.append(card);
  }
  if (!sorted.length) fragment.append(el('div','Your next good find goes here.','empty'));
  $('jobs').replaceChildren(fragment);
}
$('settings').addEventListener('click',()=>chrome.runtime.openOptionsPage());
$('clear').addEventListener('click',()=>chrome.runtime.sendMessage({type:'clearHistory'}));
$('folder').addEventListener('click',async()=>{
  const r=await chrome.runtime.sendMessage({type:'openFolder'});
  if (!r.ok) { $('helper').textContent=r.error; $('helper').classList.add('error'); }
});
$('download').addEventListener('click',()=>{
  const target=targets.length === 1 ? targets[0] : {url:currentTab?.url,title:currentTab?.title,itemIndex:1};
  start(target);
});
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='session' && changes.jobs)renderJobs();});
await renderJobs();
const hello = chrome.runtime.sendMessage({type:'hello'}).then(result=>{
  $('helper').textContent=result.ok ? `● Local helper ready · yt-dlp ${result.downloaderVersion}` : 'Setup needed: open Install.command in the project folder.';
  $('helper').classList.toggle('error',!result.ok);
});
[currentTab] = await chrome.tabs.query({active:true,currentWindow:true});
if (!globalThis.VideoButtonTargets.httpUrl(currentTab?.url)) {
  $('download').disabled=true;
  $('download').textContent='Open a video page first';
} else {
  // The overlay and right-click menu also work inside cross-origin frames.
  const frames = [];
  try {
    const found=await chrome.tabs.sendMessage(currentTab.id,{type:'listVideos'},{frameId:0});
    if(Array.isArray(found))frames.push(...found);
  } catch {}
  targets=frames;
  if(targets.length>1) {
    $('videos-section').hidden=false;
    targets.forEach((target,i)=>{
      const b=el('button',`↓ Video ${i+1} · ${new URL(target.url).hostname}`,'video-choice');
      b.addEventListener('click',()=>start(target)); $('videos').append(b);
    });
  }
}
await hello;
