"use client";

import { useState, useCallback, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export interface RoundMetric {
  round_number: number;
  global_loss: number | null;
  global_accuracy: number | null;
  global_f1_score: number | null;
  global_auc_roc: number | null;
  participating_clients: number | null;
  aggregation_time_ms: number | null;
  cumulative_epsilon: number | null;
}

export function useRounds(jobId: number | null) {
  const [rounds, setRounds] = useState<RoundMetric[]>([]);

  const fetchRounds = useCallback(async (id: number) => {
    const { data } = await supabase
      .from("training_rounds")
      .select("round_number, global_loss, global_accuracy, global_f1_score, global_auc_roc, participating_clients, aggregation_time_ms, cumulative_epsilon")
      .eq("job_id", id)
      .order("round_number", { ascending: true });
    if (data) setRounds(data as RoundMetric[]);
  }, []);

  useEffect(() => {
    if (jobId) fetchRounds(jobId);
    else setRounds([]);
  }, [jobId, fetchRounds]);

  useEffect(() => {
    if (!jobId) return;
    const channel = supabase
      .channel(`rounds_${jobId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "training_rounds" }, () => fetchRounds(jobId))
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [jobId, fetchRounds]);

  return { rounds };
}
