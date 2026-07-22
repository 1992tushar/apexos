"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeftRight } from "lucide-react";
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
  product_id: z.string().min(1, "Pick a product"),
  from_warehouse_id: z.string().min(1, "Pick a source"),
  to_warehouse_id: z.string().min(1, "Pick a destination"),
  qty: z.coerce.number().positive("Qty must be positive"),
});

type FormValues = z.input<typeof schema>;

/** Move stock between two warehouses (posts two ledger movements). */
export function TransferStockDialog({
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
    defaultValues: { product_id: "", from_warehouse_id: "", to_warehouse_id: "", qty: 1 },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    if (parsed.from_warehouse_id === parsed.to_warehouse_id) {
      toast({ title: "Source and destination must differ", variant: "destructive" });
      return;
    }
    try {
      await api.post("/inventory/transfers", {
        product_id: parsed.product_id,
        from_warehouse_id: parsed.from_warehouse_id,
        to_warehouse_id: parsed.to_warehouse_id,
        qty: parsed.qty,
      });
      toast({ title: "Stock transferred", variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not transfer", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <ArrowLeftRight className="size-4" /> Transfer
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Transfer stock</DialogTitle>
          <DialogDescription>Move stock from one warehouse to another.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
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
              <Label>From</Label>
              <Select value={watch("from_warehouse_id")} onValueChange={(v) => setValue("from_warehouse_id", v, { shouldValidate: true })}>
                <SelectTrigger>
                  <SelectValue placeholder="Source" />
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
              <Label>To</Label>
              <Select value={watch("to_warehouse_id")} onValueChange={(v) => setValue("to_warehouse_id", v, { shouldValidate: true })}>
                <SelectTrigger>
                  <SelectValue placeholder="Destination" />
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
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="qty">Quantity</Label>
            <Input id="qty" type="number" min={1} step="1" className="text-right tabular-nums" {...register("qty")} />
            {errors.qty ? <p className="text-sm text-destructive">{errors.qty.message}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Transfer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
