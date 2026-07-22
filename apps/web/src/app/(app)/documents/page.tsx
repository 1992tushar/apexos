import { api } from "@/lib/api";
import type { DocumentRow, Paginated } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { DocumentsTable } from "@/features/documents/documents-table";

export const dynamic = "force-dynamic";

async function load(): Promise<DocumentRow[]> {
  return api
    .get<Paginated<DocumentRow>>("/documents?page=1&page_size=200")
    .then((r) => r.items)
    .catch(() => []);
}

export default async function DocumentsPage() {
  const documents = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        crumbs={[{ label: "Documents" }]}
        meta={`${documents.length} document${documents.length === 1 ? "" : "s"}`}
      />
      <DocumentsTable documents={documents} />
    </div>
  );
}
