import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  startAgent: (args: {
    clientId: number;
    dataDir: string;
    serverAddr: string;
    tlsCert?: string;
  }) => ipcRenderer.invoke('agent:start', args),
  stopAgent: () => ipcRenderer.invoke('agent:stop'),
  isRunning: () => ipcRenderer.invoke('agent:isRunning') as Promise<boolean>,
  onAgentStateChange: (cb: (running: boolean) => void) => {
    const handler = (_: unknown, running: boolean) => cb(running);
    ipcRenderer.on('agent:state', handler);
    return () => ipcRenderer.removeListener('agent:state', handler);
  },
  onAgentLog: (cb: (line: string) => void) => {
    const handler = (_: unknown, line: string) => cb(line);
    ipcRenderer.on('agent:log', handler);
    return () => ipcRenderer.removeListener('agent:log', handler);
  },
  showDirectoryPicker: () => ipcRenderer.invoke('dialog:openDirectory'),
});
