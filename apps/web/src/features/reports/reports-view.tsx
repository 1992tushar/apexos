"use client";

import * as React from "react";
import { Download, Play } from "lucide-react";
import { formatMoney } from "@/lib/utils";
import type { ReportInfo, ReportResult } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

function prettify(col: string): string {
  return col.replace(/_minor$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ReportsView({ reports }: { reports: ReportInfo[] }) {
  const { toast } = useToast();
  const [reportKey, setReportKey] = React.useState<string>(reports[0]?.key ?? "");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [result, setResult] = React.useState<ReportResult | null>(null);
  const [loading, setLoading] = React.useState(false);

  function query(): string {
    const p = new URLSearchParams();
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    return p.toString();
  }

  async function run() {
    if (!reportKey) return;
    setLoading(true);
    try {
      const qs = query();
      const res = await fetch(`${API_BASE}/reports/${reportKey}${qs ? `?${qs}` : ""}`, {
        headers: { "X-Dev-Actor": "founder@apexsupply.example" },
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Report failed");
      setResult((await res.json()) as ReportResult);
    } catch {
      toast({ title: "Could not run report", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function downloadCsv() {
    if (!reportKey) return;
    const p = new URLSearchParams({ format: "csv" });
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    window.open(`${API_BASE}/reports/${reportKey}?${p.toString()}`, "_blank");
  }

  const money = new Set(result?.money_columns ?? []);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Run a report</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] space-y-1.5">
            <Label>Report</Label>
            <Select value={reportKey} onValueChange={setReportKey}>
              <SelectTrigger>
                <SelectValue placeholder="Select a report" />
              </SelectTrigger>
              <SelectContent>
                {reports.map((r) => (
                  <SelectItem key={r.key} value={r.key}>
                    {r.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="from">From</Label>
            <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="to">To</Label>
            <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
          <Button onClick={run} loading={loading}>
            <Play className="size-4" /> Run
          </Button>
          <Button variant="outline" onClick={downloadCsv} disabled={!reportKey}>
            <Download className="size-4" /> CSV
          </Button>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{result.title}</CardTitle>
            <span className="text-xs text-muted-foreground">{result.rows.length} rows</span>
          </CardHeader>
          <CardContent className="px-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    {result.columns.map((c) => (
                      <TableHead key={c} className={money.has(c) ? "text-right" : ""}>
                        {prettify(c)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.rows.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={result.columns.length} className="py-10 text-center text-sm text-muted-foreground">
                        No data for this window.
                      </TableCell>
                    </TableRow>
                  ) : (
                    result.rows.map((row, i) => (
                      <TableRow key={i} className="hover:bg-transparent">
                        {result.columns.map((c) => {
                          const val = row[c];
                          const display =
                            money.has(c) && typeof val === "number" ? formatMoney(val) : String(val ?? "");
                          return (
                            <TableCell key={c} className={money.has(c) ? "text-right tabular-nums" : ""}>
                              {display}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">Pick a report and click Run to preview, or export CSV.</p>
      )}
    </div>
  );
}
