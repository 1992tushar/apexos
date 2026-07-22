import { api } from "@/lib/api";
import type { Category, MasterKind } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { CategoriesTable } from "@/features/categories/categories-table";

export const dynamic = "force-dynamic";

async function load() {
  const [categories, procurementModels] = await Promise.all([
    api.get<Category[]>("/categories").catch(() => [] as Category[]),
    api.get<MasterKind[]>("/procurement-models").catch(() => [] as MasterKind[]),
  ]);
  return { categories, procurementModels };
}

export default async function CategoriesPage() {
  const { categories, procurementModels } = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Categories"
        crumbs={[{ label: "Categories" }]}
        meta={`${categories.length} categor${categories.length === 1 ? "y" : "ies"}`}
      />
      <CategoriesTable categories={categories} procurementModels={procurementModels} />
    </div>
  );
}
