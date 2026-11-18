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
