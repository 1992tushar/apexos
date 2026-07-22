import { api } from "@/lib/api";
import type { MasterRow, Paginated, Product } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { ProductsTable } from "@/features/products/products-table";

export const dynamic = "force-dynamic";

async function load() {
  const [products, categories, brands, uoms, procurementModels] = await Promise.all([
    api.get<Paginated<Product>>("/products?page=1&page_size=100").then((r) => r.items).catch(() => [] as Product[]),
    api.get<MasterRow[]>("/categories").catch(() => [] as MasterRow[]),
    api.get<MasterRow[]>("/brands").catch(() => [] as MasterRow[]),
    api.get<MasterRow[]>("/uoms").catch(() => [] as MasterRow[]),
    api.get<MasterRow[]>("/procurement-models").catch(() => [] as MasterRow[]),
  ]);
  return { products, masters: { categories, brands, uoms, procurementModels } };
}

export default async function ProductsPage() {
  const { products, masters } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        crumbs={[{ label: "Products" }]}
        meta={`${products.length} SKU${products.length === 1 ? "" : "s"} in the catalog`}
      />
      <ProductsTable products={products} masters={masters} />
    </div>
  );
}
