"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import type { Product, PurchaseOrderDetail, Supplier } from "@/lib/dto";
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
import { useToast } from "@/components/ui/toaster";

const schema = z.object({
  supplier_id: z.string().min(1, "Select a supplier"),
  order_date: z.string().optional().default(""),
  lines: z
    .array(
      z.object({
        product_id: z.string().min(1, "Pick a product"),
        qty: z.coerce.number().int().min(1, "Qty ≥ 1"),
      }),
    )
    .min(1, "Add at least one line"),
});

type FormValues = z.input<typeof schema>;

/** New purchase-order form. Line pricing previews the product's current buy price. */
export function NewPurchaseOrderForm({
  suppliers,
  products,
}: {
  suppliers: Supplier[];
  products: Product[];
}) {
  const router = useRouter();
  const { toast } = useToast();
  const productById = React.useMemo(
    () => new Map(products.map((p) => [p.id, p])),
    [products],
  );

  const buyPrice = (p?: Product) => (p?.purchase_price_minor ?? 0) || 0;

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { supplier_id: "", order_date: "", lines: [{ product_id: "", qty: 1 }] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");

  const subtotal = (lines ?? []).reduce((sum, l) => {
    const p = l.product_id ? productById.get(l.product_id) : undefined;
    const qty = Number(l.qty) || 0;
    return sum + buyPrice(p) * qty;
  }, 0);

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      const order = await api.post<PurchaseOrderDetail>("/purchase-orders", {
        supplier_id: parsed.supplier_id,
        order_date: parsed.order_date || undefined,
        lines: parsed.lines.map((l) => ({
          product_id: l.product_id,
          qty: l.qty,
          unit_price_minor: buyPrice(productById.get(l.product_id)) || undefined,
        })),
      });
      toast({ title: "Purchase order created", description: order.po_no, variant: "success" });
      router.push(`/purchase-orders/${order.id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create purchase order", description: message, variant: "destructive" });
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      onKeyDown={(e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onSubmit();
      }}
      className="space-y-6"
    >
      <Card>
        <CardHeader>
          <CardTitle>Order details</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Supplier</Label>
            <Select
              value={watch("supplier_id")}
              onValueChange={(v) => setValue("supplier_id", v, { shouldValidate: true })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a supplier" />
              </SelectTrigger>
              <SelectContent>
                {suppliers.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.supplier_id ? (
              <p className="text-sm text-destructive">{errors.supplier_id.message}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="order_date">Order date</Label>
            <Input id="order_date" type="date" {...register("order_date")} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Lines</CardTitle>
          <Button type="button" variant="outline" size="sm" onClick={() => append({ product_id: "", qty: 1 })}>
            <Plus className="size-4" /> Add line
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {fields.map((field, i) => {
            const product = lines?.[i]?.product_id ? productById.get(lines[i].product_id) : undefined;
            const qty = Number(lines?.[i]?.qty) || 0;
            const lineTotal = buyPrice(product) * qty;
            return (
              <div key={field.id} className="flex flex-wrap items-end gap-3 rounded-md border p-3">
                <div className="min-w-[220px] flex-1 space-y-1.5">
                  <Label>Product</Label>
                  <Select
                    value={lines?.[i]?.product_id}
                    onValueChange={(v) => setValue(`lines.${i}.product_id`, v, { shouldValidate: true })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a product" />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name} · {p.sku_code}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="w-24 space-y-1.5">
                  <Label>Qty</Label>
                  <Input
                    type="number"
                    min={1}
                    className="text-right tabular-nums"
                    {...register(`lines.${i}.qty`)}
                  />
                </div>
                <div className="w-28 space-y-1.5">
                  <Label>Buy price</Label>
                  <div className="flex h-9 items-center justify-end rounded-sm border bg-muted/40 px-3 text-sm tabular-nums text-muted-foreground">
                    {product ? formatMoney(buyPrice(product)) : "—"}
                  </div>
                </div>
                <div className="w-28 space-y-1.5">
                  <Label>Line total</Label>
                  <div className="flex h-9 items-center justify-end px-1 text-sm font-medium tabular-nums">
                    {formatMoney(lineTotal)}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Remove line"
                  onClick={() => (fields.length > 1 ? remove(i) : undefined)}
                  disabled={fields.length <= 1}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            );
          })}
          {errors.lines?.message ? (
            <p className="text-sm text-destructive">{errors.lines.message}</p>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between rounded-lg border bg-card p-4">
        <div className="text-sm text-muted-foreground">
          Subtotal (before tax)
          <span className="ml-2 text-base font-semibold tabular-nums text-foreground">
            {formatMoney(subtotal)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" onClick={() => router.push("/purchase-orders")}>
            Cancel
          </Button>
          <Button type="submit" loading={isSubmitting}>
            Create PO
          </Button>
        </div>
      </div>
    </form>
  );
}
