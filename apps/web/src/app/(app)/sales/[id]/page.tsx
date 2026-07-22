import { notFound } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { SalesOrderDetail } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { SalesOrderStatusBadge, InvoiceStatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { OrderActions } from "@/features/sales/order-actions";

export const dynamic = "force-dynamic";

async function getOrder(id: string): Promise<SalesOrderDetail | null> {
  try {
    return await api.get<SalesOrderDetail>(`/sales-orders/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    return null;
  }
}

export default async function SalesOrderDetailPage({ params }: { params: { id: string } }) {
  const order = await getOrder(params.id);
  if (!order) notFound();

  // Backend returns arrays; the spine shows the latest fulfillment / invoice.
  const fulfillment = order.fulfillments?.[0] ?? null;
  const invoice = order.invoices?.[0] ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={order.order_no}
        backHref="/sales"
        crumbs={[{ label: "Sales Orders", href: "/sales" }, { label: order.order_no }]}
        status={<SalesOrderStatusBadge status={order.status} />}
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <Link href={`/customers/${order.customer_id}`} className="font-medium text-foreground hover:underline">
              {order.customer_name}
            </Link>
            <span className="text-border">·</span>
            <span>{formatDate(order.order_date)}</span>
            <span className="text-border">·</span>
            <span className="font-semibold text-foreground">{formatMoney(order.total_minor)}</span>
          </span>
        }
        actions={<OrderActions id={order.id} status={order.status} />}
      />

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>SKU</TableHead>
                <TableHead>Product</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Unit price</TableHead>
                <TableHead className="text-right">Tax</TableHead>
                <TableHead className="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {order.lines.map((l) => (
                <TableRow key={l.id} className="hover:bg-transparent">
                  <TableCell className="font-mono text-xs text-muted-foreground">{l.sku_code}</TableCell>
                  <TableCell className="font-medium">{l.product_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(l.qty)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatMoney(l.unit_price_minor)}</TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {(l.tax_rate_bps / 100).toFixed(1)}%
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium">
                    {formatMoney(l.line_total_minor)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5} className="text-right text-muted-foreground">
                  Subtotal
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(order.subtotal_minor)}</TableCell>
              </TableRow>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5} className="text-right text-muted-foreground">
                  Tax
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(order.tax_minor)}</TableCell>
              </TableRow>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5} className="text-right font-semibold">
                  Total
                </TableCell>
                <TableCell className="text-right text-base font-semibold tabular-nums">
                  {formatMoney(order.total_minor)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </CardContent>
      </Card>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Fulfillment</CardTitle>
          </CardHeader>
          <CardContent>
            {fulfillment ? (
              <div className="flex items-center justify-between text-sm">
                <span className="capitalize">{fulfillment.status}</span>
                {fulfillment.shipped_at ? (
                  <span className="text-muted-foreground">{formatDate(fulfillment.shipped_at)}</span>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Not yet fulfilled.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Invoice</CardTitle>
          </CardHeader>
          <CardContent>
            {invoice ? (
              <Link
                href={`/finance`}
                className="flex items-center justify-between rounded-md text-sm hover:underline"
              >
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">{invoice.invoice_no}</span>
                  <InvoiceStatusBadge status={invoice.status} />
                </span>
                <span className="font-medium tabular-nums">{formatMoney(invoice.total_minor)}</span>
              </Link>
            ) : (
              <p className="text-sm text-muted-foreground">No invoice created yet.</p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
