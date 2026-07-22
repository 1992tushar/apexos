"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, UserPlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import type { Lead, MasterKind, OpportunityRow, PipelineStage } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/shared/empty-state";
import { useToast } from "@/components/ui/toaster";
import { NewLeadDialog } from "@/features/leads/new-lead-dialog";

function ConvertButton({ lead }: { lead: Lead }) {
  const router = useRouter();
  const { toast } = useToast();
  const [pending, setPending] = React.useState(false);
  if (lead.status !== "open") {
    return <Badge variant={lead.status === "converted" ? "success" : "muted"}>{lead.status}</Badge>;
  }
  async function run() {
    setPending(true);
    try {
      await api.post(`/leads/${lead.id}/convert`, {});
      toast({ title: "Lead converted to customer", variant: "success" });
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Conversion failed";
      toast({ title: "Could not convert", description: message, variant: "destructive" });
    } finally {
      setPending(false);
    }
  }
  return (
    <Button variant="outline" size="sm" loading={pending} onClick={run}>
      <UserPlus className="size-4" /> Convert
    </Button>
  );
}

function AdvanceControl({ opp, stages }: { opp: OpportunityRow; stages: PipelineStage[] }) {
  const router = useRouter();
  const { toast } = useToast();
  const [pending, setPending] = React.useState(false);

  async function advance(stageId: string) {
    if (stageId === opp.pipeline_stage_id) return;
    setPending(true);
    try {
      await api.post(`/opportunities/${opp.id}/advance`, { pipeline_stage_id: stageId });
      toast({ title: "Opportunity moved", variant: "success" });
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Action failed";
      toast({ title: "Could not move", description: message, variant: "destructive" });
    } finally {
      setPending(false);
    }
  }

  return (
    <Select value={opp.pipeline_stage_id} onValueChange={advance} disabled={pending}>
      <SelectTrigger className="h-8 text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {stages.map((s) => (
          <SelectItem key={s.id} value={s.id}>
            {s.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function LeadsView({
  leads,
  stages,
  opportunities,
  customerTypes,
}: {
  leads: Lead[];
  stages: PipelineStage[];
  opportunities: OpportunityRow[];
  customerTypes: MasterKind[];
}) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Leads</CardTitle>
          <NewLeadDialog customerTypes={customerTypes} />
        </CardHeader>
        <CardContent className="px-0">
          {leads.length === 0 ? (
            <EmptyState
              icon={<UserPlus className="size-8" strokeWidth={1.5} />}
              title="No leads yet"
              description="Add a prospect to start your pipeline."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Company</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>City</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((l) => (
                  <TableRow key={l.id} className="hover:bg-transparent">
                    <TableCell className="font-medium">{l.company_name}</TableCell>
                    <TableCell className="text-muted-foreground">{l.contact_name ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{l.city ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{l.source ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <ConvertButton lead={l} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <ArrowRight className="size-4" /> Opportunity pipeline
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {stages.map((stage) => {
            const inStage = opportunities.filter((o) => o.pipeline_stage_id === stage.id);
            const total = inStage.reduce((sum, o) => sum + o.estimated_value_minor, 0);
            return (
              <Card key={stage.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>{stage.name}</span>
                    <span className="text-xs font-normal text-muted-foreground">{inStage.length}</span>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">{formatMoney(total)}</p>
                </CardHeader>
                <CardContent className="space-y-2">
                  {inStage.length === 0 ? (
                    <p className="py-2 text-xs text-muted-foreground">—</p>
                  ) : (
                    inStage.map((o) => (
                      <div key={o.id} className="rounded-md border p-2">
                        <p className="text-sm font-medium leading-tight">{o.name}</p>
                        <p className="mb-2 text-xs tabular-nums text-muted-foreground">
                          {formatMoney(o.estimated_value_minor)}
                        </p>
                        <AdvanceControl opp={o} stages={stages} />
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
