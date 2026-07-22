import { api } from "@/lib/api";
import type { Customer, Paginated, Product } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { NewSalesOrderForm } from "@/features/sales/new-sales-order-form";

export const dynamic = "force-dynamic";

async function load() {
  const [customers, products] = await Promise.all([
    api.get<Paginated<Customer>>("/customers?page=1&page_size=200").then((r) => r.items).catch(() => [] as Customer[]),
    api.get<Paginated<Product>>("/products?page=1&page_size=200").then((r) => r.items).catch(() => [] as Product[]),
  ]);
  return { customers, products };
}

export default async function NewSalesOrderPage() {
  const { customers, products } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="New sales order"
        backHref="/sales"
        crumbs={[{ label: "Sales Orders", href: "/sales" }, { label: "New" }]}
      />
      <NewSalesOrderForm customers={customers} products={products} />
    </div>
  );
}
