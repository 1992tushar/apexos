import { api } from "@/lib/api";
import type { MasterRow, Paginated, Supplier } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { SuppliersTable } from "@/features/suppliers/suppliers-table";

export const dynamic = "force-dynamic";

async function load(): Promise<{ suppliers: Supplier[]; types: MasterRow[] }> {
  const [suppliers, types] = await Promise.all([
    api.get<Paginated<Supplier>>("/suppliers?page=1&page_size=100").then((r) => r.items).catch(() => []),
    api.get<MasterRow[]>("/supplier-types").catch(() => []),
  ]);
  return { suppliers, types };
}

export default async function SuppliersPage() {
  const { suppliers, types } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Suppliers"
        crumbs={[{ label: "Suppliers" }]}
        meta={`${suppliers.length} supplier${suppliers.length === 1 ? "" : "s"} in the directory`}
      />
      <SuppliersTable suppliers={suppliers} supplierTypes={types} />
    </div>
  );
}
