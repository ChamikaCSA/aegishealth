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
      .channel("training_jobs_realtime")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "training_jobs" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            const newJob: Job = {
              id: payload.new.id,
              status: payload.new.status,
              config: (payload.new.config as Record<string, unknown>) ?? {},
              current_round: payload.new.current_round ?? 0,
              total_rounds: payload.new.total_rounds ?? 50,
              best_accuracy: payload.new.best_accuracy ?? 0,
              best_f1_score: payload.new.best_f1_score ?? 0,
              best_auc_roc: payload.new.best_auc_roc ?? 0,
              created_at: payload.new.created_at,
            };
            setJobs((prev) => [newJob, ...prev]);
          } else if (payload.eventType === "UPDATE") {
            setJobs((prev) =>
              prev.map((j) =>
                j.id === payload.new.id
                  ? {
                      ...j,
                      status: payload.new.status ?? j.status,
                      current_round: payload.new.current_round ?? j.current_round,
                      best_accuracy: payload.new.best_accuracy ?? j.best_accuracy,
                      best_f1_score: payload.new.best_f1_score ?? j.best_f1_score,
                      best_auc_roc: payload.new.best_auc_roc ?? j.best_auc_roc,
                      model_path_pt: payload.new.model_path_pt ?? j.model_path_pt,
                      model_path_onnx: payload.new.model_path_onnx ?? j.model_path_onnx,
                      model_released_at: payload.new.model_released_at ?? j.model_released_at,
                    }
                  : j
              )
            );
          } else if (payload.eventType === "DELETE") {
            setJobs((prev) => prev.filter((j) => j.id === payload.old.id));
          }
        }
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, []);

  return { jobs, fetchJobs, initialLoadComplete };
}
