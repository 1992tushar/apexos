import { api } from "@/lib/api";
import type { Paginated, PurchaseOrderRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { PurchaseOrdersTable } from "@/features/procurement/purchase-orders-table";

export const dynamic = "force-dynamic";

async function load(): Promise<PurchaseOrderRow[]> {
  return api
    .get<Paginated<PurchaseOrderRow>>("/purchase-orders?page=1&page_size=100")
    .then((r) => r.items)
    .catch(() => []);
}

export default async function PurchaseOrdersPage() {
  const orders = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchase Orders"
        crumbs={[{ label: "Purchase Orders" }]}
        meta={`${orders.length} order${orders.length === 1 ? "" : "s"}`}
      />
      <PurchaseOrdersTable orders={orders} />
    </div>
  );
}
