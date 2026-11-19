"""Offline native SDK smoke. No Gateway, install, API or transport is started."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = os.environ.get('OPENCLAW_NATIVE_SDK')

@unittest.skipUnless(SDK, 'set OPENCLAW_NATIVE_SDK to a read-only OpenClaw 2026.11.5 package')
class NativeSupportControlTests(unittest.TestCase):
    def test_actual_sdk_entry_registers_and_executes_local_controls(self):
        sdk=Path(SDK).resolve()
        self.assertEqual(json.loads((sdk/'package.json').read_text())['version'],'2026.11.5')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/'plugins/support-guards',root/'plugin')
            (root/'node_modules').mkdir()
            (root/'node_modules/openclaw').symlink_to(sdk,target_is_directory=True)
            script=r"""
import assert from 'node:assert/strict';
import plugin from './plugin/index.mjs';
const cfg={database:process.cwd()+'/control.sqlite3',supportAgentIds:['support'],
 owners:[{channel:'telegram',account:'owner',sender:'operator',from:'operator',to:'bot',agent:'main',sessionKey:'agent:main:telegram:owner:direct:operator'}],
 customers:[{name:'demo',channel:'telegram',account:'support',peer:'customer',agent:'support',sessionKey:'agent:support:telegram:support:direct:customer'}]};
let cmd,send;
plugin.register({pluginConfig:cfg,registerCommand(c){cmd=c;},on(n,h){assert.equal(n,'message_sending');send=h;}});
assert.equal(plugin.id,'toolkit-support-guards');assert.deepEqual(cmd.requiredScopes,['operator.admin']);
const ctx={channel:'telegram',channelId:'telegram',accountId:'owner',senderId:'operator',from:'operator',to:'bot',agentId:'main',sessionKey:cfg.owners[0].sessionKey,isAuthorizedSender:true,senderIsOwner:true,assertOwnerCurrent(){}};
assert.match(cmd.handler({...ctx,senderIsOwner:false,args:'AUTO demo 0 native-request-0001'}).text,/denied/);
const result=JSON.parse(cmd.handler({...ctx,args:'AUTO demo 0 native-request-0001'}).text);
assert.equal(result.mode,'AUTO');
const out={channelId:'telegram',accountId:'support',sessionKey:cfg.customers[0].sessionKey};
assert.equal(send({to:'customer'},out),undefined);
const human=JSON.parse(cmd.handler({...ctx,args:'HUMAN demo '+result.revision+' native-request-0002'}).text);
assert.equal(human.mode,'HUMAN');assert.equal(send({to:'customer'},out).cancel,true);
console.log(JSON.stringify({sdk:'2026.11.5',entry:plugin.id,command:cmd.name,localMode:human.mode,sendCancelled:true,network:false}));
"""
            completed=subprocess.run(['node','--input-type=module','-e',script],cwd=root,
                env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(root),
                     'LANG':'C.UTF-8','OPENCLAW_STATE_DIR':str(root/'state'),
                     'OPENCLAW_CONFIG_PATH':str(root/'config.json')},
                text=True,capture_output=True,timeout=30)
            print('native SDK child exit:',completed.returncode)
            print(completed.stdout,end='')
            print(completed.stderr,end='')
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            self.assertIn('"sendCancelled":true',completed.stdout)

if __name__=='__main__':unittest.main()
