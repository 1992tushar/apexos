import { Badge, type BadgeProps } from "@/components/ui/badge";
import type {
  BillStatus,
  InvoiceStatus,
  PurchaseOrderStatus,
  SalesOrderStatus,
} from "@/lib/dto";

type Variant = NonNullable<BadgeProps["variant"]>;

const SALES_ORDER: Record<SalesOrderStatus, { label: string; variant: Variant }> = {
  draft: { label: "Draft", variant: "muted" },
  confirmed: { label: "Confirmed", variant: "default" },
  fulfilled: { label: "Fulfilled", variant: "success" },
  invoiced: { label: "Invoiced", variant: "success" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

const PURCHASE_ORDER: Record<PurchaseOrderStatus, { label: string; variant: Variant }> = {
  draft: { label: "Draft", variant: "muted" },
  confirmed: { label: "Confirmed", variant: "default" },
  partially_received: { label: "Partially received", variant: "warning" },
  received: { label: "Received", variant: "success" },
  billed: { label: "Billed", variant: "success" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

const INVOICE: Record<InvoiceStatus, { label: string; variant: Variant }> = {
  issued: { label: "Issued", variant: "default" },
  part_paid: { label: "Part paid", variant: "warning" },
  paid: { label: "Paid", variant: "success" },
};

const BILL: Record<BillStatus, { label: string; variant: Variant }> = {
  issued: { label: "Issued", variant: "default" },
  part_paid: { label: "Part paid", variant: "warning" },
  paid: { label: "Paid", variant: "success" },
};

export function SalesOrderStatusBadge({ status }: { status: SalesOrderStatus }) {
  const s = SALES_ORDER[status] ?? { label: status, variant: "muted" as Variant };
  return (
    <Badge variant={s.variant} dot>
      {s.label}
    </Badge>
  );
}

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  const s = INVOICE[status] ?? { label: status, variant: "muted" as Variant };
  return (
    <Badge variant={s.variant} dot>
      {s.label}
    </Badge>
  );
}

export function PurchaseOrderStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  const s = PURCHASE_ORDER[status] ?? { label: status, variant: "muted" as Variant };
  return (
    <Badge variant={s.variant} dot>
      {s.label}
    </Badge>
  );
}

export function BillStatusBadge({ status }: { status: BillStatus }) {
  const s = BILL[status] ?? { label: status, variant: "muted" as Variant };
  return (
    <Badge variant={s.variant} dot>
      {s.label}
    </Badge>
  );
}

/** Generic active/inactive style badge for master records. */
export function GenericStatusBadge({ status }: { status: string }) {
  const active = status?.toLowerCase() === "active";
  return (
    <Badge variant={active ? "success" : "muted"} dot>
      {status ? status[0].toUpperCase() + status.slice(1) : "—"}
    </Badge>
  );
}
