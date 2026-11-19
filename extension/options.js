const $=id=>document.getElementById(id);
const settings=await chrome.storage.local.get({showButtons:true,useCookies:false,chromeProfile:''});
for(const id of ['showButtons','useCookies'])$(id).checked=settings[id];
$('chromeProfile').value=settings.chromeProfile;
async function save(){
  const profile=$('chromeProfile').value.trim();
  if(profile && !/^(Default|Profile \d+)$/.test(profile)) { $('saved').textContent='Use Default, Profile 1, Profile 2, etc., or leave blank.'; return; }
  await chrome.storage.local.set({showButtons:$('showButtons').checked,useCookies:$('useCookies').checked,chromeProfile:profile});
  $('saved').textContent='Saved.';
}
for(const id of ['showButtons','useCookies','chromeProfile'])$(id).addEventListener('change',save);
const result=await chrome.runtime.sendMessage({type:'hello'});
$('helper').textContent=result.ok ? `● Local helper ready · yt-dlp ${result.downloaderVersion}` : 'Setup needed: run Install.command, then reload this page.';
$('helper').classList.toggle('error',!result.ok);
if(result.folder)$('destination').textContent=`Saved to ${result.folder}`;
$('folder').addEventListener('click',async()=>{const r=await chrome.runtime.sendMessage({type:'openFolder'});if(!r.ok)$('saved').textContent=r.error;});
