"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusVariant = "running" | "active" | "training" | "pending" | "idle" | "connected" | "completed" | "failed" | "disconnected" | "stopped";

const statusConfig: Record<StatusVariant, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }> = {
  running: { variant: "default", className: "bg-primary text-primary-foreground" },
  active: { variant: "default", className: "bg-primary text-primary-foreground" },
  training: { variant: "default", className: "bg-primary text-primary-foreground" },
  pending: { variant: "outline" },
  idle: { variant: "secondary" },
  connected: { variant: "secondary" },
  completed: { variant: "secondary" },
  failed: { variant: "destructive" },
  disconnected: { variant: "destructive" },
  stopped: { variant: "outline" },
};

function normalizeStatus(status: string): StatusVariant {
  const s = status?.toLowerCase() ?? "";
  if (["running", "active", "training"].includes(s)) return "running";
  if (["pending", "idle", "connected"].includes(s)) return s as StatusVariant;
  if (["completed", "failed", "disconnected", "stopped"].includes(s)) return s as StatusVariant;
  if (s === "default" || s === "idle") return "idle";
  return "pending";
}

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  const config = statusConfig[normalized] ?? statusConfig.pending;

  return (
    <Badge
      variant={config.variant}
      className={cn(config.className, className)}
    >
      {status}
    </Badge>
  );
}
