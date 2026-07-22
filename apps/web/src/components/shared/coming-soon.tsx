import { Construction } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";

export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="space-y-6">
      <PageHeader title={title} />
      <EmptyState
        icon={<Construction className="size-8" strokeWidth={1.5} />}
        title="Coming soon"
        description={`The ${title} module is on the ApexOS roadmap. This surface is scaffolded and will light up in a later release.`}
      />
    </div>
  );
}
