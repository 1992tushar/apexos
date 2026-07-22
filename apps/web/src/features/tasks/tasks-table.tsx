"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { type ColumnDef } from "@tanstack/react-table";
import { Check, CheckSquare } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { Task, TaskStatus } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { useToast } from "@/components/ui/toaster";
import { NewTaskDialog } from "@/features/tasks/new-task-dialog";

const STATUS_FILTERS: { label: string; value: TaskStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "Completed", value: "completed" },
];

const PRIORITY_VARIANT: Record<string, "muted" | "default" | "warning" | "destructive"> = {
  low: "muted",
  normal: "default",
  high: "warning",
  urgent: "destructive",
};

function CompleteButton({ task }: { task: Task }) {
  const router = useRouter();
  const { toast } = useToast();
  const [pending, setPending] = React.useState(false);
  if (task.status === "completed") {
    return <span className="text-xs text-muted-foreground">Done</span>;
  }
  async function run() {
    setPending(true);
    try {
      await api.post(`/tasks/${task.id}/complete`);
      toast({ title: "Task completed", variant: "success" });
      router.refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Action failed";
      toast({ title: "Could not complete task", description: message, variant: "destructive" });
    } finally {
      setPending(false);
    }
  }
  return (
    <Button variant="outline" size="sm" loading={pending} onClick={run}>
      <Check className="size-4" /> Complete
    </Button>
  );
}

const columns: ColumnDef<Task, unknown>[] = [
  {
    accessorKey: "title",
    header: "Task",
    cell: ({ row }) => (
      <div>
        <p className={cn("font-medium", row.original.status === "completed" && "text-muted-foreground line-through")}>
          {row.original.title}
        </p>
        {row.original.entity_type ? (
          <p className="text-xs text-muted-foreground">Linked to {row.original.entity_type.replace("_", " ")}</p>
        ) : null}
      </div>
    ),
  },
  {
    accessorKey: "priority",
    header: "Priority",
    cell: ({ row }) => (
      <Badge variant={PRIORITY_VARIANT[row.original.priority] ?? "muted"}>
        {row.original.priority[0].toUpperCase() + row.original.priority.slice(1)}
      </Badge>
    ),
  },
  {
    accessorKey: "due_date",
    header: "Due",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.due_date ? formatDate(row.original.due_date) : "—"}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={row.original.status === "completed" ? "success" : "default"} dot>
        {row.original.status === "completed" ? "Completed" : "Open"}
      </Badge>
    ),
  },
  {
    id: "actions",
    header: "",
    meta: { align: "right" },
    cell: ({ row }) => <CompleteButton task={row.original} />,
  },
];

export function TasksTable({ tasks }: { tasks: Task[] }) {
  const [status, setStatus] = React.useState<TaskStatus | "all">("all");
  const filtered = status === "all" ? tasks : tasks.filter((t) => t.status === status);

  return (
    <DataTable
      columns={columns}
      data={filtered}
      searchPlaceholder="Search tasks…"
      toolbar={
        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-1 rounded-md border bg-muted/40 p-0.5 sm:flex">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => setStatus(f.value)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  status === f.value
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <NewTaskDialog />
        </div>
      }
      emptyState={
        <EmptyState
          icon={<CheckSquare className="size-8" strokeWidth={1.5} />}
          title="No tasks"
          description="Create a task to track follow-ups across the business."
          action={<NewTaskDialog />}
        />
      }
    />
  );
}
