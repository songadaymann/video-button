import test from 'node:test';
import assert from 'node:assert/strict';
await import('../extension/targets.js');
const {canonical,httpUrl,isPost,targetFor}=globalThis.VideoButtonTargets;

test('individual video links survive social tracking URLs',()=>{
  assert.equal(canonical('https://www.youtube.com/watch?v=abc123&list=playlist&t=23'),'https://www.youtube.com/watch?v=abc123');
  assert.equal(canonical('https://youtu.be/abc123?si=tracking'),'https://www.youtube.com/watch?v=abc123');
  assert.equal(canonical('https://youtube.com/shorts/abc123?feature=share'),'https://www.youtube.com/watch?v=abc123');
  assert.equal(canonical('https://twitter.com/person/status/123/video/2?s=20'),'https://x.com/person/status/123/video/2');
  assert.equal(canonical('https://instagram.com/reel/ABC/?igsh=x'),'https://www.instagram.com/reel/ABC/');
  assert.equal(canonical('https://tiktok.com/@person/video/123?x=2'),'https://www.tiktok.com/@person/video/123');
});
test('rejects executable and credential-bearing URL schemes',()=>{
  for(const url of ['javascript:alert(1)','file:///etc/passwd','blob:https://example.org/id','https://user:pass@example.org/'])assert.equal(httpUrl(url),null);
  assert.equal(httpUrl(undefined,'https://example.org/page'),null);
  assert.equal(httpUrl('/clip.mp4','https://example.org/page'),'https://example.org/clip.mp4');
});
test('feed homepages are not individual posts',()=>{
  for(const url of ['https://x.com/home','https://youtube.com/','https://instagram.com/','https://tiktok.com/foryou'])assert.equal(isPost(url),false);
  assert.equal(isPost('https://x.com/user/status/123'),true);
  assert.equal(isPost('https://notyoutube.com/watch?v=abc'),false);
});
test('a clicked feed video targets its own post, not the whole timeline',()=>{
  const links=[{href:'https://x.com/person'},{href:'https://x.com/person/status/123'}];
  const video={currentSrc:'blob:https://x.com/a',getAttribute:()=>null,querySelector:()=>null,getBoundingClientRect:()=>({width:400,height:300})};
  const article={querySelectorAll:selector=>selector==='a[href]'?links:[video]};
  video.closest=()=>article;
  const doc={location:{href:'https://x.com/home',hostname:'x.com'},title:'Timeline'};
  const result=targetFor(video,doc);
  assert.equal(result.url,'https://x.com/person/status/123');
  assert.equal(result.mediaUrl,null);
  assert.equal(result.precise,true);
});
