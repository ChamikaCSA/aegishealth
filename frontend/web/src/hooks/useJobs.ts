"use client";

import { useState, useCallback, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export interface Job {
  id: number;
  status: string;
  config: Record<string, unknown>;
  current_round: number;
  total_rounds: number;
  best_accuracy: number;
  best_f1_score: number;
  best_auc_roc: number;
  created_at?: string;
  model_path_pt?: string | null;
  model_path_onnx?: string | null;
  model_released_at?: string | null;
}

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await supabase
        .from("training_jobs")
        .select("id, status, config, current_round, total_rounds, best_accuracy, best_f1_score, best_auc_roc, created_at, model_path_pt, model_path_onnx, model_released_at")
        .order("created_at", { ascending: false });
      if (data) {
        setJobs(data.map((j) => ({
          id: j.id,
          status: j.status,
          config: (j.config as Record<string, unknown>) ?? {},
          current_round: j.current_round ?? 0,
          total_rounds: j.total_rounds ?? 50,
          best_accuracy: j.best_accuracy ?? 0,
          best_f1_score: (j as { best_f1_score?: number }).best_f1_score ?? 0,
          best_auc_roc: (j as { best_auc_roc?: number }).best_auc_roc ?? 0,
          created_at: j.created_at,
          model_path_pt: (j as { model_path_pt?: string | null }).model_path_pt ?? null,
          model_path_onnx: (j as { model_path_onnx?: string | null }).model_path_onnx ?? null,
          model_released_at: (j as { model_released_at?: string | null }).model_released_at ?? null,
        })));
      } else {
        setJobs([]);
      }
    } finally {
      setInitialLoadComplete(true);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    const channel = supabase
      .channel("training_jobs")
      .on("postgres_changes", { event: "*", schema: "public", table: "training_jobs" }, fetchJobs)
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [fetchJobs]);

  return { jobs, fetchJobs, initialLoadComplete };
}
