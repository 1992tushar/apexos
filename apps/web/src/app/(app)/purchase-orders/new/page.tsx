import { api } from "@/lib/api";
import type { Paginated, Product, Supplier } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { NewPurchaseOrderForm } from "@/features/procurement/new-purchase-order-form";

export const dynamic = "force-dynamic";

async function load() {
  const [suppliers, products] = await Promise.all([
    api.get<Paginated<Supplier>>("/suppliers?page=1&page_size=200").then((r) => r.items).catch(() => [] as Supplier[]),
    api.get<Paginated<Product>>("/products?page=1&page_size=200").then((r) => r.items).catch(() => [] as Product[]),
  ]);
  return { suppliers, products };
}

export default async function NewPurchaseOrderPage() {
  const { suppliers, products } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="New purchase order"
        backHref="/purchase-orders"
        crumbs={[{ label: "Purchase Orders", href: "/purchase-orders" }, { label: "New" }]}
      />
      <NewPurchaseOrderForm suppliers={suppliers} products={products} />
    </div>
  );
}
