"use client";

import { useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Copy, Check } from "lucide-react";
import type { LogEvent } from "@/types/logging";

function formatRelativeTime(ts: string): string {
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  return date.toLocaleString();
}

interface LogViewerProps {
  events: LogEvent[];
  emptyMessage: string;
}

export function LogViewer({ events, emptyMessage }: LogViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const text = events
      .map((e) => {
        const parts = [
          new Date(e.ts).toISOString(),
          e.type,
          e.jobId != null ? `job=${e.jobId}` : "",
          "clientId" in e && (e as { clientId?: number }).clientId != null
            ? `client=${(e as { clientId: number }).clientId}`
            : "",
          e.message ?? "",
          e.details ? JSON.stringify(e.details) : "",
        ].filter(Boolean);
        return parts.join(" ");
      })
      .join("\n");
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [events]);

  return (
    <div className="rounded-lg border bg-muted/50">
      {events.length > 0 && (
        <div className="flex justify-end border-b px-2 py-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 text-xs"
            onClick={handleCopy}
          >
            {copied ? (
              <Check className="size-3" aria-hidden />
            ) : (
              <Copy className="size-3" aria-hidden />
            )}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      )}
      <div className="max-h-[300px] overflow-auto p-4 font-mono text-xs">
        {events.length === 0 ? (
          <p className="text-muted-foreground">{emptyMessage}</p>
        ) : (
          events.map((event, i) => (
            <div
              key={i}
              className="mb-2"
              title={new Date(event.ts).toLocaleString()}
            >
              <span className="text-muted-foreground">
                [{formatRelativeTime(event.ts)}]
              </span>{" "}
              <Badge variant="outline" className="text-xs">
                {event.type}
              </Badge>
              {event.jobId != null && (
                <>
                  {" "}
                  <span className="text-muted-foreground">job={event.jobId}</span>
                </>
              )}
              {"clientId" in event && (event as { clientId?: number }).clientId != null && (
                <>
                  {" "}
                  <span className="text-muted-foreground">
                    client={String((event as { clientId: number }).clientId)}
                  </span>
                </>
              )}
              {event.message && (
                <>
                  {" "}
                  <span className="text-muted-foreground whitespace-pre-wrap">
                    {event.message}
                  </span>
                </>
              )}
              {event.details && Object.keys(event.details).length > 0 && (
                <>
                  {" "}
                  <span className="text-muted-foreground">
                    {JSON.stringify(event.details)}
                  </span>
                </>
              )}
              {i < events.length - 1 && <Separator className="mt-2" />}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
