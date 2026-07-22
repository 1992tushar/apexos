import Link from "next/link";
import {
  AlertTriangle,
  Boxes,
  IndianRupee,
  Receipt,
  ShoppingCart,
  TrendingUp,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import { timeAgo } from "@/lib/format";
import type { DashboardSummary } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RevenueChart } from "@/features/dashboard/revenue-chart";

export const dynamic = "force-dynamic";

async function getSummary(): Promise<DashboardSummary | null> {
  try {
    return await api.get<DashboardSummary>("/dashboard/summary");
  } catch (err) {
    if (err instanceof ApiError) return null;
    return null;
  }
}

export default async function DashboardPage() {
  const data = await getSummary();

  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" meta="Company command center" />
        <EmptyState
          icon={<TrendingUp className="size-8" strokeWidth={1.5} />}
          title="Dashboard data unavailable"
          description="Could not reach GET /dashboard/summary. Start the ApexOS API on http://localhost:8000 and refresh."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" meta="What happened today, and what needs your attention." />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile
          label="Today's Sales"
          value={formatMoney(data.today_sales_minor)}
          hint="Booked today"
          icon={<TrendingUp className="size-4" />}
          accent="primary"
          href="/sales"
        />
        <StatTile
          label="Outstanding Receivables"
          value={formatMoney(data.outstanding_receivables_minor)}
          hint="Awaiting collection"
          icon={<IndianRupee className="size-4" />}
          accent={data.outstanding_receivables_minor > 0 ? "warning" : "none"}
          href="/finance"
        />
        <StatTile
          label="Inventory Value"
          value={formatMoney(data.inventory_value_minor)}
          hint="On-hand at cost"
          icon={<Boxes className="size-4" />}
          href="/inventory"
        />
        <StatTile
          label="Low-Stock Items"
          value={formatNumber(data.low_stock_count)}
          hint="Below reorder level"
          icon={<AlertTriangle className="size-4" />}
          accent={data.low_stock_count > 0 ? "destructive" : "success"}
          href="/inventory"
        />
        <StatTile
          label="Pending Sales Orders"
          value={formatNumber(data.pending_sales_orders)}
          hint="Awaiting fulfillment"
          icon={<ShoppingCart className="size-4" />}
          accent={data.pending_sales_orders > 0 ? "warning" : "none"}
          href="/sales"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Revenue trend</CardTitle>
            <span className="text-xs text-muted-foreground">Last 14 days</span>
          </CardHeader>
          <CardContent className="pl-2">
            {data.revenue_trend.length > 0 ? (
              <RevenueChart data={data.revenue_trend} />
            ) : (
              <p className="py-16 text-center text-sm text-muted-foreground">No revenue in this window.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top customers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {data.top_customers.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">No customer revenue yet.</p>
            ) : (
              data.top_customers.map((c, i) => (
                <Link
                  key={c.id}
                  href={`/customers/${c.id}`}
                  className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-accent"
                >
                  <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{c.name}</span>
                  <span className="tabular-nums text-sm text-muted-foreground">
                    {formatMoney(c.revenue_minor)}
                  </span>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_activities.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Nothing has happened yet.</p>
            ) : (
              <ol className="space-y-4">
                {data.recent_activities.map((a) => (
                  <li key={a.id} className="flex items-start gap-3">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm">
                        <span className="font-medium capitalize">{a.verb}</span>{" "}
                        <span className="text-muted-foreground">· {a.entity_type}</span>
                      </p>
                      <p className="truncate text-sm text-muted-foreground">{a.summary}</p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(a.occurred_at)}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
