"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, PackageCheck, Receipt } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { SalesOrderStatus } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";

type ActionKey = "confirm" | "fulfill" | "invoice";

const NEXT_ACTION: Partial<Record<SalesOrderStatus, { key: ActionKey; label: string; icon: React.ReactNode }>> = {
  draft: { key: "confirm", label: "Confirm order", icon: <CheckCircle2 className="size-4" /> },
  confirmed: { key: "fulfill", label: "Fulfill", icon: <PackageCheck className="size-4" /> },
  fulfilled: { key: "invoice", label: "Create invoice", icon: <Receipt className="size-4" /> },
};

export function OrderActions({ id, status }: { id: string; status: SalesOrderStatus }) {
  const router = useRouter();
  const { toast } = useToast();
  const [pending, setPending] = React.useState<ActionKey | null>(null);

  const action = NEXT_ACTION[status];
  if (!action) {
    return null;
  }

  async function run(key: ActionKey) {
    setPending(key);
    try {
      await api.post(`/sales-orders/${id}/${key}`);
      toast({ title: `Order ${key === "invoice" ? "invoiced" : `${key}ed`}`, variant: "success" });
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Action failed";
      toast({ title: "Could not complete action", description: message, variant: "destructive" });
    } finally {
      setPending(null);
    }
  }

  return (
    <Button onClick={() => run(action.key)} loading={pending === action.key}>
      {action.icon}
      {action.label}
    </Button>
  );
}
