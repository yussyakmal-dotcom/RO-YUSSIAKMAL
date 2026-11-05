/** Jakarta business dates, independent of the browser's time zone. */
export function deliveryDateInWib(daysFromToday = 2): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jakarta",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values: Record<string, number> = {};
  for (const part of parts) {
    if (part.type === "year" || part.type === "month" || part.type === "day") {
      values[part.type] = Number(part.value);
    }
  }
  const date = new Date(Date.UTC(
    values.year, values.month - 1, values.day + daysFromToday,
  ));
  return date.toISOString().slice(0, 10);
}

export function normalizeQty(qty: string): string | null {
  const value = qty.trim().replace(",", ".");
  if (value === "") return "0";
  // 18 digits total, four decimal places as supported by Django DecimalField.
  const parts = value.split(".");
  if (!/^\d+$/.test(parts[0]) || parts[0].length > 14 || parts.length > 2) {
    return null;
  }
  if (parts.length === 2 && !/^\d{0,4}$/.test(parts[1])) return null;
  return value.endsWith(".") ? value.slice(0, -1) : value;
}

export function hasPositiveQty(value: string): boolean {
  const normalized = normalizeQty(value);
  return normalized !== null && Number(normalized) >= 1;
}
