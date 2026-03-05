"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Activity, Shield, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

const serverNavItems = [
  { href: "/dashboard/server", label: "Dashboard", icon: LayoutDashboard },
];

const clientNavItems = [
  { href: "/dashboard/client", label: "Agent", icon: Activity },
];

function NavLinks({
  items,
  onLinkClick,
}: {
  items: typeof serverNavItems;
  onLinkClick?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1">
      {items.map((item) => {
        const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onLinkClick}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <item.icon className="size-4 shrink-0" aria-hidden />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarContent({ onLinkClick }: { onLinkClick?: () => void }) {
  const { user, logout } = useAuth();
  const isServer = user?.role === "server";
  const navItems = isServer ? serverNavItems : clientNavItems;

  return (
    <div className="flex h-full flex-col">
      <Link
        href={isServer ? "/dashboard/server" : "/dashboard/client"}
        onClick={onLinkClick}
        className="flex items-center gap-2.5 border-b px-4 py-4"
      >
        <div className="relative h-9 w-9 shrink-0">
          <Image
            src="/logo.png"
            alt="AegisHealth"
            fill
            sizes="36px"
            className="rounded-lg object-contain"
            priority
          />
        </div>
        <div className="flex flex-col">
          <span className="text-lg font-semibold tracking-tight">AegisHealth</span>
          <span className="text-xs text-muted-foreground">
            Federated Learning
          </span>
        </div>
      </Link>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <NavLinks items={navItems} onLinkClick={onLinkClick} />
      </div>

      <div className="border-t p-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-start gap-3 px-3"
              aria-label="User menu"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Shield className="size-4 text-primary" aria-hidden />
              </div>
              <div className="flex min-w-0 flex-1 flex-col items-start text-left">
                <span className="truncate text-sm font-medium">
                  {user?.email ?? "User"}
                </span>
                <span className="text-xs text-muted-foreground capitalize">
                  {user?.role?.replace("_", " ") ?? "—"}
                </span>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <button
                type="button"
                onClick={logout}
                className="w-full cursor-pointer"
              >
                Sign Out
              </button>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-sidebar lg:flex">
        <SidebarContent />
      </aside>

      <div className="flex items-center gap-2 lg:hidden">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Open menu">
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <SidebarContent onLinkClick={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
