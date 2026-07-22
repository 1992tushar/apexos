"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Users } from "lucide-react";
import { formatMoney } from "@/lib/utils";
import type { Customer, MasterRow } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { GenericStatusBadge } from "@/components/shared/status-badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { NewCustomerDialog } from "@/features/customers/new-customer-dialog";

const columns: ColumnDef<Customer, unknown>[] = [
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
    accessorKey: "customer_type_name",
    header: "Type",
    cell: ({ row }) => <Badge variant="secondary">{row.original.customer_type_name}</Badge>,
  },
  { accessorKey: "city", header: "City", cell: ({ row }) => row.original.city || "—" },
  {
    accessorKey: "outstanding_minor",
    header: "Outstanding",
    meta: { align: "right" },
    cell: ({ row }) => formatMoney(row.original.outstanding_minor),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <GenericStatusBadge status={row.original.status} />,
  },
];

export function CustomersTable({
  customers,
  customerTypes,
}: {
  customers: Customer[];
  customerTypes: MasterRow[];
}) {
  return (
    <DataTable
      columns={columns}
      data={customers}
      searchPlaceholder="Search customers…"
      rowHref={(c) => `/customers/${c.id}`}
      toolbar={<NewCustomerDialog customerTypes={customerTypes} />}
      emptyState={
        <EmptyState
          icon={<Users className="size-8" strokeWidth={1.5} />}
          title="No customers yet"
          description="Add your first customer to start placing sales orders."
          action={<NewCustomerDialog customerTypes={customerTypes} />}
        />
      }
    />
  );
}
