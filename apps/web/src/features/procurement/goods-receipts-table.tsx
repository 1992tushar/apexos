"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { PackageCheck } from "lucide-react";
import { formatNumber } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { GoodsReceiptRow } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";

const columns: ColumnDef<GoodsReceiptRow, unknown>[] = [
  {
    accessorKey: "receipt_no",
    header: "Receipt",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.receipt_no}</span>,
  },
  {
    accessorKey: "po_no",
    header: "PO",
    cell: ({ row }) => <span className="font-mono text-xs">{row.original.po_no ?? "—"}</span>,
  },
  {
    accessorKey: "supplier_name",
    header: "Supplier",
    cell: ({ row }) => <span className="font-medium">{row.original.supplier_name}</span>,
  },
  {
    accessorKey: "warehouse_name",
    header: "Warehouse",
    cell: ({ row }) => row.original.warehouse_name ?? "—",
  },
  {
    accessorKey: "line_count",
    header: "Lines",
    meta: { align: "right" },
    cell: ({ row }) => formatNumber(row.original.line_count),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant="success" dot>
        {row.original.status ? row.original.status[0].toUpperCase() + row.original.status.slice(1) : "—"}
      </Badge>
    ),
  },
  {
    accessorKey: "received_at",
    header: "Received",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.received_at ? formatDate(row.original.received_at) : "—"}
      </span>
    ),
  },
];

export function GoodsReceiptsTable({ receipts }: { receipts: GoodsReceiptRow[] }) {
  return (
    <DataTable
      columns={columns}
      data={receipts}
      searchPlaceholder="Search receipts…"
      rowHref={(r) => `/purchase-orders/${r.purchase_order_id}`}
      emptyState={
        <EmptyState
          icon={<PackageCheck className="size-8" strokeWidth={1.5} />}
          title="No goods receipts"
          description="Receiving goods against a confirmed purchase order posts stock in and appears here."
        />
      }
    />
  );
}
