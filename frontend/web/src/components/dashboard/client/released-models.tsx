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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Download, ChevronDown, Package } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { toast } from "sonner";

interface ReleasedJob {
  id: number;
  best_accuracy: number;
  best_f1_score: number;
  model_path_pt: string | null;
  model_path_onnx: string | null;
  model_released_at: string | null;
}

export function ReleasedModels() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<ReleasedJob[]>([]);
  const [token, setToken] = useState<string | null>(null);

  const fetchReleased = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api.getReleasedModels(token);
      setJobs(data);
    } catch {
      setJobs([]);
    }
  }, [token]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setToken(session?.access_token ?? null);
    });
  }, []);

  useEffect(() => {
    fetchReleased();
  }, [fetchReleased]);

  useEffect(() => {
    const channel = supabase
      .channel("released_models_realtime")
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "training_jobs",
        },
        (payload) => {
          if (payload.new?.model_released_at) void fetchReleased();
        }
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [fetchReleased]);

  const handleDownload = async (jobId: number, kind: "pt" | "onnx") => {
    try {
      const { url } = await api.getModelDownloadUrl(jobId, kind, token);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        kind === "pt" ? `job-${jobId}-model.pt` : `job-${jobId}-model.onnx`;
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success("Model downloaded");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to download");
    }
  };

  if (!user?.client_id || jobs.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="size-5 text-primary" aria-hidden />
          Released Models
        </CardTitle>
        <CardDescription>
          Models from jobs you participated in, released by the server
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="flex items-center justify-between rounded-lg border px-4 py-3"
            >
              <div>
                <span className="font-medium">Job #{job.id}</span>
                <span className="ml-2 text-sm text-muted-foreground">
                  Best: {(job.best_accuracy * 100).toFixed(1)}% · F1:{" "}
                  {(job.best_f1_score * 100).toFixed(1)}%
                </span>
              </div>
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
                      onClick={() => handleDownload(job.id, "pt")}
                    >
                      PyTorch (.pt)
                    </DropdownMenuItem>
                  )}
                  {job.model_path_onnx && (
                    <DropdownMenuItem
                      onClick={() => handleDownload(job.id, "onnx")}
                    >
                      ONNX (.onnx)
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
