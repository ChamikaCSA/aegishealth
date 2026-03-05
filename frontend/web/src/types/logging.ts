export type LogLevel = "info" | "warn" | "error" | "debug";

export interface LogEvent {
  ts: string;
  type: string;
  level?: LogLevel;
  message?: string;
  details?: Record<string, unknown>;
  jobId?: number;
  clientId?: number;
}
