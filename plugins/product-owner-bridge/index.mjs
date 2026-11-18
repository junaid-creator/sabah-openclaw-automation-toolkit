import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { createBridge } from './bridge.mjs';
export default definePluginEntry({
  id:'toolkit-product-owner-bridge',name:'Toolkit Product Owner Bridge',
  register(api) {
    const bridge=createBridge(api.pluginConfig,{logger:api.logger});
    api.on('before_dispatch',bridge.before);
    api.on('message_sent',bridge.sent);
  }
});
