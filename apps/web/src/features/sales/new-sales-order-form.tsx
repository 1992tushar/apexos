"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import type { Customer, Product, SalesOrderDetail } from "@/lib/dto";
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
  customer_id: z.string().min(1, "Select a customer"),
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

export function NewSalesOrderForm({
  customers,
  products,
}: {
  customers: Customer[];
  products: Product[];
}) {
  const router = useRouter();
  const { toast } = useToast();
  const priceById = React.useMemo(
    () => new Map(products.map((p) => [p.id, p])),
    [products],
  );

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { customer_id: "", order_date: "", lines: [{ product_id: "", qty: 1 }] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");

  const subtotal = (lines ?? []).reduce((sum, l) => {
    const p = l.product_id ? priceById.get(l.product_id) : undefined;
    const qty = Number(l.qty) || 0;
    return sum + (p ? p.selling_price_minor * qty : 0);
  }, 0);

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      const order = await api.post<SalesOrderDetail>("/sales-orders", {
        customer_id: parsed.customer_id,
        order_date: parsed.order_date || undefined,
        lines: parsed.lines.map((l) => ({
          product_id: l.product_id,
          qty: l.qty,
          unit_price_minor: priceById.get(l.product_id)?.selling_price_minor,
        })),
      });
      toast({ title: "Sales order created", description: order.order_no, variant: "success" });
      router.push(`/sales/${order.id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create order", description: message, variant: "destructive" });
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
            <Label>Customer</Label>
            <Select
              value={watch("customer_id")}
              onValueChange={(v) => setValue("customer_id", v, { shouldValidate: true })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a customer" />
              </SelectTrigger>
              <SelectContent>
                {customers.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.customer_id ? (
              <p className="text-sm text-destructive">{errors.customer_id.message}</p>
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
            const product = lines?.[i]?.product_id ? priceById.get(lines[i].product_id) : undefined;
            const qty = Number(lines?.[i]?.qty) || 0;
            const lineTotal = product ? product.selling_price_minor * qty : 0;
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
                  <Label>Unit price</Label>
                  <div className="flex h-9 items-center justify-end rounded-sm border bg-muted/40 px-3 text-sm tabular-nums text-muted-foreground">
                    {product ? formatMoney(product.selling_price_minor) : "—"}
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
          <Button type="button" variant="ghost" onClick={() => router.push("/sales")}>
            Cancel
          </Button>
          <Button type="submit" loading={isSubmitting}>
            Create order
          </Button>
        </div>
      </div>
    </form>
  );
}
