export type QuantityByUom = { qty: string; uom: string };

/** Only represent whole numbers to operators; never round real fractions. */
export function formatProductionQty(value: string): string {
  const input = value.trim();
  if (!/^\d+(?:\.0+)?$/.test(input)) return "Perlu koreksi Qty";
  try {
    return new Intl.NumberFormat("id-ID").format(BigInt(input.split(".")[0]));
  } catch {
    return "Perlu koreksi Qty";
  }
}

/**
 * A total is meaningful only within a single UoM.
 * Never show 1.5, decimal-place artifacts, or a sum of Kg and gram as
 * a single number. UoM conversion requires explicit master rules.
 */
export function productionQtyLabel(
  value: string | null,
  uom: string | null,
  byUom: QuantityByUom[] = [],
  invalid = false,
): string {
  if (invalid) return "Perlu koreksi Qty";
  if (byUom.length > 1) {
    return byUom.map((part) => `${formatProductionQty(part.qty)} ${part.uom}`).join(" · ");
  }
  if (value === null) return "Perlu koreksi Qty";
  if (value === "0" && !uom) return "0 (tanpa SKU)";
  return `${formatProductionQty(value)} ${uom || "pcs"}`;
}
