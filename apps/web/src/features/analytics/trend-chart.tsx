"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatMoney } from "@/lib/utils";
import type { TrendPoint } from "@/lib/dto";

/** Revenue vs purchases, monthly. Amounts are minor units; plotted in rupees. */
export function TrendChart({
  revenue,
  purchases,
}: {
  revenue: TrendPoint[];
  purchases: TrendPoint[];
}) {
  const byPeriod = new Map<string, { period: string; revenue: number; purchases: number }>();
  for (const p of revenue) {
    byPeriod.set(p.period, { period: p.period, revenue: p.amount_minor / 100, purchases: 0 });
  }
  for (const p of purchases) {
    const row = byPeriod.get(p.period) ?? { period: p.period, revenue: 0, purchases: 0 };
    row.purchases = p.amount_minor / 100;
    byPeriod.set(p.period, row);
  }
  const data = Array.from(byPeriod.values()).sort((a, b) => a.period.localeCompare(b.period));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          width={56}
          tickFormatter={(v: number) =>
            new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(v)
          }
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 8,
            fontSize: 12,
            color: "hsl(var(--popover-foreground))",
          }}
          formatter={(value: number, name: string) => [formatMoney(Math.round(value * 100)), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="revenue" name="Revenue" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="purchases" name="Purchases" stroke="hsl(var(--muted-foreground))" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
