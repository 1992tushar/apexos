import { api } from "@/lib/api";
import type { Paginated, SalesOrderRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { SalesOrdersTable } from "@/features/sales/sales-orders-table";

export const dynamic = "force-dynamic";

async function load(): Promise<SalesOrderRow[]> {
  return api
    .get<Paginated<SalesOrderRow>>("/sales-orders?page=1&page_size=100")
    .then((r) => r.items)
    .catch(() => []);
}

export default async function SalesPage() {
  const orders = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sales"
        crumbs={[{ label: "Sales Orders" }]}
        meta={`${orders.length} order${orders.length === 1 ? "" : "s"}`}
      />
      <SalesOrdersTable orders={orders} />
    </div>
  );
}
