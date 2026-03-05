"use client";

import { useState, useCallback, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export interface FleetClient {
  client_id: number;
  num_samples: number;
  status: string;
}

export function useFleet() {
  const [fleet, setFleet] = useState<FleetClient[]>([]);

  const fetchFleet = useCallback(async () => {
    const { data } = await supabase
      .from("client_registry")
      .select("client_id, num_samples, status")
      .order("client_id", { ascending: true });
    setFleet((data ?? []).map((c) => ({
      client_id: c.client_id,
      num_samples: c.num_samples ?? 0,
      status: c.status ?? "idle",
    })));
  }, []);

  useEffect(() => {
    fetchFleet();
    const interval = setInterval(fetchFleet, 5000);
    return () => clearInterval(interval);
  }, [fetchFleet]);

  useEffect(() => {
    const channel = supabase
      .channel("client_registry")
      .on("postgres_changes", { event: "*", schema: "public", table: "client_registry" }, fetchFleet)
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [fetchFleet]);

  return { fleet };
}
