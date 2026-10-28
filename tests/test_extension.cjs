const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function load(){const c=vm.createContext({URL,Date,console,window:{},chrome:{runtime:{onMessage:{addListener(){}}}}});vm.runInContext(fs.readFileSync(path.join(__dirname,'../extension/content.js'),'utf8'),c);return c;}
test('canonical Facebook video URLs preserve essential IDs and remove tracking',()=>{
 const c=load();
 assert.equal(c.canonicalVideo_('https://www.facebook.com/watch/?v=123456&ref=watch').video_id,'123456');
 assert.equal(c.canonicalVideo_('https://www.facebook.com/video.php?v=123456&foo=1').post_url,'https://www.facebook.com/watch/?v=123456');
 assert.equal(c.canonicalVideo_('https://www.facebook.com/reel/99999/?mibextid=abc').post_id,'fb_99999');
 assert.equal(c.canonicalVideo_('https://www.facebook.com/page/videos/55555/').video_id,'55555');
 assert.equal(c.canonicalVideo_('https://www.facebook.com/page'),null);
 assert.equal(c.canonicalVideo_('https://evil.example/reel/55555'),null);
});
test('unknown metrics stay null; supported compact values normalized',()=>{
 const c=load(); assert.equal(c.parseCount_(''),null); assert.equal(c.parseCount_('Thích'),null);
 assert.equal(c.parseCount_('1,2K'),1200); assert.equal(c.parseCount_('2 triệu'),2000000);
 assert.equal(c.parseCount_('0'),0);
});
test('manifest limits network origins and excludes secrets/downloads',()=>{
 const m=JSON.parse(fs.readFileSync(path.join(__dirname,'../extension/manifest.json'),'utf8'));
 assert.equal(m.manifest_version,3); assert.equal(m.permissions.includes('downloads'),false);
 assert.ok(m.host_permissions.includes('http://127.0.0.1:8765/*'));
 assert.ok(!m.host_permissions.includes('<all_urls>'));
 assert.ok(!m.host_permissions.some(x=>x.includes('googleapis')));
});

function background(initial,fetchImpl){
 const state=structuredClone(initial),removed=[],created=[],listeners={};
 const c=vm.createContext({console,URL,AbortController,setTimeout,clearTimeout,Date,fetch:fetchImpl,chrome:{
  storage:{local:{get:async keys=>{if(typeof keys==='string')keys=[keys];return Object.fromEntries(keys.map(k=>[k,state[k]]));},set:async x=>Object.assign(state,structuredClone(x)),remove:async keys=>{for(const k of Array.isArray(keys)?keys:[keys])delete state[k];}}},
  alarms:{get:async()=>({name:'studio-v3-poll'}),create:async()=>{},onAlarm:{addListener:f=>listeners.alarm=f}},
  runtime:{onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener:f=>listeners.message=f}},
  tabs:{remove:async id=>removed.push(id),get:async id=>({id,status:'complete',url:'https://www.facebook.com/test'}),create:async options=>{created.push(options);return {id:100};},sendMessage:async()=>({ok:true}),onUpdated:{addListener(){}}}
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../extension/background.js'),'utf8'),c);
 return {c,state,removed,created,listeners};
}
test('failed result delivery survives worker restart and is retried before new work',async()=>{
 const active={job:{job_id:'j1',channel_id:'ch1',channel:{name:'Test',url:'https://www.facebook.com/test'}},tabId:10,started_at:Date.now()};
 const result={job_id:'j1',channel_id:'ch1',posts:[],partial:false,error:''};
 const first=background({localToken:'token',activeScan:active,pendingResult:result},async()=>{throw new TypeError('offline');});
 await first.c.tick();assert.ok(first.state.pendingResult);assert.equal(first.removed.length,0);
 const paths=[];const restarted=background(first.state,async(url,options)=>{paths.push(url);assert.equal(options.headers['X-Local-Token'],'token');return {ok:true,json:async()=>({ok:true})};});
 await restarted.c.tick();assert.equal(restarted.state.pendingResult,null);assert.equal(restarted.state.activeScan,null);assert.deepEqual(restarted.removed,[10]);
 assert.deepEqual(paths,['http://127.0.0.1:8765/api/scan/result']);
});
test('restart resumes owned tab instead of creating another scan tab',async()=>{
 const f=background({localToken:'token',activeScan:{job:{job_id:'j',channel_id:'c',channel:{url:'https://www.facebook.com/test'}},tabId:12,started_at:Date.now()}},async()=>{throw new Error('should not fetch a new job');});
 await f.c.tick();assert.equal(f.created.length,0);assert.equal(f.state.activeScan.tabId,12);
});
test('content result from another tab is rejected',async()=>{
 const f=background({localToken:'token',activeScan:{job:{job_id:'j',channel_id:'c',channel:{url:'https://www.facebook.com/test'}},tabId:12,started_at:Date.now()}},async()=>({ok:true,json:async()=>({ok:true})}));
 const reply=await new Promise(resolve=>f.listeners.message({action:'SCAN_RESULT',result:{job_id:'j',posts:[]}}, {tab:{id:99}},resolve));
 assert.equal(reply.ok,false);assert.equal(f.state.pendingResult,undefined);
});
