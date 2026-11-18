/** Portable original support mode and rate admission guards; no transport. */
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { chmodSync, lstatSync, openSync, closeSync, constants } from 'node:fs';
import path from 'node:path';
export function customerKey(channel,account,peer) {
  if(![channel,account,peer].every(x=>typeof x==='string'&&x.length>0&&x.length<=256))throw Error('EXPLICIT_ROUTE_REQUIRED');
  return createHash('sha256').update(JSON.stringify([channel,account,peer])).digest('hex');
}
function id(value){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))throw Error('INVALID_BOUND_IDENTITY');}
function connect(file) {
  if(!path.isAbsolute(file))throw Error('ABSOLUTE_PRIVATE_DATABASE_REQUIRED');
  const parent=lstatSync(path.dirname(file));
  if(!parent.isDirectory()||parent.isSymbolicLink()||(parent.mode&0o077)||parent.uid!==process.getuid())throw Error('PRIVATE_PARENT_REQUIRED');
  try{const fd=openSync(file,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);closeSync(fd);}catch(e){if(e.code!=='EEXIST')throw e;}
  const st=lstatSync(file);if(!st.isFile()||st.isSymbolicLink()||(st.mode&0o077)||st.uid!==process.getuid())throw Error('PRIVATE_DATABASE_REQUIRED');
  const db=new DatabaseSync(file);chmodSync(file,0o600);
  db.exec('PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS customer_mode(customer TEXT PRIMARY KEY,mode TEXT NOT NULL); CREATE TABLE IF NOT EXISTS inbound_limit_events(event_id TEXT PRIMARY KEY,customer TEXT NOT NULL,accepted_at INTEGER NOT NULL,allowed INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS mode_events(id INTEGER PRIMARY KEY,customer TEXT,mode TEXT,at INTEGER);');
  return db;
}
export function setMode(file,customer,mode,now=Date.now()) {
  // Privileged local API: caller MUST authenticate owner. Never register as a customer tool.
  id(customer);if(!['AUTO','HUMAN'].includes(mode)||!Number.isSafeInteger(now))throw Error('INVALID_MODE');
  const db=connect(file);let active=false;
  try {db.exec('BEGIN IMMEDIATE');active=true;
    db.prepare('INSERT INTO customer_mode VALUES(?,?) ON CONFLICT(customer) DO UPDATE SET mode=excluded.mode').run(customer,mode);
    db.prepare('INSERT INTO mode_events(customer,mode,at) VALUES(?,?,?)').run(customer,mode,now);
    db.exec('COMMIT');active=false;
  } finally{if(active)db.exec('ROLLBACK');db.close();}
}
export function acceptInbound(file,customer,eventId,now=Date.now(),{limit=10,windowMs=60000}={}) {
  id(customer);id(eventId);
  if(!Number.isSafeInteger(now)||!Number.isSafeInteger(limit)||limit<1||limit>1000||!Number.isSafeInteger(windowMs)||windowMs<1||windowMs>86400000)throw Error('INVALID_BOUND');
  const db=connect(file);let active=false;
  try {db.exec('BEGIN IMMEDIATE');active=true;
    const old=db.prepare('SELECT customer,allowed FROM inbound_limit_events WHERE event_id=?').get(eventId);
    if(old){if(old.customer!==customer)throw Error('EVENT_IDENTITY_CONFLICT');db.exec('COMMIT');active=false;return old.allowed===1;}
    const latest=db.prepare('SELECT MAX(accepted_at) AS at FROM inbound_limit_events WHERE customer=?').get(customer).at;
    if(latest!==null&&now<latest)throw Error('CLOCK_REGRESSION');
    const count=db.prepare('SELECT COUNT(*) AS n FROM inbound_limit_events WHERE customer=? AND accepted_at>? AND allowed=1').get(customer,now-windowMs).n;
    const allowed=count<limit;
    db.prepare('INSERT INTO inbound_limit_events VALUES(?,?,?,?)').run(eventId,customer,now,allowed?1:0);
    // No automatic tombstone deletion: an old event never becomes a new admission.
    db.exec('COMMIT');active=false;return allowed;
  } finally{if(active)db.exec('ROLLBACK');db.close();}
}
export function authorizeAndHandoff(file,customer,handoff) {
  id(customer);if(typeof handoff!=='function')throw Error('TRUSTED_TRANSPORT_CALLBACK_REQUIRED');
  const db=connect(file);let active=false;
  try {db.exec('BEGIN IMMEDIATE');active=true;
    const row=db.prepare('SELECT mode FROM customer_mode WHERE customer=?').get(customer);
    if(!row || !['AUTO','HUMAN'].includes(row.mode))throw Error('EXPLICIT_CUSTOMER_MODE_REQUIRED');
    if(row.mode==='HUMAN')throw Error('HUMAN_MODE');
    const pending=handoff();
    db.exec('COMMIT');active=false;return pending;
  } finally{if(active)db.exec('ROLLBACK');db.close();}
}
