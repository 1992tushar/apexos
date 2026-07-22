import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names with Tailwind conflict resolution. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format integer minor units (paise) as INR currency. */
export function formatMoney(minor: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format((minor ?? 0) / 100);
}

/** Compact number formatting for stat tiles. */
export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n ?? 0);
}
