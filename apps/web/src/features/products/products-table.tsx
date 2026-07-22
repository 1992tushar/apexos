"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { Package } from "lucide-react";
import { formatMoney, formatNumber } from "@/lib/utils";
import type { MasterRow, Product } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { NewProductDialog } from "@/features/products/new-product-dialog";

type Masters = {
  categories: MasterRow[];
  brands: MasterRow[];
  uoms: MasterRow[];
  procurementModels: MasterRow[];
};

function StockCell({ qty }: { qty: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tabular-nums">{formatNumber(qty)}</span>
      {qty <= 0 ? (
        <Badge variant="destructive" dot>
          Out
        </Badge>
      ) : qty <= 10 ? (
        <Badge variant="warning" dot>
          Low
        </Badge>
      ) : null}
    </span>
  );
}

const columns: ColumnDef<Product, unknown>[] = [
  {
    accessorKey: "sku_code",
    header: "SKU",
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.sku_code}</span>,
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  { accessorKey: "category_name", header: "Category" },
  { accessorKey: "brand_name", header: "Brand" },
  {
    accessorKey: "specification",
    header: "Spec",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.specification || "—"}</span>
    ),
  },
  {
    accessorKey: "selling_price_minor",
    header: "Price",
    meta: { align: "right" },
    cell: ({ row }) => formatMoney(row.original.selling_price_minor),
  },
  {
    accessorKey: "stock_on_hand",
    header: "Stock",
    meta: { align: "right" },
    cell: ({ row }) => <StockCell qty={row.original.stock_on_hand} />,
  },
];

export function ProductsTable({ products, masters }: { products: Product[]; masters: Masters }) {
  return (
    <DataTable
      columns={columns}
      data={products}
      searchPlaceholder="Search products…"
      toolbar={<NewProductDialog masters={masters} />}
      emptyState={
        <EmptyState
          icon={<Package className="size-8" strokeWidth={1.5} />}
          title="No products yet"
          description="Create your first SKU to build the catalog."
          action={<NewProductDialog masters={masters} />}
        />
      }
    />
  );
}
