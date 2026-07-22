"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { MasterRow, Supplier } from "@/lib/dto";
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
  supplier_type_id: z.string().min(1, "Select a supplier type"),
  phone: z.string().optional().default(""),
  email: z.string().email("Enter a valid email").or(z.literal("")).default(""),
  gstin: z.string().optional().default(""),
  address: z.string().optional().default(""),
  city: z.string().optional().default(""),
  state: z.string().optional().default(""),
});

type FormValues = z.input<typeof schema>;

/** Dialog to create a supplier. A code is assigned by the server. */
export function NewSupplierDialog({ supplierTypes }: { supplierTypes: MasterRow[] }) {
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
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const typeId = watch("supplier_type_id");

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<Supplier>("/suppliers", {
        name: parsed.name,
        supplier_type_id: parsed.supplier_type_id,
        phone: parsed.phone,
        email: parsed.email,
        gstin: parsed.gstin,
        address: parsed.address,
        city: parsed.city,
        state: parsed.state,
      });
      toast({ title: "Supplier created", description: parsed.name, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create supplier", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New supplier
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>New supplier</DialogTitle>
          <DialogDescription>Add a supplier to the directory. A code is assigned automatically.</DialogDescription>
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
            <Input id="name" placeholder="PaperWings Sanaswadi" {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label>Supplier type</Label>
            <Select value={typeId} onValueChange={(v) => setValue("supplier_type_id", v, { shouldValidate: true })}>
              <SelectTrigger>
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent>
                {supplierTypes.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.supplier_type_id ? (
              <p className="text-sm text-destructive">{errors.supplier_type_id.message}</p>
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
            <Input id="gstin" placeholder="27AAECP1234A1Z5" {...register("gstin")} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="address">Address</Label>
            <Input id="address" placeholder="Street, area" {...register("address")} />
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

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create supplier
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
