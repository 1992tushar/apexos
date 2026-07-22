"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Tags } from "lucide-react";
import type { Category, MasterKind } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { GenericStatusBadge } from "@/components/shared/status-badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { NewCategoryDialog } from "@/features/categories/new-category-dialog";
import { ReparentCategoryDialog } from "@/features/categories/reparent-category-dialog";

export function CategoriesTable({
  categories,
  procurementModels,
}: {
  categories: Category[];
  procurementModels: MasterKind[];
}) {
  const nameById = React.useMemo(
    () => new Map(categories.map((c) => [c.id, c.name])),
    [categories],
  );

  const columns = React.useMemo<ColumnDef<Category, unknown>[]>(
    () => [
      {
        accessorKey: "code",
        header: "Code",
        cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.code}</span>,
      },
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        id: "parent",
        header: "Parent",
        cell: ({ row }) =>
          row.original.parent_category_id ? (
            <Badge variant="secondary">{nameById.get(row.original.parent_category_id) ?? "—"}</Badge>
          ) : (
            <span className="text-muted-foreground">Top level</span>
          ),
      },
      {
        accessorKey: "sort_order",
        header: "Sort",
        meta: { align: "right" },
        cell: ({ row }) => <span className="tabular-nums text-muted-foreground">{row.original.sort_order}</span>,
      },
      {
        accessorKey: "is_active",
        header: "Status",
        cell: ({ row }) => <GenericStatusBadge status={row.original.is_active ? "active" : "inactive"} />,
      },
      {
        id: "actions",
        header: "",
        meta: { align: "right" },
        cell: ({ row }) => <ReparentCategoryDialog category={row.original} categories={categories} />,
      },
    ],
    [categories, nameById],
  );

  return (
    <DataTable
      columns={columns}
      data={categories}
      searchPlaceholder="Search categories…"
      toolbar={<NewCategoryDialog categories={categories} procurementModels={procurementModels} />}
      emptyState={
        <EmptyState
          icon={<Tags className="size-8" strokeWidth={1.5} />}
          title="No categories"
          description="Create your first product category."
          action={<NewCategoryDialog categories={categories} procurementModels={procurementModels} />}
        />
      }
    />
  );
}
