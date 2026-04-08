"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { JobDetail } from "@/components/dashboard/server/job-detail";
import { useJobs } from "@/hooks/useJobs";
import { useRounds } from "@/hooks/useRounds";
import { useAuditLogs } from "@/hooks/useAuditLogs";
import { useFleet } from "@/hooks/useFleet";
import { useClients } from "@/hooks/useClients";
import type { Job } from "@/hooks/useJobs";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

export default function JobDetailPage() {
  const params = useParams();
  const jobIdParam = params.jobId;
  const jobId = useMemo(() => {
    const raw = Array.isArray(jobIdParam) ? jobIdParam[0] : jobIdParam;
    const n = Number.parseInt(String(raw), 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [jobIdParam]);

  const { jobs, fetchJobs, initialLoadComplete } = useJobs();
  const { rounds } = useRounds(jobId);
  const { auditLogs } = useAuditLogs(jobId);
  const { fleet } = useFleet();
  const { clients } = useClients();

  const [token, setToken] = useState<string | null>(null);
  const [startingJobId, setStartingJobId] = useState<number | null>(null);
  const [releasingJobId, setReleasingJobId] = useState<number | null>(null);

  const job = jobId != null ? jobs.find((j) => j.id === jobId) : undefined;

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setToken(session?.access_token ?? null);
    });
  }, []);

  const handleStartJob = useCallback(
    async (id: number) => {
      setStartingJobId(id);
      try {
        await api.startJob(id, token);
        await fetchJobs();
        toast.success("Job started");
      } catch (err) {
        console.error(err);
        toast.error(err instanceof Error ? err.message : "Failed to start job");
      } finally {
        setStartingJobId(null);
      }
    },
    [token, fetchJobs]
  );

  const handleStopJob = useCallback(async () => {
    if (!job || job.status !== "running") return;
    try {
      await api.stopJob(job.id, token);
      await fetchJobs();
      toast.success("Job stopped");
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : "Failed to stop job");
    }
  }, [job, token, fetchJobs]);

  const handleReleaseModel = useCallback(
    async (j: Job) => {
      setReleasingJobId(j.id);
      try {
        await api.releaseModel(j.id, token);
        await fetchJobs();
        toast.success("Model released for participating clients");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to release model");
      } finally {
        setReleasingJobId(null);
      }
    },
    [token, fetchJobs]
  );

  const handleDownloadModel = useCallback(
    async (j: Job, kind: "pt" | "onnx") => {
      try {
        const { url } = await api.getModelDownloadUrl(j.id, kind, token);
        const a = document.createElement("a");
        a.href = url;
        a.download =
          kind === "pt" ? `job-${j.id}-model.pt` : `job-${j.id}-model.onnx`;
        a.target = "_blank";
        document.body.appendChild(a);
        a.click();
        a.remove();
        toast.success("Model downloaded");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to download model");
      }
    },
    [token]
  );

  if (jobId === null) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground">Invalid job ID.</p>
        <Button variant="outline" asChild>
          <Link href="/dashboard/server">Back to dashboard</Link>
        </Button>
      </div>
    );
  }

  if (!initialLoadComplete) {
    return (
      <div className="flex min-h-[240px] items-center justify-center">
        <p className="text-muted-foreground text-sm">Loading job…</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground">Job not found.</p>
        <Button variant="outline" asChild>
          <Link href="/dashboard/server">Back to dashboard</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" className="gap-1.5 px-2" asChild>
          <Link href="/dashboard/server">
            <ArrowLeft className="size-4" aria-hidden />
            Dashboard
          </Link>
        </Button>
      </div>
      <JobDetail
        job={job}
        rounds={rounds}
        auditLogs={auditLogs}
        fleet={fleet}
        clients={clients}
        onStartJob={handleStartJob}
        onStopJob={handleStopJob}
        onDownloadModel={handleDownloadModel}
        onReleaseModel={handleReleaseModel}
        startingJobId={startingJobId}
        releasingJobId={releasingJobId}
        token={token}
      />
    </div>
  );
}
