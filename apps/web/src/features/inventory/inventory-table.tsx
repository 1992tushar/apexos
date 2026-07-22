"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { Boxes } from "lucide-react";
import { formatNumber } from "@/lib/utils";
import type { StockRow } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";

const columns: ColumnDef<StockRow, unknown>[] = [
  {
    accessorKey: "sku_code",
    header: "SKU",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.sku_code}</span>,
  },
  {
    accessorKey: "product_name",
    header: "Product",
    cell: ({ row }) => <span className="font-medium">{row.original.product_name}</span>,
  },
  { accessorKey: "warehouse_name", header: "Warehouse" },
  {
    accessorKey: "qty_on_hand",
    header: "On hand",
    meta: { align: "right" },
    cell: ({ row }) => formatNumber(row.original.qty_on_hand),
  },
  {
    accessorKey: "reorder_level",
    header: "Reorder",
    meta: { align: "right" },
    cell: ({ row }) => <span className="text-muted-foreground">{formatNumber(row.original.reorder_level)}</span>,
  },
  {
    id: "state",
    header: "State",
    cell: ({ row }) =>
      row.original.is_low ? (
        <Badge variant="warning" dot>
          Low stock
        </Badge>
      ) : (
        <Badge variant="success" dot>
          In stock
        </Badge>
      ),
  },
];

export function InventoryTable({ stock }: { stock: StockRow[] }) {
  return (
    <DataTable
      columns={columns}
      data={stock}
      searchPlaceholder="Search stock…"
      emptyState={
        <EmptyState
          icon={<Boxes className="size-8" strokeWidth={1.5} />}
          title="No stock records"
          description="Stock balances appear here once inventory movements are posted."
        />
      }
    />
  );
}
