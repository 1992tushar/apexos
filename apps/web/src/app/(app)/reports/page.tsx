import { api } from "@/lib/api";
import type { ReportInfo } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { ReportsView } from "@/features/reports/reports-view";

export const dynamic = "force-dynamic";

async function load(): Promise<ReportInfo[]> {
  return api.get<ReportInfo[]>("/reports").catch(() => []);
}

export default async function ReportsPage() {
  const reports = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        crumbs={[{ label: "Reports" }]}
        meta="Tabular exports over the ledgers"
      />
      <ReportsView reports={reports} />
    </div>
  );
}
