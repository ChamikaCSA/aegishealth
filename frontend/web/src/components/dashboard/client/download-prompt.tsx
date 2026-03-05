"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, Monitor, FileCheck, Activity, Shield } from "lucide-react";
import { ReleasedModels } from "@/components/dashboard/client/released-models";

const GITHUB_REPO = process.env.NEXT_PUBLIC_DESKTOP_APP_GITHUB_REPO ?? "";

function getDownloadAssetForPlatform(): string {
  if (typeof navigator === "undefined") return "darwin-arm64";
  const ua = navigator.userAgent.toLowerCase();
  const isMac = ua.includes("mac");
  const isWin = ua.includes("win");
  const isLinux = ua.includes("linux");
  const isArm = navigator.userAgent.includes("aarch64") || ua.includes("arm64");
  if (isMac) return isArm ? "darwin-arm64" : "darwin-x64";
  if (isWin) return "win32-x64";
  if (isLinux) return "linux-x64";
  return "darwin-arm64";
}

export function DownloadPrompt() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    if (!GITHUB_REPO) {
      setError(
        "Desktop app download is not configured. Please contact your administrator."
      );
      return;
    }
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(
        `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`
      );
      if (!res.ok) {
        setError("No release found. Please try again later.");
        return;
      }
      const data = await res.json();
      const platform = getDownloadAssetForPlatform();
      const asset =
        data.assets?.find(
          (a: { name: string }) =>
            a.name.endsWith(".zip") && a.name.includes(platform)
        ) ??
        data.assets?.find(
          (a: { name: string }) =>
            a.name.endsWith(".zip") || a.name.endsWith(".exe")
        ) ??
        data.assets?.[0];
      if (!asset?.browser_download_url) {
        setError("No download available for your platform.");
        return;
      }
      const a = document.createElement("a");
      a.href = asset.browser_download_url;
      a.download = asset.name;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Client Dashboard
        </h2>
        <p className="text-muted-foreground">
          Download the desktop app to participate in federated training
        </p>
      </div>

      <ReleasedModels />

      <Card>
        <CardHeader>
          <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10">
            <Monitor className="size-6 text-primary" aria-hidden />
          </div>
          <CardTitle className="pt-4">Desktop App</CardTitle>
          <CardDescription>
            Run the edge agent locally to participate in federated training.
            Your data stays on your machine.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="space-y-2.5 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <Shield className="size-4 shrink-0 text-primary" aria-hidden />
              Data never leaves your device
            </li>
            <li className="flex items-center gap-2">
              <Activity className="size-4 shrink-0 text-primary" aria-hidden />
              Start and stop the agent from the app
            </li>
            <li className="flex items-center gap-2">
              <FileCheck className="size-4 shrink-0 text-primary" aria-hidden />
              Real-time logs and compliance view
            </li>
          </ul>

          <Button
            onClick={handleDownload}
            disabled={downloading}
            className="w-full"
            size="lg"
          >
            <Download className="size-4" aria-hidden />
            {downloading ? "Preparing download…" : "Download Desktop App"}
          </Button>

          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}

          {GITHUB_REPO && (
            <p className="text-xs text-muted-foreground">
              Install the app, then sign in with your client credentials to
              connect your agent.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
