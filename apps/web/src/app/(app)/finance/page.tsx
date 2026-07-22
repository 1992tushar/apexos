import { api } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import type { BillRow, InvoiceRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { InvoicesTable } from "@/features/finance/invoices-table";
import { BillsTable } from "@/features/finance/bills-table";

export const dynamic = "force-dynamic";

// Both endpoints return plain arrays, not paginated envelopes.
async function load(): Promise<{ invoices: InvoiceRow[]; bills: BillRow[] }> {
  const [invoices, bills] = await Promise.all([
    api.get<InvoiceRow[]>("/invoices").catch(() => []),
    api.get<BillRow[]>("/bills").catch(() => []),
  ]);
  return { invoices, bills };
}

export default async function FinancePage() {
  const { invoices, bills } = await load();
  const receivable = invoices.reduce((sum, i) => sum + i.balance_minor, 0);
  const payable = bills.reduce((sum, b) => sum + b.balance_minor, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Finance"
        crumbs={[{ label: "Receivables & Payables" }]}
        meta={`${invoices.length} invoice${invoices.length === 1 ? "" : "s"} · ${bills.length} bill${bills.length === 1 ? "" : "s"}`}
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatTile
          label="Receivable"
          value={formatMoney(receivable)}
          hint="Outstanding from customers"
          accent={receivable > 0 ? "warning" : "success"}
        />
        <StatTile
          label="Payable"
          value={formatMoney(payable)}
          hint="Outstanding to suppliers"
          accent={payable > 0 ? "destructive" : "success"}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Receivables · Invoices</h2>
        <InvoicesTable invoices={invoices} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Payables · Bills</h2>
        <BillsTable bills={bills} />
      </section>
    </div>
  );
}
