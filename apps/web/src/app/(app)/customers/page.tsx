import { api } from "@/lib/api";
import type { Customer, MasterRow, Paginated } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { CustomersTable } from "@/features/customers/customers-table";

export const dynamic = "force-dynamic";

async function load(): Promise<{ customers: Customer[]; types: MasterRow[] }> {
  const [customers, types] = await Promise.all([
    api.get<Paginated<Customer>>("/customers?page=1&page_size=100").then((r) => r.items).catch(() => []),
    api.get<MasterRow[]>("/customer-types").catch(() => []),
  ]);
  return { customers, types };
}

export default async function CustomersPage() {
  const { customers, types } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        crumbs={[{ label: "Customers" }]}
        meta={`${customers.length} customer${customers.length === 1 ? "" : "s"} in the directory`}
      />
      <CustomersTable customers={customers} customerTypes={types} />
    </div>
  );
}
