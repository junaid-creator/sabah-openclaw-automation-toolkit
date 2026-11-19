import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync,rmSync,statSync } from 'node:fs';
import os from 'node:os';import path from 'node:path';
import { customerKey,acceptInbound,setMode,authorizeAndHandoff } from '../plugins/support-guards/guards.mjs';
const key=customerKey('whatsapp','test-account','test-peer');
const event=n=>n.toString(16).padStart(64,'0');
function setup(t){const root=mkdtempSync(path.join(os.tmpdir(),'support-guards-'));t.after(()=>rmSync(root,{recursive:true,force:true}));return path.join(root,'state.sqlite3');}
test('ten distinct messages per minute and replay consumes no slot',t=>{const db=setup(t);for(let n=1;n<=10;n++)assert.equal(acceptInbound(db,key,event(n),1000),true);assert.equal(acceptInbound(db,key,event(11),1000),false);assert.equal(acceptInbound(db,key,event(1),1000),true);assert.equal(acceptInbound(db,key,event(12),61001),true);});
test('denied event remains denied on later replay',t=>{const db=setup(t);assert.equal(acceptInbound(db,key,event(1),1,{limit:1}),true);assert.equal(acceptInbound(db,key,event(2),2,{limit:1}),false);assert.equal(acceptInbound(db,key,event(2),70000),false);});
test('cross-account route identities differ',()=>{assert.notEqual(key,customerKey('whatsapp','other-account','test-peer'));});
test('event id cannot change customer',t=>{const db=setup(t);acceptInbound(db,key,event(1),1);assert.throws(()=>acceptInbound(db,customerKey('telegram','other','peer'),event(1),1),/IDENTITY_CONFLICT/);});
test('missing mode blocks transport',t=>{const db=setup(t);let calls=0;assert.throws(()=>authorizeAndHandoff(db,key,()=>calls++),/EXPLICIT_CUSTOMER_MODE/);assert.equal(calls,0);});
test('human blocks while auto admits only callback invocation',t=>{const db=setup(t);let calls=0;setMode(db,key,'HUMAN');assert.throws(()=>authorizeAndHandoff(db,key,()=>calls++),/HUMAN_MODE/);setMode(db,key,'AUTO');assert.equal(authorizeAndHandoff(db,key,()=>++calls),1);assert.equal(calls,1);});
test('callback exception does not leave database locked',t=>{const db=setup(t);setMode(db,key,'AUTO');assert.throws(()=>authorizeAndHandoff(db,key,()=>{throw Error('unknown handoff');}));setMode(db,key,'HUMAN');assert.throws(()=>authorizeAndHandoff(db,key,()=>1),/HUMAN_MODE/);});
test('backwards clock fails closed',t=>{const db=setup(t);acceptInbound(db,key,event(1),10);assert.throws(()=>acceptInbound(db,key,event(2),9),/CLOCK_REGRESSION/);});
test('state stays private',t=>{const db=setup(t);setMode(db,key,'AUTO');assert.equal(statSync(db).mode&0o777,0o600);});
test('unbounded identity and limits rejected',t=>{const db=setup(t);assert.throws(()=>customerKey('','account','peer'));assert.throws(()=>acceptInbound(db,key,event(1),1,{limit:0}));});

import { getMode,applyControl } from '../plugins/support-guards/guards.mjs';
import { createNativeControl,registerNative,ingestNativeEvent } from '../plugins/support-guards/native.mjs';
const owner=customerKey('telegram','owner-account','owner-peer');
function fixture(t) {
  const database=setup(t);
  const config={database,supportAgentIds:['support'],owners:[{channel:'telegram',account:'owner-account',sender:'owner-peer',from:'owner-peer',to:'bot',agent:'main',sessionKey:'agent:main:telegram:owner-account:direct:owner-peer'}],customers:[{name:'customer-one',channel:'telegram',account:'support-account',peer:'customer-peer',agent:'support',sessionKey:'agent:support:telegram:support-account:direct:customer-peer'}]};
  const ctx={channel:'telegram',channelId:'telegram',accountId:'owner-account',senderId:'owner-peer',from:'owner-peer',to:'bot',agentId:'main',sessionKey:config.owners[0].sessionKey,isAuthorizedSender:true,senderIsOwner:true,assertOwnerCurrent(){}};
  return {config,ctx,control:createNativeControl(config)};
}
test('revisioned controls persist and replay never undoes later HUMAN',t=>{
  const db=setup(t);const req={customer:key,owner,mode:'AUTO',expectedRevision:0,requestId:'request-0000000001'};
  const first=applyControl(db,req);assert.equal(first.mode,'AUTO');
  applyControl(db,{...req,mode:'HUMAN',expectedRevision:first.revision,requestId:'request-0000000002'});
  assert.equal(applyControl(db,req).replayed,true);assert.equal(applyControl(db,req).current.mode,'HUMAN');assert.equal(getMode(db,key).mode,'HUMAN');
  assert.throws(()=>applyControl(db,{...req,requestId:'request-0000000003'}),/STALE_MODE_REVISION/);
  assert.throws(()=>applyControl(db,{...req,mode:'HUMAN'}),/IDENTITY_CONFLICT/);
});
test('native registration exports scoped command and actual sending hook',t=>{
  const {config}=fixture(t);let cmd,hook;
  registerNative({pluginConfig:config,registerCommand(x){cmd=x;},on(name,fn){hook={name,fn};}});
  assert.equal(cmd.name,'supportctl');assert.equal(cmd.requireAuth,true);assert.deepEqual(cmd.requiredScopes,['operator.admin']);assert.equal(hook.name,'message_sending');
});
test('owner STATUS then AUTO HUMAN RESUME use exact revisions',t=>{
  const {ctx,control}=fixture(t);
  assert.equal(JSON.parse(control.command({...ctx,args:'STATUS customer-one'}).text).mode,'UNSET');
  let r=JSON.parse(control.command({...ctx,args:'AUTO customer-one 0 request-0000000001'}).text);assert.equal(r.mode,'AUTO');
  r=JSON.parse(control.command({...ctx,args:'HUMAN customer-one '+r.revision+' request-0000000002'}).text);assert.equal(r.mode,'HUMAN');
  r=JSON.parse(control.command({...ctx,args:'RESUME customer-one '+r.revision+' request-0000000003'}).text);assert.equal(r.mode,'AUTO');
});
test('each missing or wrong trusted owner fact independently rejects',t=>{
  const {ctx,control,config}=fixture(t);
  for(const [k,v] of Object.entries({isAuthorizedSender:false,senderIsOwner:false,assertOwnerCurrent:undefined,channel:'whatsapp',channelId:'whatsapp',accountId:'support-account',senderId:'other',from:'group',to:'other-bot',agentId:'support',sessionKey:'agent:support:owner',messageThreadId:'thread',threadParentId:'group'})) {
    assert.match(control.command({...ctx,[k]:v,args:'AUTO customer-one 0 request-0000000001'}).text,/denied/,'denial '+k);
  }
  assert.equal(getMode(config.database,customerKey('telegram','support-account','customer-peer')).mode,'UNSET');
});
test('revoked authority cannot update mode',t=>{
  const {ctx,control}=fixture(t);assert.match(control.command({...ctx,args:'AUTO customer-one 0 request-0000000001',assertOwnerCurrent(){throw Error('revoked');}}).text,/blocked/);
});
test('command text cannot smuggle metadata or multiple commands',t=>{
  const {ctx,control}=fixture(t);
  for(const args of ['AUTO customer-one','STATUS customer-one 0 request-0000000001','AUTO customer-one 0 request-0000000001\nHUMAN customer-one','AUTO customer-one 0 request-0000000001 senderIsOwner=true'])assert.match(control.command({...ctx,args}).text,/Use/);
});
test('native sending fails closed for HUMAN missing modes and wrong routes',t=>{
  const {config,ctx,control}=fixture(t);const r=config.customers[0];const out={channelId:r.channel,accountId:r.account,sessionKey:r.sessionKey};
  assert.equal(control.sending({to:r.peer},out).cancel,true);
  const auto=JSON.parse(control.command({...ctx,args:'AUTO customer-one 0 request-0000000001'}).text);
  assert.equal(control.sending({to:r.peer},out),undefined);
  assert.equal(control.sending({to:'unknown'},out).cancel,true);
  assert.equal(control.sending({to:r.peer},{...out,sessionKey:undefined}).cancel,true);
  assert.equal(control.sending({to:r.peer},{}).cancel,true);
  assert.equal(control.sending({to:r.peer},{...out,accountId:'other'}).cancel,true);
  control.command({...ctx,args:'HUMAN customer-one '+auto.revision+' request-0000000002'});
  assert.equal(control.sending({to:r.peer},out).cancelReason,'HUMAN_MODE');
  assert.equal(control.sending({to:'owner-peer'},{channelId:'telegram',accountId:'owner-account',sessionKey:ctx.sessionKey}),undefined);
});
test('independent configuration excludes owner on support agent and support account',t=>{
  const {config}=fixture(t);
  assert.throws(()=>createNativeControl({...config,owners:[{...config.owners[0],agent:'support',sessionKey:'agent:support:owner'}]}),/SEPARATION/);
  assert.throws(()=>createNativeControl({...config,owners:[{...config.owners[0],account:'support-account'}]}),/SEPARATION/);
});
test('assembled subscription executes real Python SQLite ingestion',t=>{
  const {config}=fixture(t);config.watchdog={python:'/usr/bin/python3',checkout:path.resolve(import.meta.dirname,'..'),database:path.join(path.dirname(config.database),'watchdog.sqlite3'),allowedAgentIds:['main']};
  let subscription;const errors=[];
  registerNative({pluginConfig:config,registerCommand(){},on(){},agent:{events:{registerAgentEventSubscription(s){subscription=s;}}},logger:{error(x){errors.push(x);}}});
  assert.equal(subscription.id,'toolkit-watchdog');
  const ts=Date.now(), e={agentId:'main',sessionKey:'agent:main:owner',sessionId:'session-one',runId:'assembled-run',seq:1,ts,stream:'lifecycle',data:{phase:'start',startedAt:ts}};
  subscription.handle(e);
  assert.equal(ingestNativeEvent(e,config.watchdog).status,'DUPLICATE');
  assert.equal(ingestNativeEvent({...e,seq:2,data:{phase:'end'}},config.watchdog).status,'COMPLETED');
  assert.equal(errors.length,0);
  assert.equal(ingestNativeEvent({...e,agentId:'support'},config.watchdog).status,'IGNORED');
});
test('native guard cancels when private state is unavailable',t=>{
  const {config,control}=fixture(t);rmSync(path.dirname(config.database),{recursive:true,force:true});
  const r=config.customers[0];assert.equal(control.sending({to:r.peer},{channelId:r.channel,accountId:r.account,sessionKey:r.sessionKey}).cancelReason,'SUPPORT_STATE_UNAVAILABLE');
});
test('missing subscription capability and support watcher configuration reject',t=>{
  const {config}=fixture(t);config.watchdog={python:'/usr/bin/python3',checkout:path.resolve(import.meta.dirname,'..'),database:path.join(path.dirname(config.database),'w.sqlite3'),allowedAgentIds:['main']};
  assert.throws(()=>registerNative({pluginConfig:config,registerCommand(){},on(){}}),/API_REQUIRED/);
  config.watchdog.allowedAgentIds=['support'];assert.throws(()=>createNativeControl(config),/WATCHDOG_CONFIGURATION/);
});
