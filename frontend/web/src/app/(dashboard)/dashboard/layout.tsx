"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { useAuth } from "@/lib/auth";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { loading, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      if (user.role === "server" && pathname.startsWith("/dashboard/client")) {
        router.replace("/dashboard/server");
      } else if (user.role === "client" && pathname.startsWith("/dashboard/server")) {
        router.replace("/dashboard/client");
      }
    }
  }, [loading, user, pathname, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="mt-4 text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <main className="flex-1">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <div className="space-y-6">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
