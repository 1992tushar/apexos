"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Lead, MasterKind } from "@/lib/dto";
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
  company_name: z.string().min(2, "Company is required"),
  contact_name: z.string().optional().default(""),
  city: z.string().optional().default(""),
  source: z.string().optional().default(""),
  customer_type_id: z.string().optional().default(""),
});

type FormValues = z.input<typeof schema>;

export function NewLeadDialog({ customerTypes }: { customerTypes: MasterKind[] }) {
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
    defaultValues: { company_name: "", contact_name: "", city: "", source: "", customer_type_id: NONE },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<Lead>("/leads", {
        company_name: parsed.company_name,
        contact_name: parsed.contact_name || undefined,
        city: parsed.city || undefined,
        source: parsed.source || undefined,
        customer_type_id:
          parsed.customer_type_id && parsed.customer_type_id !== NONE ? parsed.customer_type_id : undefined,
      });
      toast({ title: "Lead created", description: parsed.company_name, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not create lead", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New lead
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>New lead</DialogTitle>
          <DialogDescription>Capture a prospect. Set a type so it can convert to a customer.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="company_name">Company</Label>
            <Input id="company_name" placeholder="Sunrise Banquets" {...register("company_name")} />
            {errors.company_name ? <p className="text-sm text-destructive">{errors.company_name.message}</p> : null}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="contact_name">Contact</Label>
              <Input id="contact_name" {...register("contact_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="city">City</Label>
              <Input id="city" {...register("city")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="source">Source</Label>
              <Input id="source" placeholder="Referral" {...register("source")} />
            </div>
            <div className="space-y-1.5">
              <Label>Customer type</Label>
              <Select value={watch("customer_type_id")} onValueChange={(v) => setValue("customer_type_id", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Optional" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Unset</SelectItem>
                  {customerTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create lead
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
