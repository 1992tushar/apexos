"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Category, MasterKind } from "@/lib/dto";
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

const NONE = "__none__";

const schema = z.object({
  code: z.string().min(1, "Code is required").max(4, "Max 4 chars"),
  name: z.string().min(2, "Name is required"),
  procurement_model_id: z.string().optional().default(""),
  parent_category_id: z.string().optional().default(""),
});

type FormValues = z.input<typeof schema>;

export function NewCategoryDialog({
  categories,
  procurementModels,
}: {
  categories: Category[];
  procurementModels: MasterKind[];
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
    defaultValues: { code: "", name: "", procurement_model_id: NONE, parent_category_id: NONE },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<Category>("/categories", {
        code: parsed.code,
        name: parsed.name,
        procurement_model_id:
          parsed.procurement_model_id && parsed.procurement_model_id !== NONE
            ? parsed.procurement_model_id
            : undefined,
        parent_category_id:
          parsed.parent_category_id && parsed.parent_category_id !== NONE
            ? parsed.parent_category_id
            : undefined,
      });
      toast({ title: "Category created", description: parsed.name, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create category", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New category
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>New category</DialogTitle>
          <DialogDescription>Categories roll up to a business unit (via their parent when set).</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="code">Code</Label>
              <Input id="code" placeholder="TIS" {...register("code")} />
              {errors.code ? <p className="text-sm text-destructive">{errors.code.message}</p> : null}
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input id="name" placeholder="Tissue & Paper" {...register("name")} />
              {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Procurement model</Label>
            <Select value={watch("procurement_model_id")} onValueChange={(v) => setValue("procurement_model_id", v)}>
              <SelectTrigger>
                <SelectValue placeholder="Optional" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>None</SelectItem>
                {procurementModels.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Parent category</Label>
            <Select value={watch("parent_category_id")} onValueChange={(v) => setValue("parent_category_id", v)}>
              <SelectTrigger>
                <SelectValue placeholder="Top level" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Top level</SelectItem>
                {categories.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create category
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
