"use client";

import { useState, useCallback, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export interface ClientRow {
  id: number;
  name: string;
  region: string | null;
  status: string;
  user_id: string | null;
}

export function useClients() {
  const [clients, setClients] = useState<ClientRow[]>([]);

  const fetchClients = useCallback(async () => {
    const { data } = await supabase
      .from("clients")
      .select("id, name, region, status, user_id")
      .order("id", { ascending: true });
    if (data) setClients(data as ClientRow[]);
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  useEffect(() => {
    const channel = supabase
      .channel("clients")
      .on("postgres_changes", { event: "*", schema: "public", table: "clients" }, fetchClients)
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [fetchClients]);

  return { clients, fetchClients };
}
