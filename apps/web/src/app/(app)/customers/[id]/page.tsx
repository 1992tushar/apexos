import { notFound } from "next/navigation";
import { CreditCard, Mail, MapPin, Phone, Receipt } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { Customer } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { GenericStatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

async function getCustomer(id: string): Promise<Customer | null> {
  try {
    return await api.get<Customer>(`/customers/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    return null;
  }
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

export default async function CustomerDetailPage({ params }: { params: { id: string } }) {
  const customer = await getCustomer(params.id);
  if (!customer) notFound();

  const creditUsedPct =
    customer.credit_limit_minor > 0
      ? Math.min(100, Math.round((customer.outstanding_minor / customer.credit_limit_minor) * 100))
      : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title={customer.name}
        backHref="/customers"
        crumbs={[{ label: "Customers", href: "/customers" }, { label: customer.code }]}
        status={<GenericStatusBadge status={customer.status} />}
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{customer.code}</span>
            <span className="text-border">·</span>
            <Badge variant="secondary">{customer.customer_type_name}</Badge>
            <span className="text-border">·</span>
            <span>Since {formatDate(customer.created_at)}</span>
          </span>
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile
          label="Outstanding"
          value={formatMoney(customer.outstanding_minor)}
          hint="Receivable balance"
          icon={<Receipt className="size-4" />}
          accent={customer.outstanding_minor > 0 ? "warning" : "success"}
        />
        <StatTile
          label="Credit Limit"
          value={formatMoney(customer.credit_limit_minor)}
          hint={`${creditUsedPct}% utilised`}
          icon={<CreditCard className="size-4" />}
          accent={creditUsedPct >= 90 ? "destructive" : "none"}
        />
        <StatTile
          label="Payment Terms"
          value={`${formatNumber(customer.payment_terms_days)} days`}
          hint="Net due window"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field icon={<Phone className="size-4" />} label="Phone" value={customer.phone} />
            <Field icon={<Mail className="size-4" />} label="Email" value={customer.email} />
            <Field
              icon={<MapPin className="size-4" />}
              label="Billing address"
              value={[customer.billing_address, customer.city, customer.state].filter(Boolean).join(", ")}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Credit policy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Credit utilisation</span>
              <span className="font-medium tabular-nums">{creditUsedPct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={
                  creditUsedPct >= 90
                    ? "h-full rounded-full bg-destructive"
                    : creditUsedPct >= 70
                      ? "h-full rounded-full bg-warning"
                      : "h-full rounded-full bg-primary"
                }
                style={{ width: `${creditUsedPct}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-4 pt-2">
              <Field icon={<Receipt className="size-4" />} label="GSTIN" value={customer.gstin} />
              <Field icon={<CreditCard className="size-4" />} label="State" value={customer.state} />
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
