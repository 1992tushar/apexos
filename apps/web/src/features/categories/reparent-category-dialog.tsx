"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Category } from "@/lib/dto";
import { Button } from "@/components/ui/button";
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

const TOP = "__top__";

/** Move a category under a new parent (or to top level). */
export function ReparentCategoryDialog({
  category,
  categories,
}: {
  category: Category;
  categories: Category[];
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [parent, setParent] = React.useState<string>(category.parent_category_id ?? TOP);
  const [pending, setPending] = React.useState(false);

  const options = categories.filter((c) => c.id !== category.id);

  async function onSave() {
    setPending(true);
    try {
      await api.post(`/categories/${category.id}/reparent`, {
        parent_category_id: parent === TOP ? null : parent,
      });
      toast({ title: "Category moved", variant: "success" });
      setOpen(false);
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong";
      toast({ title: "Could not reparent", description: message, variant: "destructive" });
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          Reparent
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Move “{category.name}”</DialogTitle>
          <DialogDescription>The category inherits its parent’s business unit.</DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label>Parent</Label>
          <Select value={parent} onValueChange={setParent}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOP}>Top level</SelectItem>
              {options.map((c) => (
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
          <Button loading={pending} onClick={onSave}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
