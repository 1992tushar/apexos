"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, SECTION_LABELS, type NavItem } from "@/components/app-shell/nav-config";

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  let lastSection: NavItem["section"] | null = null;

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r bg-sidebar text-sidebar-foreground lg:flex">
      <div className="flex h-14 items-center gap-2 px-5">
        <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Boxes className="size-4" />
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-white">ApexOS</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map((item) => {
          const label = SECTION_LABELS[item.section];
          const showLabel = item.section !== lastSection && label;
          lastSection = item.section;
          const active = isActivePath(pathname, item.href);
          const Icon = item.icon;

          return (
            <div key={item.href}>
              {showLabel ? (
                <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/45">
                  {label}
                </p>
              ) : null}
              <Link
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-white/10 font-medium text-white"
                    : "text-sidebar-foreground/80 hover:bg-white/5 hover:text-white",
                )}
              >
                {active ? (
                  <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" aria-hidden />
                ) : null}
                <Icon className="size-[18px] shrink-0" strokeWidth={1.75} />
                <span className="truncate">{item.label}</span>
                {!item.active ? (
                  <span className="ml-auto text-[10px] uppercase tracking-wide text-sidebar-foreground/35">
                    soon
                  </span>
                ) : null}
              </Link>
            </div>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-1.5">
          <span className="flex size-8 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
            TT
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">Tushar Thopte</p>
            <p className="truncate text-xs text-sidebar-foreground/50">Founder</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
