"use client";

import { usePathname } from "next/navigation";

function getBreadcrumb(pathname: string) {
  if (pathname.includes("/server")) {
    return "Orchestration Dashboard";
  }
  if (pathname.includes("/client")) {
    return "Client Dashboard";
  }
  return "Dashboard";
}

export function Header() {
  const pathname = usePathname();
  const breadcrumb = getBreadcrumb(pathname);

  return (
    <header className="sticky top-0 z-40 shrink-0 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60">
      <div className="flex h-14 items-center px-4 sm:px-6 lg:px-8">
        <h1 className="text-lg font-semibold text-foreground">
          {breadcrumb}
        </h1>
      </div>
    </header>
  );
}
