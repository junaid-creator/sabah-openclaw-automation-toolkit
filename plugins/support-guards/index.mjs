import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { registerNative } from './native.mjs';
export default definePluginEntry({id:'toolkit-support-guards',name:'Toolkit Support Guards',register:registerNative});
