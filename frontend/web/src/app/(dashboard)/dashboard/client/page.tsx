"use client";

import { useState, useEffect } from "react";
import { AgentControl } from "@/components/dashboard/client/agent-control";
import { DownloadPrompt } from "@/components/dashboard/client/download-prompt";

export default function ClientDashboardPage() {
  const [isElectron, setIsElectron] = useState<boolean | null>(null);

  useEffect(() => {
    setIsElectron(typeof window !== "undefined" && !!window.electronAPI);
  }, []);

  if (isElectron === null) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return isElectron ? <AgentControl /> : <DownloadPrompt />;
}
