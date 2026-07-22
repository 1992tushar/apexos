/**
 * Response DTOs for the ApexOS API (contract-pinned). Money fields are integer
 * minor units (paise) and must render through `formatMoney`.
 */

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

/** Generic master-data row (customer types, categories, brands, uoms, etc.). */
export type MasterRow = {
  id: string;
  name: string;
  code?: string;
};

export type SalesOrderStatus =
  | "draft"
  | "confirmed"
  | "fulfilled"
  | "invoiced"
  | "cancelled";

export type InvoiceStatus = "issued" | "part_paid" | "paid";

export type TopCustomer = {
  id: string;
  name: string;
  revenue_minor: number;
};

export type RevenuePoint = {
  date: string;
  amount_minor: number;
};

export type Activity = {
  id: string;
  verb: string;
  entity_type: string;
  summary: string;
  occurred_at: string;
};

export type DashboardSummary = {
  today_sales_minor: number;
  outstanding_receivables_minor: number;
  inventory_value_minor: number;
  low_stock_count: number;
  pending_sales_orders: number;
  pending_purchase_orders: number;
  top_customers: TopCustomer[];
  revenue_trend: RevenuePoint[];
  recent_activities: Activity[];
};

export type Customer = {
  id: string;
  code: string;
  name: string;
  customer_type_id: string;
  customer_type_name: string;
  phone: string;
  email: string;
  gstin: string;
  billing_address: string;
  city: string;
  state: string;
  credit_limit_minor: number;
  payment_terms_days: number;
  outstanding_minor: number;
  status: string;
  created_at: string;
};

export type Product = {
  id: string;
  sku_code: string;
  name: string;
  category_id: string;
  category_name: string;
  brand_id: string;
  brand_name: string;
  specification: string;
  uom_id: string;
  uom_code: string;
  procurement_model_id: string;
  procurement_model_name: string;
  launch_phase: string;
  status: string;
  selling_price_minor: number;
  purchase_price_minor: number;
  stock_on_hand: number;
};

export type SalesOrderRow = {
  id: string;
  order_no: string;
  customer_name: string;
  status: SalesOrderStatus;
  total_minor: number;
  order_date: string;
  line_count: number;
};

export type SalesOrderLine = {
  id: string;
  product_id: string;
  sku_code: string;
  product_name: string;
  qty: number;
  unit_price_minor: number;
  tax_rate_bps: number;
  line_total_minor: number;
};

export type SalesOrderDetail = {
  id: string;
  order_no: string;
  customer_id: string;
  customer_name: string | null;
  business_unit_id: string;
  status: SalesOrderStatus;
  order_date: string;
  lines: SalesOrderLine[];
  subtotal_minor: number;
  tax_minor: number;
  total_minor: number;
  fulfillments: {
    id: string;
    fulfillment_no: string;
    warehouse_id: string;
    status: string;
    shipped_at?: string | null;
  }[];
  invoices: {
    id: string;
    invoice_no: string;
    status: InvoiceStatus;
    total_minor: number;
  }[];
};

export type InvoiceRow = {
  id: string;
  invoice_no: string;
  customer_name: string;
  total_minor: number;
  paid_minor: number;
  balance_minor: number;
  status: InvoiceStatus;
  invoice_date: string;
  due_date: string;
};

export type StockRow = {
  product_id: string;
  sku_code: string;
  product_name: string;
  warehouse_id: string;
  warehouse_name: string;
  qty_on_hand: number;
  reorder_level: number;
  is_low: boolean;
};

export type Me = {
  id: string;
  email: string;
  role: string;
};

// --- Buy side (suppliers, procurement, bills) ---------------------------

export type PurchaseOrderStatus =
  | "draft"
  | "confirmed"
  | "partially_received"
  | "received"
  | "billed"
  | "cancelled";

export type BillStatus = "issued" | "part_paid" | "paid";

export type Supplier = {
  id: string;
  code: string;
  name: string;
  supplier_type_id: string;
  supplier_type_name: string | null;
  phone: string | null;
  email: string | null;
  gstin: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  outstanding_minor: number;
  latest_score: number | null;
  evaluation_count: number;
  status: string;
  created_at: string;
};

export type SupplierEvaluation = {
  id: string;
  supplier_id: string;
  quality_score: number;
  price_score: number;
  reliability_score: number;
  overall_score: number;
  notes: string | null;
  evaluated_on: string;
};

export type PurchaseOrderRow = {
  id: string;
  po_no: string;
  supplier_name: string | null;
  status: PurchaseOrderStatus;
  total_minor: number;
  order_date: string;
  line_count: number;
};

export type PurchaseOrderLine = {
  id: string;
  product_id: string;
  product_name: string | null;
  sku_code: string | null;
  qty: number;
  qty_received: number;
  unit_price_minor: number;
  tax_rate_bps: number;
  line_subtotal_minor: number;
  line_tax_minor: number;
  line_total_minor: number;
};

export type PurchaseOrderDetail = {
  id: string;
  po_no: string;
  supplier_id: string;
  supplier_name: string | null;
  business_unit_id: string;
  status: PurchaseOrderStatus;
  order_date: string;
  subtotal_minor: number;
  tax_minor: number;
  total_minor: number;
  lines: PurchaseOrderLine[];
  goods_receipts: {
    id: string;
    receipt_no: string;
    warehouse_id: string;
    status: string;
    received_at: string | null;
  }[];
  bills: {
    id: string;
    bill_no: string;
    status: BillStatus;
    total_minor: number;
  }[];
};

export type GoodsReceiptRow = {
  id: string;
  receipt_no: string;
  purchase_order_id: string;
  po_no: string | null;
  supplier_name: string | null;
  warehouse_name: string | null;
  status: string;
  received_at: string | null;
  line_count: number;
};

export type BillRow = {
  id: string;
  bill_no: string;
  supplier_name: string | null;
  total_minor: number;
  paid_minor: number;
  balance_minor: number;
  status: BillStatus;
  bill_date: string;
  due_date: string | null;
};

export type BillLine = {
  id: string;
  product_id: string;
  product_name: string | null;
  qty: number;
  unit_price_minor: number;
  tax_rate_bps: number;
  line_subtotal_minor: number;
  line_tax_minor: number;
  line_total_minor: number;
};

export type BillDetail = {
  id: string;
  bill_no: string;
  supplier_id: string;
  supplier_name: string | null;
  purchase_order_id: string | null;
  status: BillStatus;
  bill_date: string;
  due_date: string | null;
  subtotal_minor: number;
  tax_minor: number;
  total_minor: number;
  paid_minor: number;
  balance_minor: number;
  lines: BillLine[];
};
