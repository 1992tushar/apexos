"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, PackageCheck, Receipt } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { PurchaseOrderStatus } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";

type ActionKey = "confirm" | "receive" | "bill";

type Action = { key: ActionKey; label: string; icon: React.ReactNode; variant?: "primary" | "outline" };

/** Available actions per PO status. Partially-received orders can receive more
 * remaining stock or be billed for what has arrived so far. */
const ACTIONS: Record<PurchaseOrderStatus, Action[]> = {
  draft: [{ key: "confirm", label: "Confirm PO", icon: <CheckCircle2 className="size-4" /> }],
  confirmed: [{ key: "receive", label: "Receive goods", icon: <PackageCheck className="size-4" /> }],
  partially_received: [
    { key: "receive", label: "Receive remaining", icon: <PackageCheck className="size-4" /> },
    { key: "bill", label: "Create bill", icon: <Receipt className="size-4" />, variant: "outline" },
  ],
  received: [{ key: "bill", label: "Create bill", icon: <Receipt className="size-4" /> }],
  billed: [],
  cancelled: [],
};

const DONE_LABEL: Record<ActionKey, string> = {
  confirm: "confirmed",
  receive: "received",
  bill: "billed",
};

export function PoActions({ id, status }: { id: string; status: PurchaseOrderStatus }) {
  const router = useRouter();
  const { toast } = useToast();
  const [pending, setPending] = React.useState<ActionKey | null>(null);

  const actions = ACTIONS[status] ?? [];
  if (actions.length === 0) return null;

  async function run(key: ActionKey) {
    setPending(key);
    try {
      await api.post(`/purchase-orders/${id}/${key}`);
      toast({ title: `Purchase order ${DONE_LABEL[key]}`, variant: "success" });
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Action failed";
      toast({ title: "Could not complete action", description: message, variant: "destructive" });
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {actions.map((a) => (
        <Button
          key={a.key}
          variant={a.variant ?? "primary"}
          onClick={() => run(a.key)}
          loading={pending === a.key}
          disabled={pending !== null}
        >
          {a.icon}
          {a.label}
        </Button>
      ))}
    </div>
  );
}
