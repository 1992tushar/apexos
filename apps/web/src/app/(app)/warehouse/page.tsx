import { api } from "@/lib/api";
import type { Paginated, Product, Warehouse, WarehouseStockRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { WarehouseView } from "@/features/warehouse/warehouse-view";

export const dynamic = "force-dynamic";

async function load() {
  const [warehouses, stock, products] = await Promise.all([
    api.get<Warehouse[]>("/warehouses").catch(() => [] as Warehouse[]),
    api.get<WarehouseStockRow[]>("/inventory/warehouse-stock").catch(() => [] as WarehouseStockRow[]),
    api
      .get<Paginated<Product>>("/products?page=1&page_size=300")
      .then((r) => r.items)
      .catch(() => [] as Product[]),
  ]);
  return { warehouses, stock, products };
}

export default async function WarehousePage() {
  const { warehouses, stock, products } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warehouse"
        crumbs={[{ label: "Warehouse" }]}
        meta={`${warehouses.length} warehouse${warehouses.length === 1 ? "" : "s"} · ${stock.length} stock line${stock.length === 1 ? "" : "s"}`}
      />
      <WarehouseView warehouses={warehouses} stock={stock} products={products} />
    </div>
  );
}
