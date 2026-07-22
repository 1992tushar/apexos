"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Star } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { SupplierEvaluation } from "@/lib/dto";
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
import { useToast } from "@/components/ui/toaster";

const score = z.coerce.number().int().min(0, "0–5").max(5, "0–5");
const schema = z.object({
  quality_score: score,
  price_score: score,
  reliability_score: score,
  notes: z.string().optional().default(""),
});

type FormValues = z.input<typeof schema>;

/** Dialog to record a vendor evaluation (quality / price / reliability, 0–5). */
export function ScoreSupplierDialog({ supplierId, supplierName }: { supplierId: string; supplierName: string }) {
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { quality_score: 4, price_score: 4, reliability_score: 4, notes: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.parse(values);
    try {
      await api.post<SupplierEvaluation>("/supplier-evaluations", {
        supplier_id: supplierId,
        quality_score: parsed.quality_score,
        price_score: parsed.price_score,
        reliability_score: parsed.reliability_score,
        notes: parsed.notes,
      });
      toast({ title: "Evaluation recorded", description: supplierName, variant: "success" });
      setOpen(false);
      reset();
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not record evaluation", description: message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Star className="size-4" /> Evaluate
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Evaluate supplier</DialogTitle>
          <DialogDescription>{supplierName} · score each dimension 0–5.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={onSubmit}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onSubmit();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-3 gap-4">
            {(["quality_score", "price_score", "reliability_score"] as const).map((f) => (
              <div key={f} className="space-y-1.5">
                <Label htmlFor={f} className="capitalize">
                  {f.replace("_score", "")}
                </Label>
                <Input
                  id={f}
                  type="number"
                  min={0}
                  max={5}
                  className="text-right tabular-nums"
                  {...register(f)}
                />
                {errors[f] ? <p className="text-sm text-destructive">{errors[f]?.message}</p> : null}
              </div>
            ))}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="notes">Notes</Label>
            <Input id="notes" placeholder="Optional" {...register("notes")} />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Save evaluation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
