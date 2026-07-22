import { api } from "@/lib/api";
import type { GoodsReceiptRow } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { GoodsReceiptsTable } from "@/features/procurement/goods-receipts-table";

export const dynamic = "force-dynamic";

// GET /goods-receipts returns a plain array (list[GoodsReceiptListRow]).
async function load(): Promise<GoodsReceiptRow[]> {
  return api.get<GoodsReceiptRow[]>("/goods-receipts").catch(() => []);
}

export default async function ProcurementPage() {
  const receipts = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Procurement"
        crumbs={[{ label: "Goods Receipts" }]}
        meta={`${receipts.length} goods receipt${receipts.length === 1 ? "" : "s"}`}
      />
      <GoodsReceiptsTable receipts={receipts} />
    </div>
  );
}
