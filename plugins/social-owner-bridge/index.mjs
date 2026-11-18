import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { createBridge } from '../product-owner-bridge/bridge.mjs';
export default definePluginEntry({id:'toolkit-social-owner-bridge',name:'Toolkit Social Owner Bridge',register(api){const bridge=createBridge({...api.pluginConfig,engineModule:'toolkit.social_commands'},{logger:api.logger});api.on('before_dispatch',bridge.before);api.on('message_sent',bridge.sent);}});
