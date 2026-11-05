/** Format quantities without ever silently rounding a fractional value. */
export function formatProductionQty(value: string): string {
  const input = value.trim();
  // Django/PostgreSQL Decimal(18,4) often serializes 1232 as "1232.0000".
  // Only discard fractional zeroes, not a real fractional quantity.
  if (/^\d+(?:\.0+)?$/.test(input)) {
    try {
      return new Intl.NumberFormat("id-ID").format(BigInt(input.split(".")[0]));
    } catch {
      return input.split(".")[0];
    }
  }
  return input.replace(".", ",");
}

/** Show a single actual UoM, or an explicit mixed-UoM marker. */
export function productionQtyLabel(value: string, uom: string | null): string {
  return `${formatProductionQty(value)} ${uom || "beragam UoM"}`;
}
