import { api } from "@/lib/api";
import type { Lead, MasterKind, OpportunityRow, Paginated, PipelineStage } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { LeadsView } from "@/features/leads/leads-view";

export const dynamic = "force-dynamic";

async function load() {
  const [leads, stages, opportunities, customerTypes] = await Promise.all([
    api
      .get<Paginated<Lead>>("/leads?page=1&page_size=200")
      .then((r) => r.items)
      .catch(() => [] as Lead[]),
    api.get<PipelineStage[]>("/pipeline-stages").catch(() => [] as PipelineStage[]),
    api.get<OpportunityRow[]>("/opportunities").catch(() => [] as OpportunityRow[]),
    api.get<MasterKind[]>("/customer-types").catch(() => [] as MasterKind[]),
  ]);
  return { leads, stages, opportunities, customerTypes };
}

export default async function LeadsPage() {
  const { leads, stages, opportunities, customerTypes } = await load();
  const open = leads.filter((l) => l.status === "open").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leads"
        crumbs={[{ label: "Leads" }]}
        meta={`${leads.length} lead${leads.length === 1 ? "" : "s"}${open > 0 ? ` · ${open} open` : ""} · ${opportunities.length} opportunities`}
      />
      <LeadsView leads={leads} stages={stages} opportunities={opportunities} customerTypes={customerTypes} />
    </div>
  );
}
