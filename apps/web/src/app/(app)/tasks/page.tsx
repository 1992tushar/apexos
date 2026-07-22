import { api } from "@/lib/api";
import type { Paginated, Task } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { TasksTable } from "@/features/tasks/tasks-table";

export const dynamic = "force-dynamic";

async function load(): Promise<Task[]> {
  return api
    .get<Paginated<Task>>("/tasks?page=1&page_size=200")
    .then((r) => r.items)
    .catch(() => []);
}

export default async function TasksPage() {
  const tasks = await load();
  const open = tasks.filter((t) => t.status === "open").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tasks"
        crumbs={[{ label: "Tasks" }]}
        meta={`${tasks.length} task${tasks.length === 1 ? "" : "s"}${open > 0 ? ` · ${open} open` : ""}`}
      />
      <TasksTable tasks={tasks} />
    </div>
  );
}
