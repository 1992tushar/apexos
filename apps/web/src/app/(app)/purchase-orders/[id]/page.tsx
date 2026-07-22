import { notFound } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { PurchaseOrderDetail } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { PurchaseOrderStatusBadge, BillStatusBadge } from "@/components/shared/status-badge";
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
import { PoActions } from "@/features/procurement/po-actions";

export const dynamic = "force-dynamic";

async function getOrder(id: string): Promise<PurchaseOrderDetail | null> {
  try {
    return await api.get<PurchaseOrderDetail>(`/purchase-orders/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    return null;
  }
}

export default async function PurchaseOrderDetailPage({ params }: { params: { id: string } }) {
  const order = await getOrder(params.id);
  if (!order) notFound();

  const receipts = order.goods_receipts ?? [];
  const bill = order.bills?.[0] ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={order.po_no}
        backHref="/purchase-orders"
        crumbs={[{ label: "Purchase Orders", href: "/purchase-orders" }, { label: order.po_no }]}
        status={<PurchaseOrderStatusBadge status={order.status} />}
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <Link href={`/suppliers/${order.supplier_id}`} className="font-medium text-foreground hover:underline">
              {order.supplier_name}
            </Link>
            <span className="text-border">·</span>
            <span>{formatDate(order.order_date)}</span>
            <span className="text-border">·</span>
            <span className="font-semibold text-foreground">{formatMoney(order.total_minor)}</span>
          </span>
        }
        actions={<PoActions id={order.id} status={order.status} />}
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
                <TableHead className="text-right">Ordered</TableHead>
                <TableHead className="text-right">Received</TableHead>
                <TableHead className="text-right">Buy price</TableHead>
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
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {formatNumber(l.qty_received)}
                  </TableCell>
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
                <TableCell colSpan={6} className="text-right text-muted-foreground">
                  Subtotal
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(order.subtotal_minor)}</TableCell>
              </TableRow>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="text-right text-muted-foreground">
                  Tax
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(order.tax_minor)}</TableCell>
              </TableRow>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="text-right font-semibold">
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
            <CardTitle>Goods receipts</CardTitle>
          </CardHeader>
          <CardContent>
            {receipts.length > 0 ? (
              <ul className="space-y-2 text-sm">
                {receipts.map((r) => (
                  <li key={r.id} className="flex items-center justify-between">
                    <span className="font-mono text-xs text-muted-foreground">{r.receipt_no}</span>
                    <span className="flex items-center gap-2">
                      <span className="capitalize">{r.status}</span>
                      {r.received_at ? (
                        <span className="text-muted-foreground">{formatDate(r.received_at)}</span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No goods received yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Bill</CardTitle>
          </CardHeader>
          <CardContent>
            {bill ? (
              <Link href="/finance" className="flex items-center justify-between rounded-md text-sm hover:underline">
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">{bill.bill_no}</span>
                  <BillStatusBadge status={bill.status} />
                </span>
                <span className="font-medium tabular-nums">{formatMoney(bill.total_minor)}</span>
              </Link>
            ) : (
              <p className="text-sm text-muted-foreground">No bill created yet.</p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
