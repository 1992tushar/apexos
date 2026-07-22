"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { MasterRow, Product } from "@/lib/dto";
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
  category_id: z.string().min(1, "Select a category"),
  brand_id: z.string().min(1, "Select a brand"),
  specification: z.string().optional().default(""),
  uom_id: z.string().min(1, "Select a unit"),
  procurement_model_id: z.string().min(1, "Select a model"),
  launch_phase: z.string().optional().default("active"),
  selling_price_rupees: z.coerce.number().min(0, "Must be ≥ 0").default(0),
  purchase_price_rupees: z.coerce.number().min(0, "Must be ≥ 0").default(0),
  reorder_level: z.coerce.number().int().min(0).default(0),
});

type FormValues = z.input<typeof schema>;

type Masters = {
  categories: MasterRow[];
  brands: MasterRow[];
  uoms: MasterRow[];
  procurementModels: MasterRow[];
};

function SelectField({
  label,
  value,
  onChange,
  options,
  error,
  placeholder,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string) => void;
  options: MasterRow[];
  error?: string;
  placeholder: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.id} value={o.id}>
              {o.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}

export function NewProductDialog({ masters }: { masters: Masters }) {
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
    defaultValues: { launch_phase: "active", reorder_level: 0 },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<Product>("/products", {
        name: parsed.name,
        category_id: parsed.category_id,
        brand_id: parsed.brand_id,
        specification: parsed.specification,
        uom_id: parsed.uom_id,
        procurement_model_id: parsed.procurement_model_id,
        launch_phase: parsed.launch_phase,
        selling_price_minor: Math.round(parsed.selling_price_rupees * 100),
        purchase_price_minor: Math.round(parsed.purchase_price_rupees * 100),
        reorder_level: parsed.reorder_level,
      });
      toast({ title: "Product created", description: parsed.name, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create product", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New product
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>New product</DialogTitle>
          <DialogDescription>Create a SKU. The SKU code is generated from brand + category.</DialogDescription>
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
            <Input id="name" placeholder="Aura Toilet Roll" {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SelectField
              label="Category"
              placeholder="Category"
              value={watch("category_id")}
              onChange={(v) => setValue("category_id", v, { shouldValidate: true })}
              options={masters.categories}
              error={errors.category_id?.message}
            />
            <SelectField
              label="Brand"
              placeholder="Brand"
              value={watch("brand_id")}
              onChange={(v) => setValue("brand_id", v, { shouldValidate: true })}
              options={masters.brands}
              error={errors.brand_id?.message}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="specification">Specification</Label>
            <Input id="specification" placeholder="3-ply, 200 pulls" {...register("specification")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SelectField
              label="Unit of measure"
              placeholder="UOM"
              value={watch("uom_id")}
              onChange={(v) => setValue("uom_id", v, { shouldValidate: true })}
              options={masters.uoms}
              error={errors.uom_id?.message}
            />
            <SelectField
              label="Procurement model"
              placeholder="Model"
              value={watch("procurement_model_id")}
              onChange={(v) => setValue("procurement_model_id", v, { shouldValidate: true })}
              options={masters.procurementModels}
              error={errors.procurement_model_id?.message}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="selling_price_rupees">Selling (₹)</Label>
              <Input
                id="selling_price_rupees"
                type="number"
                min={0}
                step="0.01"
                className="text-right tabular-nums"
                {...register("selling_price_rupees")}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="purchase_price_rupees">Purchase (₹)</Label>
              <Input
                id="purchase_price_rupees"
                type="number"
                min={0}
                step="0.01"
                className="text-right tabular-nums"
                {...register("purchase_price_rupees")}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="reorder_level">Reorder</Label>
              <Input
                id="reorder_level"
                type="number"
                min={0}
                className="text-right tabular-nums"
                {...register("reorder_level")}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create product
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
