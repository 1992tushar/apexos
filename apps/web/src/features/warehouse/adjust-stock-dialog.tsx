"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { SlidersHorizontal } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Product, Warehouse } from "@/lib/dto";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toaster";

const schema = z.object({
  mode: z.enum(["ADJUSTMENT", "COUNT"]),
  product_id: z.string().min(1, "Pick a product"),
  warehouse_id: z.string().min(1, "Pick a warehouse"),
  amount: z.coerce.number(),
});

type FormValues = z.input<typeof schema>;

/** Manual stock adjustment (signed delta) or cycle count (absolute counted qty). */
export function AdjustStockDialog({
  warehouses,
  products,
}: {
  warehouses: Warehouse[];
  products: Product[];
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "ADJUSTMENT", product_id: "", warehouse_id: "", amount: 0 },
  });

  const mode = watch("mode");

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      if (parsed.mode === "COUNT") {
        await api.post("/inventory/counts", {
          product_id: parsed.product_id,
          warehouse_id: parsed.warehouse_id,
          counted_qty: parsed.amount,
        });
      } else {
        await api.post("/inventory/adjustments", {
          product_id: parsed.product_id,
          warehouse_id: parsed.warehouse_id,
          qty_delta: parsed.amount,
          reason: "ADJUSTMENT",
        });
      }
      toast({ title: parsed.mode === "COUNT" ? "Count reconciled" : "Stock adjusted", variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not apply", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <SlidersHorizontal className="size-4" /> Adjust / Count
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Adjust or count stock</DialogTitle>
          <DialogDescription>
            An adjustment applies a signed change; a count reconciles on-hand to a physical number.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Mode</Label>
            <Select value={mode} onValueChange={(v) => setValue("mode", v as "ADJUSTMENT" | "COUNT")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ADJUSTMENT">Adjustment (signed delta)</SelectItem>
                <SelectItem value="COUNT">Cycle count (absolute)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Product</Label>
            <Select value={watch("product_id")} onValueChange={(v) => setValue("product_id", v, { shouldValidate: true })}>
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
            {errors.product_id ? <p className="text-sm text-destructive">{errors.product_id.message}</p> : null}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Warehouse</Label>
              <Select value={watch("warehouse_id")} onValueChange={(v) => setValue("warehouse_id", v, { shouldValidate: true })}>
                <SelectTrigger>
                  <SelectValue placeholder="Warehouse" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="amount">{mode === "COUNT" ? "Counted qty" : "Delta (±)"}</Label>
              <Input id="amount" type="number" step="1" className="text-right tabular-nums" {...register("amount")} />
              {errors.amount ? <p className="text-sm text-destructive">{errors.amount.message}</p> : null}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Apply
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
