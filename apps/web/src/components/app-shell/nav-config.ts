import {
  BarChart3,
  Boxes,
  CheckSquare,
  Factory,
  Folder,
  IndianRupee,
  LayoutDashboard,
  LineChart,
  Package,
  ClipboardList,
  Settings,
  ShoppingCart,
  Tags,
  Truck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  active: boolean;
  section: "main" | "work" | "system";
};

/**
 * Sidebar modules in the exact canonical order. Spine modules are live links;
 * the rest render a "Coming soon" placeholder.
 */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard, active: true, section: "main" },
  { label: "Sales", href: "/sales", icon: ShoppingCart, active: true, section: "work" },
  { label: "Customers", href: "/customers", icon: Users, active: true, section: "work" },
  { label: "Products", href: "/products", icon: Package, active: true, section: "work" },
  { label: "Categories", href: "/categories", icon: Tags, active: true, section: "work" },
  { label: "Inventory", href: "/inventory", icon: Boxes, active: true, section: "work" },
  { label: "Warehouse", href: "/warehouse", icon: Warehouse, active: true, section: "work" },
  { label: "Procurement", href: "/procurement", icon: Truck, active: true, section: "work" },
  { label: "Purchase Orders", href: "/purchase-orders", icon: ClipboardList, active: true, section: "work" },
  { label: "Suppliers", href: "/suppliers", icon: Factory, active: true, section: "work" },
  { label: "Finance", href: "/finance", icon: IndianRupee, active: true, section: "work" },
  { label: "Reports", href: "/reports", icon: BarChart3, active: false, section: "work" },
  { label: "Analytics", href: "/analytics", icon: LineChart, active: false, section: "work" },
  { label: "Tasks", href: "/tasks", icon: CheckSquare, active: true, section: "system" },
  { label: "Documents", href: "/documents", icon: Folder, active: true, section: "system" },
  { label: "Settings", href: "/settings", icon: Settings, active: true, section: "system" },
];

export const SECTION_LABELS: Record<NavItem["section"], string | null> = {
  main: null,
  work: "Work",
  system: "System",
};
