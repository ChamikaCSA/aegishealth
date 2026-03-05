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
      .channel("audit_logs")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "audit_logs" }, fetchAuditLogs)
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [fetchAuditLogs]);

  return { auditLogs };
}
