import Link from "next/link";
import { IndianRupee, Percent, ShoppingCart, TrendingUp } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import type { KpiBoard } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendChart } from "@/features/analytics/trend-chart";

export const dynamic = "force-dynamic";

async function load(): Promise<KpiBoard | null> {
  try {
    return await api.get<KpiBoard>("/analytics/kpis");
  } catch (err) {
    if (err instanceof ApiError) return null;
    return null;
  }
}

function TopList({ title, rows }: { title: string; rows: { id: string | null; name: string; value_minor: number }[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No data yet.</p>
        ) : (
          rows.map((r, i) => (
            <div key={r.id ?? i} className="flex items-center gap-3 rounded-md px-2 py-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{r.name}</span>
              <span className="tabular-nums text-sm text-muted-foreground">{formatMoney(r.value_minor)}</span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

export default async function AnalyticsPage() {
  const kpi = await load();

  if (!kpi) {
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics" meta="KPI board" />
        <EmptyState
          icon={<TrendingUp className="size-8" strokeWidth={1.5} />}
          title="Analytics unavailable"
          description="Could not reach GET /analytics/kpis. Start the ApexOS API and refresh."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" meta="Margins, cash-cycle and top performers." />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Revenue" value={formatMoney(kpi.revenue_minor)} hint="Invoiced, all time" icon={<TrendingUp className="size-4" />} accent="primary" />
        <StatTile label="Gross profit" value={formatMoney(kpi.gross_profit_minor)} hint={`${(kpi.margin_bps / 100).toFixed(1)}% margin`} icon={<Percent className="size-4" />} accent="success" />
        <StatTile label="Purchases" value={formatMoney(kpi.purchases_minor)} hint="Billed, all time" icon={<ShoppingCart className="size-4" />} />
        <StatTile label="Receivables" value={formatMoney(kpi.receivables_minor)} hint="Outstanding from customers" icon={<IndianRupee className="size-4" />} accent={kpi.receivables_minor > 0 ? "warning" : "none"} />
        <StatTile label="Payables" value={formatMoney(kpi.payables_minor)} hint="Owed to suppliers" icon={<IndianRupee className="size-4" />} accent={kpi.payables_minor > 0 ? "destructive" : "none"} />
        <StatTile label="DSO" value={`${formatNumber(kpi.dso_days)} days`} hint="Days sales outstanding" />
        <StatTile label="Fill rate" value={`${(kpi.fill_rate_bps / 100).toFixed(0)}%`} hint="Orders fulfilled" accent="success" />
        <StatTile label="Margin" value={`${(kpi.margin_bps / 100).toFixed(1)}%`} hint="Gross margin" />
      </section>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Revenue vs purchases</CardTitle>
          <span className="text-xs text-muted-foreground">Last 6 months</span>
        </CardHeader>
        <CardContent className="pl-2">
          <TrendChart revenue={kpi.revenue_trend} purchases={kpi.purchase_trend} />
        </CardContent>
      </Card>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <TopList title="Top customers" rows={kpi.top_customers} />
        <TopList title="Top suppliers" rows={kpi.top_suppliers} />
        <TopList title="Top products" rows={kpi.top_products} />
      </section>
    </div>
  );
}
