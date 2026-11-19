/** Native 2026.11.5 entry logic; never a model tool or generic sender callback. */
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { lstatSync } from 'node:fs';
import { customerKey, getMode, applyControl } from './guards.mjs';

const bounded = x => typeof x==='string' && x.length>0 && x.length<=256 && !/[\x00-\x1f\x7f]/.test(x);
function privateParent(file) {
  if(!path.isAbsolute(file))throw Error('ABSOLUTE_STATE_REQUIRED');
  const s=lstatSync(path.dirname(file));
  if(!s.isDirectory()||s.isSymbolicLink()||(s.mode&0o077)||s.uid!==process.getuid())throw Error('PRIVATE_STATE_REQUIRED');
}
export function validateConfig(c) {
  if(!c || !Array.isArray(c.owners)||!c.owners.length || !Array.isArray(c.customers)||!c.customers.length ||
     !Array.isArray(c.supportAgentIds)||!c.supportAgentIds.length || !c.supportAgentIds.every(bounded))throw Error('EXPLICIT_ROUTES_REQUIRED');
  privateParent(c.database);
  const seen=new Set();
  for(const r of c.customers) {
    if(!['name','channel','account','peer','sessionKey','agent'].every(k=>bounded(r[k]))||
       !/^[a-zA-Z0-9_-]{1,64}$/.test(r.name)||!c.supportAgentIds.includes(r.agent)||
       !r.sessionKey.startsWith('agent:'+r.agent+':'))throw Error('INVALID_CUSTOMER_ROUTE');
    for(const key of ['name:'+r.name,'route:'+JSON.stringify([r.channel,r.account,r.peer]),'session:'+r.sessionKey]) {
      if(seen.has(key))throw Error('AMBIGUOUS_CUSTOMER_ROUTE');seen.add(key);
    }
  }
  const owners=new Set();
  for(const r of c.owners) {
    if(!['channel','account','sender','from','to','agent','sessionKey'].every(k=>bounded(r[k]))||
       c.supportAgentIds.includes(r.agent)||!r.sessionKey.startsWith('agent:'+r.agent+':')||
       c.customers.some(s=>s.channel===r.channel&&s.account===r.account))throw Error('OWNER_SUPPORT_SEPARATION_REQUIRED');
    const key=JSON.stringify([r.channel,r.account,r.sender,r.from,r.to,r.agent,r.sessionKey]);
    if(owners.has(key))throw Error('AMBIGUOUS_OWNER_ROUTE');owners.add(key);
  }
  if(c.watchdog) {
    const w=c.watchdog;
    if(!path.isAbsolute(w.python)||!path.isAbsolute(w.checkout)||!Array.isArray(w.allowedAgentIds)||!w.allowedAgentIds.length||
       !w.allowedAgentIds.every(x=>bounded(x)&&!c.supportAgentIds.includes(x)))throw Error('INVALID_WATCHDOG_CONFIGURATION');
    privateParent(w.database);
  }
  return c;
}
export function createNativeControl(config) {
  const c=validateConfig(config);
  function command(ctx) {
    // Core requiredScopes enforces owner-or-admin; exact routes independently exclude support.
    const route=c.owners.filter(r=>ctx.isAuthorizedSender===true && ctx.senderIsOwner===true && typeof ctx.assertOwnerCurrent==='function' && ctx.channel===r.channel &&
      (ctx.channelId===undefined||ctx.channelId===r.channel) && ctx.accountId===r.account && ctx.senderId===r.sender &&
      ctx.from===r.from && ctx.to===r.to && ctx.agentId===r.agent && ctx.sessionKey===r.sessionKey &&
      ctx.messageThreadId===undefined && ctx.threadParentId===undefined && !c.supportAgentIds.includes(ctx.agentId));
    if(route.length!==1)return {text:'Support control denied: exact private owner route required.'};
    const args=ctx.args??'';
    const m=args.match(/^(STATUS|HUMAN|AUTO|RESUME) ([a-zA-Z0-9_-]{1,64})(?: (0|[1-9][0-9]{0,14}) ([A-Za-z0-9_-]{16,64}))?$/);
    if(!m || (m[1]==='STATUS')!==(m[3]===undefined))return {text:'Use /supportctl STATUS customer or HUMAN|AUTO|RESUME customer revision request-id (16–64 characters).'};
    const customer=c.customers.find(r=>r.name===m[2]);
    if(!customer)return {text:'Support control denied: unknown configured customer.'};
    try {
      // No await between authority validation and the local transaction.
      ctx.assertOwnerCurrent();
      const key=customerKey(customer.channel,customer.account,customer.peer);
      const result=m[1]==='STATUS'?getMode(c.database,key):applyControl(c.database,{
        customer:key, mode:m[1]==='HUMAN'?'HUMAN':'AUTO', expectedRevision:Number(m[3]), requestId:m[4],
        owner:customerKey(route[0].channel,route[0].account,route[0].sender)});
      return {text:JSON.stringify({customer:customer.name,...result,scope:'native message_sending admission; in-flight sends cannot be undone'})};
    }catch{return {text:'Support control blocked: inspect STATUS; stale revision, conflicting request or private-state failure. No automatic retry.'};}
  }
  function sending(event,ctx) {
    const supportSession=c.supportAgentIds.some(a=>ctx?.sessionKey?.startsWith('agent:'+a+':'));
    const supportAccount=c.customers.some(r=>r.channel===ctx?.channelId&&r.account===ctx.accountId);
    const supportPeer=c.customers.some(r=>r.peer===event?.to&&(r.channel===ctx?.channelId||!ctx?.channelId));
    if(!supportSession&&!supportAccount&&!supportPeer)return undefined;
    const deny=reason=>({cancel:true,cancelReason:reason});
    const route=c.customers.filter(r=>r.channel===ctx?.channelId&&r.account===ctx.accountId&&r.peer===event?.to&&r.sessionKey===ctx.sessionKey);
    if(route.length!==1)return deny('SUPPORT_EXACT_ROUTE_REQUIRED');
    try {
      const mode=getMode(c.database,customerKey(route[0].channel,route[0].account,route[0].peer)).mode;
      return mode==='AUTO'?undefined:deny(mode==='HUMAN'?'HUMAN_MODE':'EXPLICIT_CUSTOMER_MODE_REQUIRED');
    }catch{return deny('SUPPORT_STATE_UNAVAILABLE');}
  }
  return {command,sending};
}

export function ingestNativeEvent(event,c) {
  // Select metadata only; never persist tool inputs/results, messages or error text.
  if(!c.allowedAgentIds.includes(event?.agentId)||!['lifecycle','tool'].includes(event.stream))return {status:'IGNORED'};
  if(event.stream==='tool'&&event.data?.phase!=='end')return {status:'IGNORED'};
  const data={};
  for(const k of ['phase','startedAt','endedAt','executionSettled','fallbackExhaustedFailure','aborted','status','stopReason','timeoutPhase','livenessState']) {
    if(['string','number','boolean'].includes(typeof event.data?.[k]))data[k]=event.data[k];
  }
  const envelope={};
  for(const k of ['runId','seq','stream','ts','sessionKey','sessionId','agentId'])envelope[k]=event[k];
  envelope.data=data;
  const args=['-m','toolkit.watchdog','ingest-runtime','--database',c.database];
  for(const a of c.allowedAgentIds)args.push('--allowed-agent',a);
  const result=spawnSync(c.python,args,{cwd:c.checkout,shell:false,input:JSON.stringify(envelope),encoding:'utf8',
    env:{PATH:'/usr/bin:/bin',LANG:'C.UTF-8',PYTHONNOUSERSITE:'1',PYTHONDONTWRITEBYTECODE:'1'},timeout:5000,maxBuffer:65536});
  if(result.error||result.status!==0)throw Error('WATCHDOG_INGESTION_FAILED_NO_REPLAY');
  return JSON.parse(result.stdout);
}
export function registerNative(api) {
  const c=validateConfig(api.pluginConfig);
  const control=createNativeControl(c);
  if(typeof api.registerCommand!=='function'||typeof api.on!=='function'||
    (c.watchdog&&typeof api.agent?.events?.registerAgentEventSubscription!=='function'))throw Error('OPENCLAW_2026_11_5_API_REQUIRED');
  api.registerCommand({name:'supportctl',description:'Owner-only revisioned support mode control',acceptsArgs:true,
    requireAuth:true,requiredScopes:['operator.admin'],channels:[...new Set(c.owners.map(r=>r.channel))],handler:control.command});
  api.on('message_sending',control.sending);
  if(c.watchdog)api.agent.events.registerAgentEventSubscription({id:'toolkit-watchdog',streams:['lifecycle','tool'],payload:'metadata',handle(event){
    try{return void ingestNativeEvent(event,c.watchdog);}catch{api.logger.error('Watchdog ingestion failed; no replay or business completion inferred. Inspect private watchdog state.');}
  }});
}
