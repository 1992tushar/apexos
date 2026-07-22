import { notFound } from "next/navigation";
import { Mail, MapPin, Phone, Receipt, Star } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { Supplier, SupplierEvaluation } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { GenericStatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ScoreSupplierDialog } from "@/features/suppliers/score-supplier-dialog";

export const dynamic = "force-dynamic";

async function getSupplier(id: string): Promise<Supplier | null> {
  try {
    return await api.get<Supplier>(`/suppliers/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    return null;
  }
}

async function getEvaluations(id: string): Promise<SupplierEvaluation[]> {
  return api.get<SupplierEvaluation[]>(`/suppliers/${id}/evaluations`).catch(() => []);
}

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium">{value || "—"}</p>
      </div>
    </div>
  );
}

export default async function SupplierDetailPage({ params }: { params: { id: string } }) {
  const supplier = await getSupplier(params.id);
  if (!supplier) notFound();
  const evaluations = await getEvaluations(params.id);

  return (
    <div className="space-y-6">
      <PageHeader
        title={supplier.name}
        backHref="/suppliers"
        crumbs={[{ label: "Suppliers", href: "/suppliers" }, { label: supplier.code }]}
        status={<GenericStatusBadge status={supplier.status} />}
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{supplier.code}</span>
            <span className="text-border">·</span>
            <Badge variant="secondary">{supplier.supplier_type_name ?? "—"}</Badge>
            <span className="text-border">·</span>
            <span>Since {formatDate(supplier.created_at)}</span>
          </span>
        }
        actions={<ScoreSupplierDialog supplierId={supplier.id} supplierName={supplier.name} />}
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile
          label="Payable"
          value={formatMoney(supplier.outstanding_minor)}
          hint="Outstanding balance"
          icon={<Receipt className="size-4" />}
          accent={supplier.outstanding_minor > 0 ? "warning" : "success"}
        />
        <StatTile
          label="Latest score"
          value={supplier.latest_score != null ? `${supplier.latest_score}/5` : "—"}
          hint={`${formatNumber(supplier.evaluation_count)} evaluation${supplier.evaluation_count === 1 ? "" : "s"}`}
          icon={<Star className="size-4" />}
          accent={supplier.latest_score != null && supplier.latest_score >= 4 ? "success" : "none"}
        />
        <StatTile label="GSTIN" value={supplier.gstin || "—"} hint="Tax registration" />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field icon={<Phone className="size-4" />} label="Phone" value={supplier.phone ?? ""} />
            <Field icon={<Mail className="size-4" />} label="Email" value={supplier.email ?? ""} />
            <Field
              icon={<MapPin className="size-4" />}
              label="Address"
              value={[supplier.address, supplier.city, supplier.state].filter(Boolean).join(", ")}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Evaluations</CardTitle>
          </CardHeader>
          <CardContent>
            {evaluations.length === 0 ? (
              <EmptyState
                icon={<Star className="size-8" strokeWidth={1.5} />}
                title="No evaluations yet"
                description="Score this supplier on quality, price and reliability."
              />
            ) : (
              <ul className="space-y-3">
                {evaluations.map((e) => (
                  <li key={e.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                    <div>
                      <p className="font-medium">
                        Overall {e.overall_score}/5
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Q {e.quality_score} · P {e.price_score} · R {e.reliability_score}
                        {e.notes ? ` · ${e.notes}` : ""}
                      </p>
                    </div>
                    <span className="text-muted-foreground">{formatDate(e.evaluated_on)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
