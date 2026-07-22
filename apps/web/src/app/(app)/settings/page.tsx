import { api } from "@/lib/api";
import type { MasterKind, Setting, TaxRate, Warehouse } from "@/lib/dto";
import { PageHeader } from "@/components/shared/page-header";
import { MasterCard } from "@/features/settings/master-card";

export const dynamic = "force-dynamic";

async function load() {
  const [businessUnits, brands, uoms, customerTypes, supplierTypes, warehouses, taxRates, settings] =
    await Promise.all([
      api.get<MasterKind[]>("/business-units").catch(() => [] as MasterKind[]),
      api.get<MasterKind[]>("/brands").catch(() => [] as MasterKind[]),
      api.get<MasterKind[]>("/uoms").catch(() => [] as MasterKind[]),
      api.get<MasterKind[]>("/customer-types").catch(() => [] as MasterKind[]),
      api.get<MasterKind[]>("/supplier-types").catch(() => [] as MasterKind[]),
      api.get<Warehouse[]>("/warehouses").catch(() => [] as Warehouse[]),
      api.get<TaxRate[]>("/tax-rates").catch(() => [] as TaxRate[]),
      api.get<Setting[]>("/settings").catch(() => [] as Setting[]),
    ]);
  return { businessUnits, brands, uoms, customerTypes, supplierTypes, warehouses, taxRates, settings };
}

const CODE_NAME = [
  { name: "code", label: "Code", required: true, placeholder: "CODE" },
  { name: "name", label: "Name", required: true },
] as const;

export default async function SettingsPage() {
  const data = await load();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        crumbs={[{ label: "Settings" }]}
        meta="Configure the data-driven nouns that power the app"
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MasterCard
          title="Business Units"
          description="Operating lines. Categories and operations roll up to a BU."
          endpoint="/business-units"
          fields={[...CODE_NAME]}
          rows={data.businessUnits.map((b) => ({
            id: b.id,
            primary: b.name,
            secondary: b.code,
            active: b.is_active,
          }))}
        />
        <MasterCard
          title="Brands"
          endpoint="/brands"
          fields={[...CODE_NAME]}
          rows={data.brands.map((b) => ({ id: b.id, primary: b.name, secondary: b.code, active: b.is_active }))}
        />
        <MasterCard
          title="Units of Measure"
          endpoint="/uoms"
          fields={[...CODE_NAME]}
          rows={data.uoms.map((u) => ({ id: u.id, primary: u.name, secondary: u.code, active: u.is_active }))}
        />
        <MasterCard
          title="Customer Types"
          endpoint="/customer-types"
          fields={[...CODE_NAME]}
          rows={data.customerTypes.map((c) => ({ id: c.id, primary: c.name, secondary: c.code, active: c.is_active }))}
        />
        <MasterCard
          title="Supplier Types"
          endpoint="/supplier-types"
          fields={[...CODE_NAME]}
          rows={data.supplierTypes.map((s) => ({ id: s.id, primary: s.name, secondary: s.code, active: s.is_active }))}
        />
        <MasterCard
          title="Warehouses"
          description="Stocking locations."
          endpoint="/warehouses"
          fields={[
            { name: "code", label: "Code", required: true, placeholder: "PUNE" },
            { name: "name", label: "Name", required: true },
            { name: "city", label: "City" },
            { name: "state_code", label: "State code", placeholder: "27" },
          ]}
          rows={data.warehouses.map((w) => ({
            id: w.id,
            primary: w.name,
            secondary: w.code,
            trailing: w.city ?? undefined,
            active: w.is_active,
          }))}
        />
        <MasterCard
          title="Tax Rates (GST slabs)"
          description="Versioned — adding a slab closes the prior one; history is kept."
          endpoint="/tax-rates"
          fields={[
            { name: "code", label: "Code", required: true, placeholder: "GST_18" },
            { name: "name", label: "Name", required: true, placeholder: "GST 18%" },
            { name: "rate_bps", label: "Rate (basis points)", type: "number", required: true, placeholder: "1800" },
          ]}
          rows={data.taxRates.map((t) => ({
            id: t.id,
            primary: t.name,
            secondary: t.code,
            trailing: `${(t.rate_bps / 100).toFixed(1)}%`,
            active: t.is_active,
          }))}
        />
        <MasterCard
          title="Settings"
          description="Free-form key/value configuration."
          endpoint="/settings"
          fields={[
            { name: "key", label: "Key", required: true, placeholder: "invoice.footer_note" },
            { name: "value", label: "Value", required: true },
            { name: "description", label: "Description" },
          ]}
          rows={data.settings.map((s) => ({
            id: s.id,
            primary: s.key,
            secondary: undefined,
            trailing: typeof s.value === "string" ? s.value : JSON.stringify(s.value),
          }))}
        />
      </div>
    </div>
  );
}
