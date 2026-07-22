"use client";

import * as React from "react";
import { Bell, Check } from "lucide-react";
import { timeAgo } from "@/lib/format";
import type { Notification, NotificationList } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const HEADERS = { "X-Dev-Actor": "founder@apexsupply.example" };

const LEVEL_DOT: Record<string, string> = {
  info: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
};

/** App-shell inbox: unread count on the bell; a slide-over lists notifications. */
export function NotificationBell() {
  const [open, setOpen] = React.useState(false);
  const [items, setItems] = React.useState<Notification[]>([]);
  const [unread, setUnread] = React.useState(0);

  const load = React.useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/notifications?limit=50`, { headers: HEADERS, cache: "no-store" });
      if (!res.ok) return;
      const data = (await res.json()) as NotificationList;
      setItems(data.items);
      setUnread(data.unread);
    } catch {
      /* offline / API down — leave the bell quiet */
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  React.useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function markAllRead() {
    try {
      await fetch(`${API_BASE}/notifications/read-all`, { method: "POST", headers: HEADERS });
      await load();
    } catch {
      /* ignore */
    }
  }

  async function markRead(id: string) {
    try {
      await fetch(`${API_BASE}/notifications/${id}/read`, { method: "POST", headers: HEADERS });
      await load();
    } catch {
      /* ignore */
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
          <Bell className="size-4" />
          {unread > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-destructive-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader className="flex-row items-center justify-between">
          <SheetTitle>Notifications</SheetTitle>
          {unread > 0 ? (
            <Button variant="ghost" size="sm" onClick={markAllRead}>
              <Check className="size-4" /> Mark all read
            </Button>
          ) : null}
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-4">
          {items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">You’re all caught up.</p>
          ) : (
            <ul className="space-y-2">
              {items.map((n) => (
                <li
                  key={n.id}
                  className={`rounded-md border p-3 ${n.is_read ? "opacity-60" : "bg-accent/40"}`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${LEVEL_DOT[n.level] ?? "bg-muted-foreground"}`} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{n.title}</p>
                      {n.body ? <p className="text-sm text-muted-foreground">{n.body}</p> : null}
                      <p className="mt-1 text-xs text-muted-foreground">{timeAgo(n.created_at)}</p>
                    </div>
                    {!n.is_read ? (
                      <button
                        type="button"
                        onClick={() => markRead(n.id)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Read
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
