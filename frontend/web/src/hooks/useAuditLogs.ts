"use client";

import { useState, useCallback, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export interface AuditLogRow {
  event_type: string;
  job_id: number | null;
  client_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

export function useAuditLogs(jobId: number | null) {
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);

  const fetchAuditLogs = useCallback(async () => {
    let query = supabase
      .from("audit_logs")
      .select("event_type, job_id, client_id, details, created_at")
      .order("created_at", { ascending: false })
      .limit(100);
    if (jobId) query = query.eq("job_id", jobId);
    const { data } = await query;
    setAuditLogs((data as AuditLogRow[]) ?? []);
  }, [jobId]);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  useEffect(() => {
    const channel = supabase
      .channel("audit_logs_realtime")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "audit_logs" },
        (payload) => {
          const newLog = payload.new as AuditLogRow;
          if (jobId && newLog.job_id !== jobId) return;

          setAuditLogs((prev) => {
            if (prev.find((l) => l.created_at === newLog.created_at && l.event_type === newLog.event_type)) return prev;
            return [newLog, ...prev].slice(0, 100);
          });
        }
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [jobId]);

  return { auditLogs };
}
