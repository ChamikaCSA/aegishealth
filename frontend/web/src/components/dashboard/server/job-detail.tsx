"use client";

import { useMemo } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { LogViewer } from "@/components/shared/log-viewer";
import { FleetTable } from "@/components/dashboard/server/fleet-table";
import type { Job } from "@/hooks/useJobs";
import type { RoundMetric } from "@/hooks/useRounds";
import type { AuditLogRow } from "@/hooks/useAuditLogs";
import type { FleetClient } from "@/hooks/useFleet";
import type { ClientRow } from "@/hooks/useClients";
import type { LogEvent } from "@/types/logging";
import { Download, ChevronDown, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface JobDetailProps {
  job: Job;
  rounds: RoundMetric[];
  auditLogs: AuditLogRow[];
  fleet: FleetClient[];
  clients: ClientRow[];
  onStartJob: (id: number) => void;
  onStopJob: () => void;
  onDownloadModel: (job: Job, kind: "pt" | "onnx") => void;
  onReleaseModel?: (job: Job) => void;
  startingJobId: number | null;
  releasingJobId?: number | null;
  token: string | null;
}

export function JobDetail({
  job,
  rounds,
  auditLogs,
  fleet,
  clients,
  onStartJob,
  onStopJob,
  onDownloadModel,
  onReleaseModel,
  startingJobId,
  releasingJobId = null,
}: JobDetailProps) {
  const metrics = rounds.map((r) => ({
    round: r.round_number,
    avg_loss: r.global_loss,
    avg_accuracy: r.global_accuracy,
    avg_f1: r.global_f1_score,
    avg_auc_roc: r.global_auc_roc,
    participating_clients: r.participating_clients,
    aggregation_time_ms: r.aggregation_time_ms,
    cumulative_epsilon: r.cumulative_epsilon,
  }));

  const hasEpsilon = metrics.some(
    (m) => m.cumulative_epsilon != null && m.cumulative_epsilon > 0,
  );

  const fleetClientNames = useMemo(() => {
    const m: Record<number, string> = {};
    for (const c of clients) {
      m[c.id] = c.name;
    }
    return m;
  }, [clients]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Job #{job.id}</CardTitle>
            <CardDescription>
              {job.current_round}/{job.total_rounds} rounds · Acc:{" "}
              {(job.best_accuracy * 100).toFixed(1)}% · F1:{" "}
              {(job.best_f1_score * 100).toFixed(1)}% · AUC:{" "}
              {(job.best_auc_roc * 100).toFixed(1)}% · {fleet.length} Connected Clients
            </CardDescription>
          </div>
          <div className="flex flex-col items-end gap-2">
            {(job.model_path_pt || job.model_path_onnx) && (
              <>
                {job.status === "completed" &&
                  onReleaseModel &&
                  (job.model_released_at ? (
                    <Badge variant="secondary">Released</Badge>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onReleaseModel(job)}
                      disabled={releasingJobId !== null}
                    >
                      <Send className="size-4" aria-hidden />
                      {releasingJobId === job.id ? "Releasing…" : "Release model"}
                    </Button>
                  ))}
                <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5">
                    <Download className="size-4" aria-hidden />
                    Download model
                    <ChevronDown className="size-4 opacity-50" aria-hidden />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {job.model_path_pt && (
                    <DropdownMenuItem
                      onClick={() => onDownloadModel(job, "pt")}
                    >
                      PyTorch (.pt)
                    </DropdownMenuItem>
                  )}
                  {job.model_path_onnx && (
                    <DropdownMenuItem
                      onClick={() => onDownloadModel(job, "onnx")}
                    >
                      ONNX (.onnx)
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              </>
            )}
            <div className="flex gap-2">
              {job.status === "pending" && (
                <Button
                  onClick={() => onStartJob(job.id)}
                  disabled={startingJobId !== null}
                >
                  {startingJobId === job.id ? "Starting..." : "Start"}
                </Button>
              )}
              {job.status === "running" && (
                <Button variant="destructive" onClick={onStopJob}>
                  Stop Training
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Global Loss</CardTitle>
          </CardHeader>
          <CardContent className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg_loss"
                  stroke="var(--chart-1)"
                  strokeWidth={2}
                  dot={false}
                  name="Loss"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Global Accuracy</CardTitle>
          </CardHeader>
          <CardContent className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg_accuracy"
                  stroke="var(--chart-3)"
                  strokeWidth={2}
                  dot={false}
                  name="Accuracy"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>F1 Score</CardTitle>
          </CardHeader>
          <CardContent className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg_f1"
                  stroke="var(--chart-2)"
                  strokeWidth={2}
                  dot={false}
                  name="F1"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>AUC-ROC</CardTitle>
          </CardHeader>
          <CardContent className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg_auc_roc"
                  stroke="var(--chart-4)"
                  strokeWidth={2}
                  dot={false}
                  name="AUC-ROC"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {hasEpsilon && (
        <Card>
          <CardHeader>
            <CardTitle>Cumulative Privacy Budget (ε)</CardTitle>
            <CardDescription>
              Running total of the privacy budget used as training progresses
            </CardDescription>
          </CardHeader>
          <CardContent className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="cumulative_epsilon"
                  stroke="var(--chart-5)"
                  strokeWidth={2}
                  dot={false}
                  name="Cumulative ε"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <FleetTable fleet={fleet} clientNames={fleetClientNames} />

      <Card>
        <CardHeader>
          <CardTitle>Audit Logs</CardTitle>
          <CardDescription>Events for job #{job.id}</CardDescription>
        </CardHeader>
        <CardContent>
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
            emptyMessage="No audit events for this job yet."
          />
        </CardContent>
      </Card>
    </div>
  );
}
