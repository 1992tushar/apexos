import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AddMasterDialog, type MasterField } from "@/features/settings/add-master-dialog";

export type MasterCardRow = {
  id: string;
  primary: string;
  secondary?: string | null;
  trailing?: string | null;
  active?: boolean;
};

/** A settings section: a titled card listing master rows with an add dialog. */
export function MasterCard({
  title,
  description,
  rows,
  endpoint,
  fields,
}: {
  title: string;
  description?: string;
  rows: MasterCardRow[];
  endpoint: string;
  fields: MasterField[];
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2">
        <div>
          <CardTitle>{title}</CardTitle>
          {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        </div>
        <AddMasterDialog title={title} endpoint={endpoint} fields={fields} />
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No rows yet.</p>
        ) : (
          <ul className="divide-y">
            {rows.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className="flex items-center gap-2">
                  <span className="font-medium">{r.primary}</span>
                  {r.secondary ? (
                    <span className="font-mono text-xs text-muted-foreground">{r.secondary}</span>
                  ) : null}
                </span>
                <span className="flex items-center gap-2">
                  {r.trailing ? <span className="tabular-nums text-muted-foreground">{r.trailing}</span> : null}
                  {r.active === false ? <Badge variant="muted">Inactive</Badge> : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
