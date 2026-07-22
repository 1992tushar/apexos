"use client";

import * as React from "react";
import Link from "next/link";
import { type ColumnDef } from "@tanstack/react-table";
import { ClipboardList, Plus } from "lucide-react";
import { formatMoney, formatNumber, cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { PurchaseOrderRow, PurchaseOrderStatus } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import { PurchaseOrderStatusBadge } from "@/components/shared/status-badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";

const STATUS_FILTERS: { label: string; value: PurchaseOrderStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Received", value: "received" },
  { label: "Billed", value: "billed" },
];

const columns: ColumnDef<PurchaseOrderRow, unknown>[] = [
  {
    accessorKey: "po_no",
    header: "PO",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.po_no}</span>,
  },
  {
    accessorKey: "supplier_name",
    header: "Supplier",
    cell: ({ row }) => <span className="font-medium">{row.original.supplier_name}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <PurchaseOrderStatusBadge status={row.original.status} />,
  },
  {
    accessorKey: "line_count",
    header: "Lines",
    meta: { align: "right" },
    cell: ({ row }) => formatNumber(row.original.line_count),
  },
  {
    accessorKey: "total_minor",
    header: "Total",
    meta: { align: "right" },
    cell: ({ row }) => formatMoney(row.original.total_minor),
  },
  {
    accessorKey: "order_date",
    header: "Date",
    cell: ({ row }) => <span className="text-muted-foreground">{formatDate(row.original.order_date)}</span>,
  },
];

export function PurchaseOrdersTable({ orders }: { orders: PurchaseOrderRow[] }) {
  const [status, setStatus] = React.useState<PurchaseOrderStatus | "all">("all");
  const filtered = status === "all" ? orders : orders.filter((o) => o.status === status);

  return (
    <DataTable
      columns={columns}
      data={filtered}
      searchPlaceholder="Search purchase orders…"
      rowHref={(o) => `/purchase-orders/${o.id}`}
      toolbar={
        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-1 rounded-md border bg-muted/40 p-0.5 sm:flex">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => setStatus(f.value)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  status === f.value
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <Button asChild size="sm">
            <Link href="/purchase-orders/new">
              <Plus className="size-4" /> New PO
            </Link>
          </Button>
        </div>
      }
      emptyState={
        <EmptyState
          icon={<ClipboardList className="size-8" strokeWidth={1.5} />}
          title="No purchase orders"
          description="Raise a purchase order to buy stock from a supplier."
          action={
            <Button asChild size="sm">
              <Link href="/purchase-orders/new">
                <Plus className="size-4" /> New PO
              </Link>
            </Button>
          }
        />
      }
    />
  );
}
