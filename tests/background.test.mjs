import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';

test('background limits content-script actions and reports a disconnected helper',async()=>{
  let listener,disconnect;
  const portListeners=[];
  const sent=[];
  let session={jobs:{}};
  const chrome={
    storage:{
      session:{get:async()=>structuredClone(session),set:async update=>{session=structuredClone({...session,...update});}},
      local:{get:async defaults=>defaults},
    },
    action:{setBadgeText:async()=>{},setBadgeBackgroundColor:async()=>{}},
    tabs:{sendMessage:async()=>{}},
    contextMenus:{onClicked:{addListener:()=>{}},removeAll:()=>{},create:()=>{}},
    runtime:{id:'test',getURL:path=>`chrome-extension://test/${path}`,onInstalled:{addListener:()=>{}},onMessage:{addListener:fn=>{listener=fn;}},
      connectNative:()=>({
        onMessage:{addListener:fn=>portListeners.push(fn)},
        onDisconnect:{addListener:fn=>{disconnect=fn;}},
        postMessage:message=>{
          sent.push(message);
          queueMicrotask(()=>portListeners.forEach(fn=>fn({requestId:message.requestId,ok:true,type:message.action==='hello'?'hello':'ack',downloaderVersion:'test'})));
        },
      }),
    },
  };
  const context=vm.createContext({chrome,crypto:webcrypto,URL,setTimeout,clearTimeout});
  vm.runInContext(await readFile(new URL('../extension/targets.js',import.meta.url),'utf8'),context);
  const background=(await readFile(new URL('../extension/background.js',import.meta.url),'utf8')).replace("import './targets.js';",'');
  vm.runInContext(background,context);
  const content={id:'test',tab:{id:123},frameId:2,url:'https://example.org/video'};
  const popup={id:'test',url:'chrome-extension://test/popup.html'};
  assert.equal(listener({type:'openFolder'},content,()=>assert.fail('content script gained file action')),false);
  const call=(message,sender)=>new Promise(resolve=>listener(message,sender,resolve));
  const bad=await call({type:'download',target:{url:'file:///private/video'}},content);
  assert.equal(bad.ok,false);
  assert.equal(sent.length,0);
  const hello=await call({type:'hello'},popup);
  assert.equal(hello.ok,true);
  const result=await call({type:'download',target:{url:'https://example.org/video',mediaUrl:'https://example.org/video.mp4',title:'Selected clip',itemIndex:1}},content);
  assert.equal(result.ok,true);
  assert.equal(session.jobs[result.jobId].tabId,123);
  assert.equal(session.jobs[result.jobId].frameId,2);
  assert.equal(sent.at(-1).useCookies,false);
  assert.equal(sent.at(-1).target.url,'https://example.org/video');
  chrome.runtime.lastError={message:'Test disconnection'};
  await disconnect();
  assert.equal(session.jobs[result.jobId].status,'error');
  assert.match(session.jobs[result.jobId].error,/disconnected/);
});
