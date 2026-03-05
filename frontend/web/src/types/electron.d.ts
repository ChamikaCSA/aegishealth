export interface ElectronAPI {
  startAgent: (args: {
    clientId: number;
    dataDir: string;
    serverAddr: string;
    tlsCert?: string;
  }) => Promise<void>;
  stopAgent: () => Promise<void>;
  isRunning: () => Promise<boolean>;
  onAgentStateChange: (cb: (running: boolean) => void) => () => void;
  onAgentLog: (cb: (line: string) => void) => () => void;
  showDirectoryPicker: () => Promise<string | null>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
