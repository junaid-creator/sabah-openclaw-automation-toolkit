/** Original portable adaptation of the native product before_dispatch bridge.
 * Host hook metadata is the authority. This module is never a model-callable tool.
 */
import { spawn } from 'node:child_process';
import { StringDecoder } from 'node:string_decoder';
import { createHash, createHmac } from 'node:crypto';
import { mkdir, open, readFile, lstat, rename, unlink } from 'node:fs/promises';
import path from 'node:path';

export const canonical = value => JSON.stringify(sort(value));
function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k=>[k,sort(value[k])]));
  return value;
}
export const hash = value => createHash('sha256').update(typeof value==='string'?value:canonical(value)).digest('hex');
const safeId = value => typeof value==='string' && /^[a-zA-Z0-9_-]{1,100}$/.test(value);

const boundedRouteValue = value => typeof value==='string' && value.length>0 && value.length<=512 && !/[\x00-\x1f\x7f]/.test(value);
export function validateOwnerRoutes(routes,supportAgentIds) {
  if(!Array.isArray(supportAgentIds)||!supportAgentIds.length||!supportAgentIds.every(safeId)||!Array.isArray(routes)||!routes.length)throw Error('EXPLICIT_OWNER_AND_SUPPORT_SESSION_POLICY_REQUIRED');
  const seen=new Set();
  for(const r of routes) {
    if(!r || r.role!=='owner'||!safeId(r.agent)||supportAgentIds.includes(r.agent)||!['channel','account','peer','sessionKey'].every(k=>boundedRouteValue(r[k]))||!r.sessionKey.startsWith('agent:'+r.agent+':'))throw Error('INVALID_OWNER_SESSION_ROUTE');
    for(const k of ['senderAliases','chatAliases'])if(r[k]!==undefined&&(!Array.isArray(r[k])||!r[k].every(boundedRouteValue)))throw Error('INVALID_OWNER_ROUTE_ALIASES');
    const key=canonical([r.channel,r.account,r.peer,r.sessionKey]);
    if(seen.has(key))throw Error('DUPLICATE_OWNER_SESSION_ROUTE');seen.add(key);
  }
}
export function ownerRoute(event, ctx, routes, supportAgentIds) {
  try{validateOwnerRoutes(routes,supportAgentIds);}catch{return null;}
  if (event?.isGroup!==false || typeof ctx?.messageId!=='string' || !ctx.messageId || ctx.messageId.length>256) return null;
  // before_dispatch has no agentId or owner assertion: do not invent either.
  if(!boundedRouteValue(ctx.sessionKey)||!boundedRouteValue(event.sessionKey)||event.sessionKey!==ctx.sessionKey)return null;
  if(supportAgentIds.some(a=>ctx.sessionKey.startsWith('agent:'+a+':')||event.sessionKey.startsWith('agent:'+a+':')))return null;
  if ((event.channel!==undefined && event.channel!==ctx.channelId) || (event.messageId!==undefined && event.messageId!==ctx.messageId)) return null;
  const matches=routes.filter(r=>r.role==='owner' && r.sessionKey===ctx.sessionKey && ctx.sessionKey.startsWith('agent:'+r.agent+':') && !supportAgentIds.includes(r.agent) && r.channel===ctx.channelId && r.account===ctx.accountId &&
    [r.peer,...(r.senderAliases??[])].includes(ctx.senderId) && [r.peer,...(r.chatAliases??[])].includes(ctx.conversationId));
  return matches.length===1 ? matches[0] : null;
}

export class Store {
  constructor(root) {if(!path.isAbsolute(root))throw Error('ABSOLUTE_PRIVATE_STATE_REQUIRED');this.root=root;}
  async init() {
    await mkdir(this.root,{recursive:true,mode:0o700});
    const st=await lstat(this.root);
    if(!st.isDirectory() || st.isSymbolicLink() || (st.mode&0o077) || st.uid!==process.getuid())throw Error('PRIVATE_STATE_REQUIRED');
  }
  async get(name) {
    if(!safeId(name))throw Error('INVALID_STATE_KEY');
    const file=path.join(this.root,name+'.json');
    try {const st=await lstat(file);if(!st.isFile()||st.isSymbolicLink()||(st.mode&0o077)||st.uid!==process.getuid())throw Error('PRIVATE_STATE_REQUIRED');return JSON.parse(await readFile(file,'utf8'));}
    catch(e){if(e.code==='ENOENT')return null;throw e;}
  }
  async replace(name,value) {
    if(!safeId(name))throw Error('INVALID_STATE_KEY');
    await this.get(name);
    const temporary=path.join(this.root,name+'-'+process.pid+'-'+Date.now()+'.tmp');
    const target=path.join(this.root,name+'.json');
    let handle;
    try {handle=await open(temporary,'wx',0o600);await handle.writeFile(canonical(value));await handle.sync();await handle.close();handle=null;await rename(temporary,target);const directory=await open(this.root,'r');try{await directory.sync();}finally{await directory.close();}}
    finally {await handle?.close();await unlink(temporary).catch(e=>{if(e.code!=='ENOENT')throw e;});}
  }
  async putOnce(name,value) {
    if(!safeId(name))throw Error('INVALID_STATE_KEY');
    const file=path.join(this.root,name+'.json');
    let handle;
    try {handle=await open(file,'wx',0o600);await handle.writeFile(canonical(value));await handle.sync();}
    catch(e){if(e.code!=='EEXIST')throw e;const prior=await this.get(name);if(canonical(prior)!==canonical(value))throw Error('STATE_CONFLICT');}
    finally{await handle?.close();}
  }
}

export function runEngine(envelope, config, environment=process.env, spawnFn=spawn) {
  const env={PATH:'/usr/local/bin:/usr/bin:/bin',LANG:'C.UTF-8',PYTHONNOUSERSITE:'1',PYTHONDONTWRITEBYTECODE:'1'};
  for(const key of config.environmentKeys??[]) {
    if(!/^[A-Z][A-Z0-9_]{0,80}$/.test(key) || /^(?:LD_|DYLD_|PYTHON|NODE_OPTIONS|PATH|HOME)/.test(key))throw Error('UNSAFE_ENVIRONMENT_KEY');
    if(typeof environment[key]==='string')env[key]=environment[key];
  }
  if(!path.isAbsolute(config.python)||!path.isAbsolute(config.checkout)||!path.isAbsolute(config.engineConfig)||!path.isAbsolute(config.engineState))throw Error('EXPLICIT_OPERATOR_PATHS_REQUIRED');
  const module=config.engineModule??'toolkit.product_commands';
  if(!['toolkit.product_commands','toolkit.social_commands'].includes(module))throw Error('UNSUPPORTED_ENGINE_MODULE');
  const args=['-m',module,'--config',config.engineConfig,'--state',config.engineState];
  if(config.allowNetwork===true)args.push('--network');
  if(config.allowWrites===true)args.push('--writes');
  return new Promise((resolve,reject)=>{
    let settled=false,stdout='',bytes=0,child,timer;
    const decoder=new StringDecoder('utf8');
    const finish=(error,result)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(result);};
    const stop=()=>{try{child?.kill('SIGKILL');}catch{}};
    try {
      child=spawnFn(config.python,args,{cwd:config.checkout,env,shell:false,stdio:['pipe','pipe','pipe']});
      timer=setTimeout(()=>{stop();finish(Error('ENGINE_TIMEOUT_UNKNOWN'));},180000);
      child.on('error',()=>finish(Error('ENGINE_START_FAILED')));
      child.stdin.on('error',()=>{stop();finish(Error('ENGINE_INPUT_FAILED'));});
      child.stdout.on('data',chunk=>{bytes+=Buffer.byteLength(chunk);if(bytes>262144){stop();finish(Error('ENGINE_OUTPUT_LIMIT'));}else stdout+=decoder.write(Buffer.isBuffer(chunk)?chunk:Buffer.from(chunk));});
      child.stderr.on('data',chunk=>{bytes+=Buffer.byteLength(chunk);if(bytes>262144){stop();finish(Error('ENGINE_OUTPUT_LIMIT'));}});
      child.on('close',code=>{if(code!==0)return finish(Error('ENGINE_BLOCKED_OR_FAILED'));try{const value=JSON.parse(stdout+decoder.end());if(!value||typeof value!=='object')throw Error();finish(null,value);}catch{finish(Error('ENGINE_INVALID_RESULT'));}});
      child.stdin.end(canonical(envelope));
    }catch{stop();finish(Error('ENGINE_START_FAILED'));}
  });
}

export function createBridge(config,{store=new Store(config.stateDir),run=env=>runEngine(env,config),environment=process.env,clock=()=>Date.now(),logger={warn(){}}}={}) {
  if(!Array.isArray(config.routes)||!config.routes.length||typeof config.signingKeyEnv!=='string')throw Error('EXPLICIT_OWNER_ROUTES_REQUIRED');
  validateOwnerRoutes(config.routes,config.supportAgentIds);
  const key=environment[config.signingKeyEnv];
  if(typeof key!=='string'||Buffer.byteLength(key)<32)throw Error('HOST_SIGNING_KEY_REQUIRED');
  const pending=[];
  const remember=(job,binding,text,route,ctx)=>{
    if(pending.length>=100)throw Error('PENDING_REVIEW_LIMIT');
    pending.push({job,binding,digest:hash(text),route,session:ctx.sessionKey??null,created:clock()});
  };
  async function before(event,ctx) {
    const text=event?.content;
    const social=config.engineModule==='toolkit.social_commands';
    const relevant=typeof text==='string' && (text.startsWith('CONFIRM ') || (social?text.startsWith('SOCIAL '):(text.startsWith('PRODUCT ')||text.startsWith('MEDIA '))));
    if(!relevant)return undefined;
    if(text.length>60000 || /[\x00-\x1f\x7f]/.test(text))return {handled:true,text:'Product command rejected: one bounded exact command required.'};
    const route=ownerRoute(event,ctx,config.routes,config.supportAgentIds);
    if(!route)return {handled:true,text:'Product command rejected: trusted direct owner route required.'};
    try {
      await store.init();
      if(text.startsWith('CONFIRM ')) {
        const cid=text.slice(8);if(!safeId(cid)||!await store.get('challenge-'+cid))return undefined;
      }
      const id=hash([route.channel,route.account,route.peer,ctx.messageId]);
      const previous=await store.get('event-'+id);
      const attested={id,channel:route.channel,account:route.account,peer:route.peer,kind:'direct',timestamp:Math.floor(clock()/1000),text};
      if(previous) {
        if(previous.text!==text)throw Error('EVENT_COLLISION');
        attested.timestamp=previous.timestamp;
      } else await store.putOnce('event-'+id,attested);
      const envelope={event:attested,signature:createHmac('sha256',key).update(canonical(attested)).digest('hex')};
      const review=text.match(social?/^SOCIAL REVIEW (SM-[a-f0-9]{20})$/:/^(?:PRODUCT|MEDIA) REVIEW ((?:product|media)-[a-f0-9]{24})$/);
      if(review) {
        const proof=await store.get('review-'+review[1]);
        if(!proof || proof.peer!==route.peer || proof.channel!==route.channel || proof.account!==route.account)throw Error('REAL_REVIEW_RECEIPT_REQUIRED');
        envelope.review_receipt=proof;
      }
      const result=await run(envelope);
      const reply=canonical(result);
      if(reply.length>12000)throw Error('REVIEW_TOO_LARGE_FOR_INLINE_DELIVERY');
      if(result.binding && safeId(result.job_id))remember(result.job_id,result.binding,reply,route,ctx);
      if(result.challenge_id && safeId(result.challenge_id))await store.putOnce('challenge-'+result.challenge_id,{job:review?.[1]??null});
      return {handled:true,text:reply};
    }catch {
      logger.warn('Product bridge stopped; inspect private durable state before any retry. No automatic replay.');
      return {handled:true,text:'Product command blocked or outcome uncertain. Inspect existing job status; do not create another job or replay a write.'};
    }
  }
  async function sent(event,ctx) {
    if(!boundedRouteValue(ctx?.sessionKey)||config.supportAgentIds.some(a=>ctx.sessionKey.startsWith('agent:'+a+':'))||(event?.sessionKey!==undefined&&event.sessionKey!==ctx.sessionKey))return;
    if(event?.success!==true || typeof event.messageId!=='string' || !event.messageId || typeof event.content!=='string')return;
    const fresh=pending.filter(p=>clock()-p.created<=300000);
    pending.splice(0,pending.length,...fresh);
    const matches=pending.filter(p=>p.digest===hash(event.content) && p.route.channel===ctx?.channelId && p.route.account===ctx.accountId &&
      [p.route.peer,...(p.route.chatAliases??[])].includes(event.to) && p.session===ctx.sessionKey);
    if(matches.length!==1)return;
    const p=matches[0];
    const proof={delivered:true,message_id:event.messageId,binding_digest:hash(p.binding),channel:p.route.channel,account:p.route.account,peer:p.route.peer};
    try {if(config.engineModule==='toolkit.social_commands')await store.replace('review-'+p.job,proof);else await store.putOnce('review-'+p.job,proof);pending.splice(pending.indexOf(p),1);}
    catch{logger.warn('Review receipt persistence failed; approval remains blocked.');}
  }
  return {before,sent};
}
