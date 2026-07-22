import { api } from "@/lib/api";
import type { StockRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { InventoryTable } from "@/features/inventory/inventory-table";

export const dynamic = "force-dynamic";

async function load(): Promise<StockRow[]> {
  return api.get<StockRow[]>("/inventory/stock").catch(() => []);
}

export default async function InventoryPage() {
  const stock = await load();
  const lowCount = stock.filter((s) => s.is_low).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory"
        crumbs={[{ label: "Inventory" }]}
        meta={`${stock.length} stock line${stock.length === 1 ? "" : "s"}${lowCount > 0 ? ` · ${lowCount} low` : ""}`}
      />
      <InventoryTable stock={stock} />
    </div>
  );
}
