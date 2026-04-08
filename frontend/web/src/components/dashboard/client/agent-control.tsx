"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LogViewer } from "@/components/shared/log-viewer";
import { ReleasedModels } from "@/components/dashboard/client/released-models";
import { useAuth } from "@/lib/auth";
import type { LogEvent } from "@/types/logging";
import { supabase } from "@/lib/supabase";

interface AuditLog {
  event_type: string;
  job_id: number | null;
  client_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

function getOrchestratorAddr(): string {
  const explicit = process.env.NEXT_PUBLIC_ORCHESTRATOR_ADDR?.trim();
  if (explicit) return explicit;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
  try {
    const url = new URL(apiUrl);
    return `${url.hostname}:50051`;
  } catch {
    return "localhost:50051";
  }
}

export function AgentControl() {
  const { user } = useAuth();
  const [dataDir, setDataDir] = useState("");
  const [logs, setLogs] = useState<{ ts: string; line: string }[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [localProcessRunning, setLocalProcessRunning] = useState(false);
  const [agentStatus, setAgentStatus] = useState<string>("disconnected");
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const clientId = user?.client_id ?? 0;

  useEffect(() => {
    const api = typeof window !== "undefined" ? window.electronAPI : undefined;
    if (!api?.onAgentLog) return;
    const handler = (payload: string) => {
      let entry: { ts: string; line: string };
      try {
        const parsed = JSON.parse(payload) as {
          ts?: string;
          type?: string;
          message?: string;
        };
        if (parsed.ts && parsed.type) {
          const type = parsed.type.toLowerCase();
          const cleanType = type === "agent_stdout" ? "log" : type === "agent_stderr" ? "error" : type;
          const msg = parsed.message
            ? `[${cleanType}] ${parsed.message}`
            : `[${cleanType}]`;
          entry = { ts: parsed.ts, line: msg };
          if (type === "agent_exit" || type === "agent_error") {
            setIsStarting(false);
          }
        } else {
          entry = { ts: new Date().toISOString(), line: payload };
        }
      } catch {
        entry = { ts: new Date().toISOString(), line: payload };
        if (
          payload.includes("[Agent exited]") ||
          payload.includes("[Agent error]")
        ) {
          setIsStarting(false);
        }
      }
      setLogs((prev) => [...prev.slice(-499), entry]);
    };
    const cleanup = api.onAgentLog(handler);
    return () => cleanup();
  }, []);

  useEffect(() => {
    const api = typeof window !== "undefined" ? window.electronAPI : undefined;
    if (!api?.isRunning || !api?.onAgentStateChange) return;
    api.isRunning().then(setLocalProcessRunning);
    const cleanup = api.onAgentStateChange(setLocalProcessRunning);
    return () => cleanup();
  }, []);

  const fetchCompliance = useCallback(async () => {
    if (!user?.client_id) return;
    try {
      const { data: fleet } = await supabase
        .from("client_registry")
        .select("client_id, status");
      const myClient = (fleet ?? []).find(
        (c) => c.client_id === user?.client_id
      );
      setAgentStatus(myClient ? myClient.status : "disconnected");

      const { data: logs } = await supabase
        .from("audit_logs")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(100);
      const allLogs = (logs as AuditLog[]) ?? [];
      const myLogs = allLogs.filter(
        (l) => l.client_id === user?.client_id || l.client_id === null
      );
      setAuditLogs(myLogs);
    } catch {
      setAuditLogs([]);
    }
  }, [user?.client_id]);

  useEffect(() => {
    fetchCompliance();
  }, [fetchCompliance, localProcessRunning]);

  useEffect(() => {
    const channel = supabase
      .channel("audit_and_fleet_patching")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "audit_logs" },
        (payload) => {
          const newEntry = payload.new as AuditLog;
          if (newEntry.client_id === user?.client_id || newEntry.client_id === null) {
            setAuditLogs((prev) => {
               if (prev.find(l => l.created_at === newEntry.created_at && l.event_type === newEntry.event_type)) return prev;
               return [newEntry, ...prev].slice(0, 100);
            });
          }
        }
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "client_registry" },
        (payload) => {
          if (payload.eventType === "UPDATE" || payload.eventType === "INSERT") {
            const updatedClient = payload.new as { client_id: number; status: string };
            if (updatedClient.client_id === user?.client_id) {
              setAgentStatus(updatedClient.status);
            }
          } else if (payload.eventType === "DELETE") {
            if ((payload.old as { client_id: number }).client_id === user?.client_id) {
              setAgentStatus("disconnected");
            }
          }
        }
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [user?.client_id]);

  useEffect(() => {
    if (["training", "idle", "connected"].includes(agentStatus)) {
      setIsStarting(false);
    }
  }, [agentStatus]);

  useEffect(() => {
    if (!localProcessRunning && agentStatus === "disconnected") {
      setIsStopping(false);
    }
  }, [agentStatus, localProcessRunning]);



  const handlePickDir = async () => {
    const api = window.electronAPI;
    if (!api?.showDirectoryPicker) return;
    const path = await api.showDirectoryPicker();
    if (path) setDataDir(path);
  };

  const handleStart = async () => {
    const api = window.electronAPI;
    if (!api?.startAgent || !dataDir) return;
    setLogs([]);
    setIsStarting(true);
    try {
      await api.startAgent({
        clientId,
        dataDir,
        serverAddr: getOrchestratorAddr(),
      });
    } catch (err) {
      setLogs((prev) => [
        ...prev,
        { ts: new Date().toISOString(), line: `Error: ${err}` },
      ]);
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    const api = window.electronAPI;
    if (!api?.stopAgent) return;
    setIsStopping(true);
    try {
      await api.stopAgent();
    } catch (err) {
      setLogs((prev) => [
        ...prev,
        { ts: new Date().toISOString(), line: `Error: ${err}` },
      ]);
      setIsStopping(false);
    }
  };

  const hasElectronAPI = typeof window !== "undefined" && !!window.electronAPI;
  const isAgentBusy = isStarting || isStopping || localProcessRunning;
  const statusInfo =
    agentStatus === "training"
      ? { color: "bg-primary", label: "Training" }
      : agentStatus === "idle" || agentStatus === "connected"
        ? { color: "bg-primary/70", label: "Connected" }
        : { color: "bg-destructive", label: "Disconnected" };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Client Dashboard
        </h2>
        <p className="text-muted-foreground">
          Control your edge agent and monitor participation
        </p>
      </div>

      <ReleasedModels />

      <Card>
        <CardHeader>
          <CardTitle>Agent</CardTitle>
          <CardDescription>
            Choose a folder on this computer that contains your prepared data
            files, then start the agent to join training.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3">
              <div
                className={`h-3 w-3 rounded-full ${statusInfo.color} animate-pulse`}
                aria-hidden
              />
              <span className="font-medium">{statusInfo.label}</span>
              <span className="text-sm text-muted-foreground">
                Client #{clientId || "N/A"}
              </span>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleStart}
                disabled={!dataDir || isAgentBusy || !hasElectronAPI}
              >
                {isStarting ? "Starting…" : "Start Agent"}
              </Button>
              <Button
                variant="destructive"
                onClick={handleStop}
                disabled={isStopping || !localProcessRunning}
              >
                {isStopping ? "Stopping…" : "Stop Agent"}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="data-dir">Data directory</Label>
            <div className="flex gap-2">
              <Input
                id="data-dir"
                value={dataDir}
                onChange={(e) => !isAgentBusy && setDataDir(e.target.value)}
                placeholder="Select folder containing patients.csv, vitals.csv, and events.csv"
                readOnly={!hasElectronAPI || isAgentBusy}
              />
              <Button
                variant="outline"
                onClick={handlePickDir}
                disabled={!hasElectronAPI || isAgentBusy}
              >
                Browse
              </Button>
            </div>
          </div>

          <Tabs defaultValue="agent-logs">
            <TabsList>
              <TabsTrigger value="agent-logs">Agent Logs</TabsTrigger>
              <TabsTrigger value="audit">Audit Logs</TabsTrigger>
            </TabsList>
            <TabsContent value="agent-logs">
              <LogViewer
                events={[...logs]
                  .reverse()
                  .filter((entry) => {
                    const msgWithoutPrefix = entry.line.replace(/^\[[^\]]+\]\s*/, "");
                    const isNoisy =
                      msgWithoutPrefix.includes("Secure RNG turned off") ||
                      msgWithoutPrefix.includes("Optimal order is the largest alpha") ||
                      msgWithoutPrefix.includes("Full backward hook is firing") ||
                      msgWithoutPrefix.includes("does not fit in a single ciphertext") ||
                      msgWithoutPrefix.includes("operations are disabled in this setup") ||
                      msgWithoutPrefix.includes("increasing the poly_modulus parameter") ||
                      msgWithoutPrefix.includes("recvmsg encountered uncommon error: Message too long") ||
                      msgWithoutPrefix.includes("InitializeLog() is called") ||
                      msgWithoutPrefix.includes("DPLSTMCell") ||
                      msgWithoutPrefix.includes("RNNLinear") ||
                      msgWithoutPrefix.includes("DPLSTM") ||
                      /^\s*[)]\s*$/.test(msgWithoutPrefix) ||
                      /^\s*[(].*[)]\s*$/.test(msgWithoutPrefix);
                    return !isNoisy;
                  })
                  .map((entry) => {
                    const match = entry.line.match(/^\[([^\]]+)\]\s*(.*)$/);
                    const type = match ? match[1] : "log";
                    const message = match ? match[2].trim() : entry.line;
                    return {
                      ts: entry.ts,
                      type,
                      message: message || undefined,
                    } satisfies LogEvent;
                  })}
                emptyMessage="No logs yet. Start the agent to see output."
              />
            </TabsContent>
            <TabsContent value="audit">
              <LogViewer
                events={auditLogs.map((log) => ({
                  ts: log.created_at,
                  type: log.event_type,
                  jobId: log.job_id ?? undefined,
                  clientId: log.client_id ?? undefined,
                  details:
                    Object.keys(log.details ?? {}).length > 0
                      ? (log.details as Record<string, unknown>)
                      : undefined,
                } satisfies LogEvent))}
                emptyMessage="No audit events yet. Participate in a training round to see events."
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
