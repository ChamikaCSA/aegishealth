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
  }, [fetchFleet]);

  useEffect(() => {
    const channel = supabase
      .channel("client_registry_realtime")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "client_registry" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            const newItem: FleetClient = {
              client_id: payload.new.client_id,
              num_samples: payload.new.num_samples ?? 0,
              status: payload.new.status ?? "idle",
            };
            setFleet((prev) => {
              if (prev.find((c) => c.client_id === newItem.client_id)) return prev;
              return [...prev, newItem].sort((a, b) => a.client_id - b.client_id);
            });
          } else if (payload.eventType === "UPDATE") {
            setFleet((prev) =>
              prev.map((c) =>
                c.client_id === payload.new.client_id
                  ? {
                      ...c,
                      status: payload.new.status ?? c.status,
                      num_samples: payload.new.num_samples ?? c.num_samples,
                    }
                  : c
              )
            );
          } else if (payload.eventType === "DELETE") {
            setFleet((prev) =>
              prev.filter((c) => c.client_id === payload.old.client_id)
            );
          }
        }
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, []);

  return { fleet };
}
