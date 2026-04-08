"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Copy, Check, GripHorizontal } from "lucide-react";
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
  const [height, setHeight] = useState(300);
  const isResizing = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      setHeight((prev) => {
        const newHeight = prev + e.movementY;
        return Math.max(150, Math.min(1200, newHeight));
      });
    };

    const handleMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = "default";
      document.body.style.userSelect = "auto";
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

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
    <div className="rounded-lg border bg-muted/50 flex flex-col overflow-hidden">
      {events.length > 0 && (
        <div className="flex justify-end border-b px-2 py-1 bg-background/50">
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
      <div 
        className="overflow-auto p-4 font-mono text-xs transition-colors"
        style={{ height: `${height}px` }}
      >
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
              <Badge
                variant={
                  event.type === "error" || event.type === "agent_error" || event.type.includes("failed")
                    ? "destructive"
                    : event.type === "warning" || event.type.includes("stopped")
                      ? "secondary"
                      : event.type === "info" || event.type.includes("completed") || event.type.includes("registered") || event.type.includes("released")
                        ? "default"
                        : "outline"
                }
                className={`text-[10px] px-1.5 py-0 h-4 uppercase tracking-tight ${
                  event.type === "warning" || event.type.includes("stopped")
                    ? "bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800"
                    : ""
                } ${
                  event.type === "info" || event.type.includes("completed") || event.type.includes("registered") || event.type.includes("released")
                    ? "bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800"
                    : ""
                }`}
              >
                {event.type.replace(/_/g, " ")}
              </Badge>
              {event.jobId != null && (
                <>
                  {" "}
                  <span className="text-muted-foreground whitespace-nowrap">job={event.jobId}</span>
                </>
              )}
              {"clientId" in event && (event as { clientId?: number }).clientId != null && (
                <>
                  {" "}
                  <span className="text-muted-foreground whitespace-nowrap">
                    client={String((event as { clientId: number }).clientId)}
                  </span>
                </>
              )}
              {(event.message || event.details) && (
                <div className="mt-1 pl-4 border-l-2 border-muted-foreground/10 py-0.5">
                  {event.message && (
                    <div className="text-muted-foreground whitespace-pre-wrap block">
                      {(() => {
                        let displayMsg = event.message.replace(
                          /^(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\s+\w+\s+)?\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d{3}\s+\[\w+\]\s+.*?:\s*/,
                          ""
                        );

                        if (displayMsg.startsWith("gRPC ")) {
                          const parts = displayMsg.split(" | ");
                          const method = parts[0].replace("gRPC ", "");
                          const reqPart = parts.find(p => p.startsWith("Req: "))?.replace("Req: ", "");
                          const resPart = parts.find(p => p.startsWith("Res: "))?.replace("Res: ", "");
                          const errPart = parts.find(p => p.startsWith("ERROR: ") || p.startsWith("EXCEPTION: "));

                          const renderJson = (jsonStr: string, isRes: boolean) => {
                            if (!jsonStr) return null;
                            return (
                              <div className={`bg-background/40 rounded px-2 py-1 mt-1 border overflow-x-auto ${isRes ? "border-emerald-500/20" : "border-primary/10"}`}>
                                {jsonStr.trim().split(/("[^"]+":)/g).map((token, tk) => {
                                  if (token.startsWith('"') && token.endsWith('":')) {
                                    return <span key={tk} className={isRes ? "text-emerald-500 font-medium" : "text-primary font-medium"}>{token}</span>;
                                  }
                                  if (token.includes('chars)')) {
                                     return <span key={tk} className="text-muted-foreground italic">{token}</span>;
                                  }
                                  return <span key={tk} className="text-foreground">{token}</span>;
                                })}
                              </div>
                            );
                          };

                          return (
                            <div className="space-y-2 py-1">
                              <div className="flex items-center gap-2">
                                <span className="text-primary font-bold text-[10px] uppercase tracking-widest bg-primary/10 px-1.5 rounded">gRPC</span>
                                <span className="text-foreground font-semibold">{method}</span>
                              </div>
                              
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {reqPart && (
                                  <div className="space-y-0.5">
                                    <span className="text-[9px] uppercase font-bold text-muted-foreground ml-1">Request</span>
                                    {renderJson(reqPart, false)}
                                  </div>
                                )}
                                {resPart && (
                                  <div className="space-y-0.5">
                                    <span className="text-[9px] uppercase font-bold text-emerald-600/70 ml-1">Response</span>
                                    {renderJson(resPart, true)}
                                  </div>
                                )}
                              </div>

                              {errPart && (
                                <div className="bg-destructive/10 border border-destructive/20 rounded px-2 py-1.5 text-destructive font-medium text-[11px]">
                                   {errPart}
                                </div>
                              )}
                            </div>
                          );
                        }

                        return displayMsg.split(/([a-z_]+=[0-9.]+)/g).map((part, k) => {
                          if (part.includes("=")) {
                            const [label, val] = part.split("=");
                            return (
                              <span key={k} className="text-primary font-medium">
                                {label}=<span className="text-foreground">{val}</span>
                              </span>
                            );
                          }
                          return part;
                        });
                      })()}
                    </div>
                  )}
                  {event.details && Object.keys(event.details).length > 0 && (
                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
                      {Object.entries(event.details).map(([key, val]) => (
                        <span key={key} className="text-xs text-muted-foreground font-medium">
                          {key}=
                          <span className="text-foreground">
                            {typeof val === "object" ? JSON.stringify(val) : String(val)}
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {i < events.length - 1 && <Separator className="mt-2" />}
            </div>
          ))
        )}
      </div>
      <div 
        onMouseDown={(e) => {
          isResizing.current = true;
          document.body.style.cursor = "row-resize";
          document.body.style.userSelect = "none";
        }}
        className="h-3 w-full cursor-row-resize bg-muted/80 hover:bg-primary/20 flex items-center justify-center border-t transition-colors group"
        title="Drag to resize logs"
      >
        <GripHorizontal className="size-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
      </div>
    </div>
  );
}
