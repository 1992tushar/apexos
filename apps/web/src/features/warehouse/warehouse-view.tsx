"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Boxes, Warehouse as WarehouseIcon } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import type { Product, Warehouse, WarehouseStockRow } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { StatTile } from "@/components/shared/stat-tile";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { TransferStockDialog } from "@/features/warehouse/transfer-stock-dialog";
import { AdjustStockDialog } from "@/features/warehouse/adjust-stock-dialog";

const columns: ColumnDef<WarehouseStockRow, unknown>[] = [
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
  {
    accessorKey: "warehouse_name",
    header: "Warehouse",
    cell: ({ row }) => <Badge variant="secondary">{row.original.warehouse_name}</Badge>,
  },
  {
    accessorKey: "qty_on_hand",
    header: "On hand",
    meta: { align: "right" },
    cell: ({ row }) => (
      <span className={cn("tabular-nums font-medium", row.original.is_low && "text-warning-foreground dark:text-warning")}>
        {formatNumber(row.original.qty_on_hand)}
      </span>
    ),
  },
  {
    accessorKey: "reorder_level",
    header: "Reorder",
    meta: { align: "right" },
    cell: ({ row }) => <span className="tabular-nums text-muted-foreground">{formatNumber(row.original.reorder_level)}</span>,
  },
];

export function WarehouseView({
  warehouses,
  stock,
  products,
}: {
  warehouses: Warehouse[];
  stock: WarehouseStockRow[];
  products: Product[];
}) {
  const [warehouseId, setWarehouseId] = React.useState<string | "all">("all");
  const filtered = warehouseId === "all" ? stock : stock.filter((s) => s.warehouse_id === warehouseId);

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {warehouses.map((w) => {
          const lines = stock.filter((s) => s.warehouse_id === w.id);
          const units = lines.reduce((sum, l) => sum + Number(l.qty_on_hand), 0);
          return (
            <StatTile
              key={w.id}
              label={w.name}
              value={formatNumber(units)}
              hint={`${lines.length} SKU${lines.length === 1 ? "" : "s"} · ${w.city ?? "—"}`}
              icon={<WarehouseIcon className="size-4" />}
              accent={w.is_active ? "primary" : "none"}
            />
          );
        })}
      </section>

      <DataTable
        columns={columns}
        data={filtered}
        searchPlaceholder="Search stock…"
        toolbar={
          <div className="flex flex-wrap items-center gap-2">
            <div className="hidden items-center gap-1 rounded-md border bg-muted/40 p-0.5 sm:flex">
              <button
                type="button"
                onClick={() => setWarehouseId("all")}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  warehouseId === "all" ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
                )}
              >
                All
              </button>
              {warehouses.map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => setWarehouseId(w.id)}
                  className={cn(
                    "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                    warehouseId === w.id ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {w.name}
                </button>
              ))}
            </div>
            <TransferStockDialog warehouses={warehouses} products={products} />
            <AdjustStockDialog warehouses={warehouses} products={products} />
          </div>
        }
        emptyState={
          <EmptyState
            icon={<Boxes className="size-8" strokeWidth={1.5} />}
            title="No stock in this warehouse"
            description="Receive goods or transfer stock in to see balances here."
          />
        }
      />
    </div>
  );
}
