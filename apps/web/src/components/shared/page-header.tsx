import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export type Crumb = { label: string; href?: string };

interface PageHeaderProps {
  title: string;
  crumbs?: Crumb[];
  /** Optional back link target; renders a leading chevron. */
  backHref?: string;
  meta?: React.ReactNode;
  status?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  crumbs,
  backHref,
  meta,
  status,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-3 border-b pb-5", className)}>
      {crumbs && crumbs.length > 0 ? (
        <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {backHref ? (
            <Link href={backHref} className="mr-0.5 rounded p-0.5 hover:text-foreground" aria-label="Back">
              <ChevronLeft className="size-4" />
            </Link>
          ) : null}
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 ? <span className="text-border">/</span> : null}
              {c.href ? (
                <Link href={c.href} className="hover:text-foreground">
                  {c.label}
                </Link>
              ) : (
                <span className="text-foreground">{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {status}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="text-sm text-muted-foreground">{meta}</div> : null}
    </header>
  );
}
