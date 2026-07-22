"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import type { BillRow } from "@/lib/dto";
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

const METHODS = [
  { value: "cash", label: "Cash" },
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "upi", label: "UPI" },
  { value: "cheque", label: "Cheque" },
  { value: "card", label: "Card" },
];

const schema = z.object({
  amount_rupees: z.coerce.number().positive("Enter an amount"),
  method: z.string().min(1, "Select a method"),
});

type FormValues = z.input<typeof schema>;

/** Record an outbound payment against a supplier bill (payment direction=out). */
export function RecordSupplierPaymentDialog({ bill }: { bill: BillRow }) {
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
    defaultValues: { amount_rupees: bill.balance_minor / 100, method: "bank_transfer" },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post(`/bills/${bill.id}/payments`, {
        amount_minor: Math.round(parsed.amount_rupees * 100),
        method: parsed.method,
      });
      toast({ title: "Payment recorded", description: bill.bill_no, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not record payment", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) reset({ amount_rupees: bill.balance_minor / 100, method: "bank_transfer" });
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" onClick={(e) => e.stopPropagation()}>
          Pay supplier
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Pay supplier</DialogTitle>
          <DialogDescription>
            {bill.bill_no} · {bill.supplier_name} · Balance {formatMoney(bill.balance_minor)}
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={onSubmit}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onSubmit();
          }}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="amount_rupees">Amount (₹)</Label>
            <Input
              id="amount_rupees"
              type="number"
              min={0}
              step="0.01"
              className="text-right tabular-nums"
              {...register("amount_rupees")}
            />
            {errors.amount_rupees ? (
              <p className="text-sm text-destructive">{errors.amount_rupees.message}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label>Method</Label>
            <Select value={watch("method")} onValueChange={(v) => setValue("method", v, { shouldValidate: true })}>
              <SelectTrigger>
                <SelectValue placeholder="Select a method" />
              </SelectTrigger>
              <SelectContent>
                {METHODS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.method ? <p className="text-sm text-destructive">{errors.method.message}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Record payment
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
