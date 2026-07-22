"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Factory, Star } from "lucide-react";
import { formatMoney } from "@/lib/utils";
import type { MasterRow, Supplier } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { GenericStatusBadge } from "@/components/shared/status-badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { NewSupplierDialog } from "@/features/suppliers/new-supplier-dialog";

const columns: ColumnDef<Supplier, unknown>[] = [
  {
    accessorKey: "code",
    header: "Code",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.code}</span>,
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "supplier_type_name",
    header: "Type",
    cell: ({ row }) => <Badge variant="secondary">{row.original.supplier_type_name ?? "—"}</Badge>,
  },
  { accessorKey: "city", header: "City", cell: ({ row }) => row.original.city || "—" },
  {
    id: "score",
    header: "Score",
    meta: { align: "right" },
    cell: ({ row }) =>
      row.original.latest_score != null ? (
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Star className="size-3.5 text-warning" /> {row.original.latest_score}/5
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    accessorKey: "outstanding_minor",
    header: "Payable",
    meta: { align: "right" },
    cell: ({ row }) => formatMoney(row.original.outstanding_minor),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <GenericStatusBadge status={row.original.status} />,
  },
];

export function SuppliersTable({
  suppliers,
  supplierTypes,
}: {
  suppliers: Supplier[];
  supplierTypes: MasterRow[];
}) {
  return (
    <DataTable
      columns={columns}
      data={suppliers}
      searchPlaceholder="Search suppliers…"
      rowHref={(s) => `/suppliers/${s.id}`}
      toolbar={<NewSupplierDialog supplierTypes={supplierTypes} />}
      emptyState={
        <EmptyState
          icon={<Factory className="size-8" strokeWidth={1.5} />}
          title="No suppliers yet"
          description="Add your first supplier to start raising purchase orders."
          action={<NewSupplierDialog supplierTypes={supplierTypes} />}
        />
      }
    />
  );
}
