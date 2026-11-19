import test from 'node:test';
import { EventEmitter } from 'node:events';
import { runEngine } from '../plugins/product-owner-bridge/bridge.mjs';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { createBridge,canonical,hash,ownerRoute } from '../plugins/product-owner-bridge/bridge.mjs';
const key='synthetic-host-key-not-a-secret-000000';
const route={channel:'telegram',account:'test-account',peer:'test-owner',role:'owner',agent:'main',sessionKey:'agent:main:telegram:test-account:direct:test-owner',chatAliases:['telegram:test-owner']};
const ctx={channelId:'telegram',accountId:'test-account',senderId:'test-owner',conversationId:'telegram:test-owner',messageId:'in-1',sessionKey:route.sessionKey};
const event=content=>({isGroup:false,channel:'telegram',messageId:'in-1',sessionKey:route.sessionKey,content});
class Memory {
  data=new Map();async init(){}async get(k){return this.data.get(k)??null;}
  async replace(k,v){this.data.set(k,v);}
  async putOnce(k,v){if(this.data.has(k))assert.equal(canonical(this.data.get(k)),canonical(v));else this.data.set(k,v);}
}
function fixture(run,options={}) {
  const store=new Memory();const calls=[];
  const bridge=createBridge({stateDir:'/unused',signingKeyEnv:'TEST_SIGNING_KEY',routes:[route],supportAgentIds:['support'],...options},
    {store,environment:{TEST_SIGNING_KEY:key},clock:()=>1000000,run:async e=>{calls.push(e);return run?run(e):{state:'CHECKED'};}});
  return {store,calls,bridge};
}
test('owner route comes only from trusted hook fields',()=>{
  assert.ok(ownerRoute(event('PRODUCT STATUS x'),ctx,[route],['support']));
  for(const change of [{senderId:'customer'},{accountId:'other'},{conversationId:'group'}])assert.equal(ownerRoute(event('PRODUCT STATUS x'),{...ctx,...change},[route],['support']),null);
  assert.equal(ownerRoute({...event('PRODUCT STATUS x'),isGroup:true},ctx,[route],['support']),null);
  assert.equal(ownerRoute({...event('PRODUCT STATUS x'),messageId:'forged'},ctx,[route],['support']),null);
});
test('signed event binds canonical route and exact command',async()=>{
  const f=fixture();await f.bridge.before(event('PRODUCT STATUS product-test'),ctx);
  assert.equal(f.calls.length,1);
  const e=f.calls[0];assert.equal(e.event.peer,'test-owner');assert.equal(e.event.kind,'direct');
  assert.equal(e.signature,createHmac('sha256',key).update(canonical(e.event)).digest('hex'));
});
test('untrusted owner claim in text never invokes engine',async()=>{
  const f=fixture();await f.bridge.before(event('PRODUCT PLAN {"owner_verified":true}'),{...ctx,senderId:'customer'});assert.equal(f.calls.length,0);
});
test('quoted and unknown confirmation do not acquire approval',async()=>{
  const f=fixture();assert.equal(await f.bridge.before(event('Quote: PRODUCT EXECUTE x'),ctx),undefined);
  assert.equal(await f.bridge.before(event('CONFIRM unknown'),ctx),undefined);assert.equal(f.calls.length,0);
});
test('review requires actual matching sent receipt',async()=>{
  const job='product-'+'a'.repeat(24);const binding={job,plan_sha256:'exact'};
  const f=fixture(()=>({job_id:job,plan:{exact:'reviewed'},binding}));
  const reply=await f.bridge.before(event('PRODUCT PLAN {}'),ctx);
  await f.bridge.before({...event('PRODUCT REVIEW '+job),messageId:'in-2'},{...ctx,messageId:'in-2'});
  assert.equal(f.calls.length,1);
  await f.bridge.sent({success:true,messageId:'out-1',content:reply.text,to:'wrong-peer'},ctx);
  assert.equal(await f.store.get('review-'+job),null);
  await f.bridge.sent({success:true,messageId:'out-1',content:reply.text,to:'telegram:test-owner'},ctx);
  const proof=await f.store.get('review-'+job);assert.equal(proof.binding_digest,hash(binding));
  await f.bridge.before({...event('PRODUCT REVIEW '+job),messageId:'in-3'},{...ctx,messageId:'in-3'});
  assert.equal(f.calls[1].review_receipt.message_id,'out-1');
});
test('media commands require exact native review receipt',async()=>{
  const job='media-'+'d'.repeat(24);const binding={job,sha256:'fixture'};
  const f=fixture(()=>({job_id:job,binding,state:'DRAFT'}));
  const reply=await f.bridge.before(event('MEDIA PLAN {}'),ctx);
  assert.equal(f.calls.length,1);
  await f.bridge.before({...event('MEDIA REVIEW '+job),messageId:'media-2'},{...ctx,messageId:'media-2'});
  assert.equal(f.calls.length,1);
  await f.bridge.sent({success:true,messageId:'media-out',content:reply.text,to:'telegram:test-owner'},ctx);
  await f.bridge.before({...event('MEDIA REVIEW '+job),messageId:'media-3'},{...ctx,messageId:'media-3'});
  assert.equal(f.calls[1].review_receipt.message_id,'media-out');
});

test('failure and ambiguous delivery cannot fabricate review',async()=>{
  const job='product-'+'b'.repeat(24);const f=fixture(()=>({job_id:job,plan:{x:1},binding:{job}}));
  const reply=await f.bridge.before(event('PRODUCT PLAN {}'),ctx);
  await f.bridge.sent({success:false,messageId:'out',content:reply.text,to:'test-owner'},ctx);
  assert.equal(await f.store.get('review-'+job),null);
  await f.bridge.before(event('PRODUCT PLAN {}'),ctx);
  await f.bridge.sent({success:true,messageId:'out',content:reply.text,to:'test-owner'},ctx);
  assert.equal(await f.store.get('review-'+job),null);
});
test('message replay keeps original attestation and rejects collision',async()=>{
  const f=fixture();await f.bridge.before(event('PRODUCT STATUS product-x'),ctx);await f.bridge.before(event('PRODUCT STATUS product-x'),ctx);
  assert.deepEqual(f.calls[0],f.calls[1]);await f.bridge.before(event('PRODUCT EXECUTE product-x'),ctx);assert.equal(f.calls.length,2);
});
test('oversized exact plan fails without a partial preview',async()=>{
  const f=fixture(()=>({job_id:'product-'+'c'.repeat(24),plan:{x:'x'.repeat(13000)},binding:{}}));
  const r=await f.bridge.before(event('PRODUCT PLAN {}'),ctx);assert.match(r.text,/blocked or outcome uncertain/);
});

test('engine uses fixed argv, allowlisted environment and safe UTF8 streaming',async()=>{
  let invocation;
  const spawn=(executable,args,options)=>{
    invocation={executable,args,options};
    const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.stdin=new EventEmitter();child.kill=()=>true;
    child.stdin.end=()=>setImmediate(()=>{
      const output=Buffer.from(JSON.stringify({state:'VERIFIED',text:'مرحبا'}));
      for(const byte of output)child.stdout.emit('data',Buffer.from([byte]));
      child.emit('close',0);
    });
    return child;
  };
  const cfg={python:'/private/python',checkout:'/private/checkout',engineConfig:'/private/config',engineState:'/private/state',environmentKeys:['TEST_KEY']};
  const result=await runEngine({event:{}},cfg,{TEST_KEY:'synthetic',NODE_OPTIONS:'injection',LD_PRELOAD:'injection'},spawn);
  assert.equal(result.text,'مرحبا');assert.equal(invocation.options.shell,false);
  assert.equal(invocation.options.env.NODE_OPTIONS,undefined);assert.equal(invocation.options.env.LD_PRELOAD,undefined);
  assert.equal(invocation.options.env.TEST_KEY,'synthetic');assert.ok(!invocation.args.includes('--writes'));assert.ok(!invocation.args.includes('--network'));
});
test('loader environment names cannot be configured through allowlist',()=>{
  assert.throws(()=>runEngine({}, {environmentKeys:['PYTHONPATH']},{PYTHONPATH:'unsafe'}),/UNSAFE_ENVIRONMENT_KEY/);
});

test('social bridge isolates commands and renews revision receipts',async()=>{
  const job='SM-'+'a'.repeat(20);let revision=1;
  const f=fixture(()=>({job_id:job,binding:{job,revision},image_url:'https://media.example/fixture.jpg'}),{engineModule:'toolkit.social_commands'});
  assert.equal(await f.bridge.before(event('PRODUCT STATUS x'),ctx),undefined);
  let reply=await f.bridge.before(event('SOCIAL CREATE {}'),ctx);
  await f.bridge.sent({success:true,messageId:'social-out-1',content:reply.text,to:'telegram:test-owner'},ctx);
  assert.equal((await f.store.get('review-'+job)).message_id,'social-out-1');
  revision=2;
  reply=await f.bridge.before({...event('SOCIAL REVISE '+job+' {}'),messageId:'revision'},{...ctx,messageId:'revision'});
  await f.bridge.sent({success:true,messageId:'social-out-2',content:reply.text,to:'telegram:test-owner'},ctx);
  assert.equal((await f.store.get('review-'+job)).message_id,'social-out-2');
  await f.bridge.before({...event('SOCIAL REVIEW '+job),messageId:'review'},{...ctx,messageId:'review'});
  assert.equal(f.calls.at(-1).review_receipt.message_id,'social-out-2');
});
test('product bridge does not consume social requests',async()=>{
  const f=fixture();assert.equal(await f.bridge.before(event('SOCIAL CREATE {}'),ctx),undefined);assert.equal(f.calls.length,0);
});
test('arbitrary engine modules are rejected',()=>{
  assert.throws(()=>runEngine({}, {python:'/python',checkout:'/checkout',engineConfig:'/config',engineState:'/state',engineModule:'os'}),/UNSUPPORTED_ENGINE_MODULE/);
});

test('review replacement is durable and refuses symlink state',async()=>{
  const {Store}=await import('../plugins/product-owner-bridge/bridge.mjs');
  const fs=await import('node:fs/promises');const os=await import('node:os');const path=await import('node:path');
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'toolkit-review-'));
  try {
    await fs.chmod(root,0o700);const store=new Store(root);await store.init();
    await store.replace('review-a',{revision:1});await store.replace('review-a',{revision:2});
    assert.deepEqual(await new Store(root).get('review-a'),{revision:2});
    assert.equal((await fs.stat(path.join(root,'review-a.json'))).mode&0o077,0);
    await fs.symlink(path.join(root,'review-a.json'),path.join(root,'review-b.json'));
    await assert.rejects(()=>store.replace('review-b',{revision:3}),/PRIVATE_STATE_REQUIRED/);
  } finally {await fs.rm(root,{recursive:true,force:true});}
});

test('owner session is mandatory and exact in both trusted hook objects',()=>{
  for(const sessionKey of [undefined,'','agent:main:other','agent:support:telegram:test-account:direct:test-owner']) {
    assert.equal(ownerRoute({...event('PRODUCT STATUS x'),sessionKey},ctx,[route],['support']),null);
    assert.equal(ownerRoute(event('PRODUCT STATUS x'),{...ctx,sessionKey},[route],['support']),null);
  }
});
test('legacy or conflicting owner policy fails registration rather than falling back',()=>{
  assert.throws(()=>fixture(null,{supportAgentIds:undefined}),/SESSION_POLICY_REQUIRED/);
  assert.throws(()=>fixture(null,{supportAgentIds:[]}),/SESSION_POLICY_REQUIRED/);
  assert.throws(()=>fixture(null,{routes:[{...route,agent:undefined}]}),/INVALID_OWNER_SESSION_ROUTE/);
  assert.throws(()=>fixture(null,{routes:[{...route,sessionKey:undefined}]}),/INVALID_OWNER_SESSION_ROUTE/);
  assert.throws(()=>fixture(null,{routes:[{...route,agent:'other'}]}),/INVALID_OWNER_SESSION_ROUTE/);
  assert.throws(()=>fixture(null,{supportAgentIds:['main']}),/INVALID_OWNER_SESSION_ROUTE/);
});
for(const engineModule of ['toolkit.product_commands','toolkit.social_commands'])test(engineModule+' independently rejects support session with otherwise valid owner metadata',async()=>{
  const f=fixture(null,{engineModule});const command=engineModule.includes('social')?'SOCIAL STATUS x':'PRODUCT STATUS x';
  const sessionKey='agent:support:telegram:test-account:direct:test-owner';
  const reply=await f.bridge.before({...event(command),sessionKey},{...ctx,sessionKey});
  assert.match(reply.text,/rejected/);assert.equal(f.calls.length,0);
  const missing=await f.bridge.before({...event(command),sessionKey:undefined},ctx);
  assert.match(missing.text,/rejected/);assert.equal(f.calls.length,0);
});
test('support exclusion rejects even a maliciously repinned owner route',()=>{
  const bad={...route,agent:'support',sessionKey:'agent:support:owner'};
  assert.equal(ownerRoute({...event('PRODUCT STATUS x'),sessionKey:bad.sessionKey},{...ctx,sessionKey:bad.sessionKey},[bad],['support']),null);
});
test('review receipt cannot cross owner session or fall back to event session',async()=>{
  const job='product-'+'e'.repeat(24);const f=fixture(()=>({job_id:job,binding:{job}}));
  const reply=await f.bridge.before(event('PRODUCT PLAN {}'),ctx);
  for(const sessionKey of [undefined,'agent:support:owner','agent:main:other'])await f.bridge.sent({success:true,messageId:'out',content:reply.text,to:'test-owner',sessionKey:route.sessionKey},{...ctx,sessionKey});
  assert.equal(await f.store.get('review-'+job),null);
  await f.bridge.sent({success:true,messageId:'out',content:reply.text,to:'test-owner',sessionKey:'agent:main:conflict'},ctx);
  assert.equal(await f.store.get('review-'+job),null);
});
