"""Actual SDK import/registration only; no Gateway or plugin activation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = os.environ.get('OPENCLAW_NATIVE_SDK')


@unittest.skipUnless(SDK, 'OPENCLAW_NATIVE_SDK required for actual SDK import')
class NativeOwnerEntryTests(unittest.TestCase):
    def test_both_entries_register_with_real_sdk(self):
        sdk = Path(SDK).resolve()
        self.assertEqual(json.loads((sdk/'package.json').read_text())['version'], '2026.11.5')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('product-owner-bridge', 'social-owner-bridge'):
                shutil.copytree(ROOT/'plugins'/name, root/'plugins'/name)
            (root/'node_modules').mkdir()
            (root/'node_modules/openclaw').symlink_to(sdk, target_is_directory=True)
            script = r'''
import assert from 'node:assert/strict';
process.env.FIXTURE_BRIDGE_KEY='synthetic-owner-sdk-key-not-a-secret-000000';
for (const name of ['product-owner-bridge','social-owner-bridge']) {
 const plugin=(await import('./plugins/'+name+'/index.mjs')).default;
 const hooks=[];
 const config={stateDir:process.cwd(),signingKeyEnv:'FIXTURE_BRIDGE_KEY',supportAgentIds:['support'],
  routes:[{role:'owner',channel:'fixture',account:'owner',peer:'operator',agent:'main',sessionKey:'agent:main:fixture:owner:direct:operator'}]};
 plugin.register({pluginConfig:config,logger:{warn(){}},on(name,handler){assert.equal(typeof handler,'function');hooks.push(name);}});
 assert.deepEqual(hooks,['before_dispatch','message_sent']);
 assert.equal(plugin.id,'toolkit-'+name);
}
console.log('Two actual SDK owner entries registered; no hooks invoked, no Gateway activated');
'''
            result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=root,
                env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(root),
                     'LANG':'C.UTF-8','OPENCLAW_STATE_DIR':str(root/'state'),
                     'OPENCLAW_CONFIG_PATH':str(root/'config.json')}, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
