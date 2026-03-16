import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import path from 'path';
import { app } from 'electron';
import type { WebContents } from 'electron';

let agentProcess: ChildProcess | null = null;
let logSender: WebContents | null = null;
let stateNotifier: ((running: boolean) => void) | null = null;

export function setLogSender(wc: WebContents | null) {
  logSender = wc;
}

export function setAgentStateNotifier(cb: ((running: boolean) => void) | null) {
  stateNotifier = cb;
  if (cb) cb(agentProcess !== null);
}

function notifyState() {
  stateNotifier?.(agentProcess !== null);
}

type AgentLogEvent = { ts: string; type: string; message?: string; details?: Record<string, unknown> };

function sendLog(payload: string) {
  logSender?.send('agent:log', payload);
}

function emitStructured(event: AgentLogEvent, onLog?: (line: string) => void) {
  const payload = JSON.stringify(event);
  sendLog(payload);
  onLog?.(payload);
}

export function startAgent(
  clientId: number,
  dataDir: string,
  serverAddr: string,
  onLog?: (line: string) => void,
  tlsCert?: string,
): void {
  const emit = (event: AgentLogEvent) => {
    emitStructured(event, onLog);
  };
  if (agentProcess) {
    emit({ ts: new Date().toISOString(), type: 'agent_already_running', message: 'Agent already running' });
    return;
  }

  // Use system Python with agents module; in production would use bundled binary
  const isDev = !app.isPackaged;
  const backendDir = isDev
    ? path.resolve(app.getAppPath(), '..', '..', 'backend')
    : path.join(process.resourcesPath, 'agent');

  // Prefer venv Python in dev; fallback to python3 (macOS) or python
  const venvPython = path.join(backendDir, 'venv', 'bin', 'python');
  const pythonCmd = isDev
    ? (fs.existsSync(venvPython) ? venvPython : 'python3')
    : path.join(backendDir, 'aegishealth-agent');
  const args = isDev
    ? [
        '-m',
        'agents.agent',
        '--client-id',
        String(clientId),
        '--data-dir',
        dataDir,
        '--server',
        serverAddr,
      ]
    : ['--client-id', String(clientId), '--data-dir', dataDir, '--server', serverAddr];

  const certPath = tlsCert || path.join(backendDir, 'certs', 'ca.crt');
  args.push('--tls-cert', certPath);

  const cwd = isDev ? backendDir : undefined;

  emit({
    ts: new Date().toISOString(),
    type: 'agent_start',
    message: `client=${clientId} dataDir=${dataDir} server=${serverAddr}`,
  });
  emit({ ts: new Date().toISOString(), type: 'agent_cwd', message: cwd ?? process.cwd() });

  agentProcess = spawn(pythonCmd, args, {
    cwd,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  notifyState();

  agentProcess.stdout?.on('data', (data: Buffer) => {
    data
      .toString()
      .split('\n')
      .filter((l) => l.trim())
      .forEach((line) =>
        emit({ ts: new Date().toISOString(), type: 'agent_stdout', message: line })
      );
  });

  agentProcess.stderr?.on('data', (data: Buffer) => {
    data
      .toString()
      .split('\n')
      .filter((l) => l.trim())
      .forEach((line) =>
        emit({ ts: new Date().toISOString(), type: 'agent_stderr', message: line })
      );
  });

  agentProcess.on('close', (code, signal) => {
    emit({
      ts: new Date().toISOString(),
      type: 'agent_exit',
      message: `code=${code} signal=${signal}`,
    });
    agentProcess = null;
    notifyState();
  });

  agentProcess.on('error', (err) => {
    emit({ ts: new Date().toISOString(), type: 'agent_error', message: err.message });
    agentProcess = null;
    notifyState();
  });
}

export function stopAgent(): void {
  if (agentProcess) {
    agentProcess.kill('SIGTERM');
    agentProcess = null;
    notifyState();
  }
}

export function isRunning(): boolean {
  return agentProcess !== null;
}
