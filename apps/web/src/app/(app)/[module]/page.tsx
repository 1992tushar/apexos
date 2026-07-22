import { ComingSoon } from "@/components/shared/coming-soon";
import { NAV_ITEMS } from "@/components/app-shell/nav-config";

const LABELS = new Map(NAV_ITEMS.map((i) => [i.href.replace(/^\//, ""), i.label]));

function prettify(slug: string): string {
  return slug
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}

export default function ModulePlaceholderPage({ params }: { params: { module: string } }) {
  const title = LABELS.get(params.module) ?? prettify(params.module);
  return <ComingSoon title={title} />;
}
