"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Receipt } from "lucide-react";
import { formatMoney, cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { InvoiceRow, InvoiceStatus } from "@/lib/dto";
import { InvoiceStatusBadge } from "@/components/shared/status-badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { RecordPaymentDialog } from "@/features/finance/record-payment-dialog";

const STATUS_FILTERS: { label: string; value: InvoiceStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Issued", value: "issued" },
  { label: "Part paid", value: "part_paid" },
  { label: "Paid", value: "paid" },
];

const columns: ColumnDef<InvoiceRow, unknown>[] = [
  {
    accessorKey: "invoice_no",
    header: "Invoice",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.invoice_no}</span>,
  },
  {
    accessorKey: "customer_name",
    header: "Customer",
    cell: ({ row }) => <span className="font-medium">{row.original.customer_name}</span>,
  },
  {
    accessorKey: "total_minor",
    header: "Total",
    meta: { align: "right" },
    cell: ({ row }) => formatMoney(row.original.total_minor),
  },
  {
    accessorKey: "paid_minor",
    header: "Paid",
    meta: { align: "right" },
    cell: ({ row }) => <span className="text-muted-foreground">{formatMoney(row.original.paid_minor)}</span>,
  },
  {
    accessorKey: "balance_minor",
    header: "Balance",
    meta: { align: "right" },
    cell: ({ row }) => (
      <span className={cn("font-medium", row.original.balance_minor > 0 && "text-warning-foreground dark:text-warning")}>
        {formatMoney(row.original.balance_minor)}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <InvoiceStatusBadge status={row.original.status} />,
  },
  {
    accessorKey: "due_date",
    header: "Due",
    cell: ({ row }) => <span className="text-muted-foreground">{formatDate(row.original.due_date)}</span>,
  },
  {
    id: "actions",
    header: "",
    cell: ({ row }) =>
      row.original.balance_minor > 0 ? <RecordPaymentDialog invoice={row.original} /> : null,
  },
];

export function InvoicesTable({ invoices }: { invoices: InvoiceRow[] }) {
  const [status, setStatus] = React.useState<InvoiceStatus | "all">("all");
  const filtered = status === "all" ? invoices : invoices.filter((i) => i.status === status);

  return (
    <DataTable
      columns={columns}
      data={filtered}
      searchPlaceholder="Search invoices…"
      toolbar={
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
      }
      emptyState={
        <EmptyState
          icon={<Receipt className="size-8" strokeWidth={1.5} />}
          title="No invoices"
          description="Invoices appear here once sales orders are billed."
        />
      }
    />
  );
}
