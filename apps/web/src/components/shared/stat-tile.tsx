import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

type Accent = "none" | "success" | "warning" | "destructive" | "primary";

const ACCENT_BAR: Record<Accent, string> = {
  none: "before:bg-transparent",
  success: "before:bg-success",
  warning: "before:bg-warning",
  destructive: "before:bg-destructive",
  primary: "before:bg-primary",
};

interface StatTileProps {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
  accent?: Accent;
  href?: string;
}

export function StatTile({ label, value, hint, icon, accent = "none", href }: StatTileProps) {
  const inner = (
    <Card
      className={cn(
        "relative h-full overflow-hidden p-5 transition-shadow",
        "before:absolute before:inset-y-0 before:left-0 before:w-[2px] before:content-['']",
        ACCENT_BAR[accent],
        href && "hover:shadow-sm",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </div>
      <p className="mt-3 text-[28px] font-semibold leading-9 tabular-nums tracking-tight">{value}</p>
      {hint ? (
        <p className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
          {hint}
          {href ? <ArrowUpRight className="size-3.5" /> : null}
        </p>
      ) : null}
    </Card>
  );

  if (href) {
    return (
      <Link href={href} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg">
        {inner}
      </Link>
    );
  }
  return inner;
}
