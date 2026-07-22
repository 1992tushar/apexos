"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Customer, MasterRow } from "@/lib/dto";
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
  name: z.string().min(2, "Name is required"),
  customer_type_id: z.string().min(1, "Select a customer type"),
  phone: z.string().optional().default(""),
  email: z.string().email("Enter a valid email").or(z.literal("")).default(""),
  gstin: z.string().optional().default(""),
  billing_address: z.string().optional().default(""),
  city: z.string().optional().default(""),
  state: z.string().optional().default(""),
  credit_limit_rupees: z.coerce.number().min(0, "Must be ≥ 0").default(0),
  payment_terms_days: z.coerce.number().int().min(0).default(0),
});

type FormValues = z.input<typeof schema>;

export function NewCustomerDialog({ customerTypes }: { customerTypes: MasterRow[] }) {
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
    defaultValues: { credit_limit_rupees: 0, payment_terms_days: 30 },
  });

  const typeId = watch("customer_type_id");

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<Customer>("/customers", {
        name: parsed.name,
        customer_type_id: parsed.customer_type_id,
        phone: parsed.phone,
        email: parsed.email,
        gstin: parsed.gstin,
        billing_address: parsed.billing_address,
        city: parsed.city,
        state: parsed.state,
        credit_limit_minor: Math.round(parsed.credit_limit_rupees * 100),
        payment_terms_days: parsed.payment_terms_days,
      });
      toast({ title: "Customer created", description: parsed.name, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create customer", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New customer
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>New customer</DialogTitle>
          <DialogDescription>Add a customer to the directory. A code is assigned automatically.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={onSubmit}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onSubmit();
          }}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" placeholder="Blue Café" {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label>Customer type</Label>
            <Select value={typeId} onValueChange={(v) => setValue("customer_type_id", v, { shouldValidate: true })}>
              <SelectTrigger>
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent>
                {customerTypes.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.customer_type_id ? (
              <p className="text-sm text-destructive">{errors.customer_type_id.message}</p>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" placeholder="+91…" {...register("phone")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="name@company.com" {...register("email")} />
              {errors.email ? <p className="text-sm text-destructive">{errors.email.message}</p> : null}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="gstin">GSTIN</Label>
            <Input id="gstin" placeholder="22AAAAA0000A1Z5" {...register("gstin")} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="billing_address">Billing address</Label>
            <Input id="billing_address" placeholder="Street, area" {...register("billing_address")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="city">City</Label>
              <Input id="city" {...register("city")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="state">State</Label>
              <Input id="state" {...register("state")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="credit_limit_rupees">Credit limit (₹)</Label>
              <Input
                id="credit_limit_rupees"
                type="number"
                min={0}
                step="0.01"
                className="text-right tabular-nums"
                {...register("credit_limit_rupees")}
              />
              {errors.credit_limit_rupees ? (
                <p className="text-sm text-destructive">{errors.credit_limit_rupees.message}</p>
              ) : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="payment_terms_days">Payment terms (days)</Label>
              <Input
                id="payment_terms_days"
                type="number"
                min={0}
                className="text-right tabular-nums"
                {...register("payment_terms_days")}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create customer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
