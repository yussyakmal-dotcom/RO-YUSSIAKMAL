import { describe, expect, it } from "vitest";
import { formatProductionQty, productionQtyLabel } from "./productionQty";

describe("production Qty display", () => {
  it("shows stored integral Decimal values as Indonesian integers", () => {
    expect(formatProductionQty("1232.0000")).toBe("1.232");
    expect(formatProductionQty("120.0000")).toBe("120");
    expect(formatProductionQty("0.0000")).toBe("0");
    expect(formatProductionQty("1645")).toBe("1.645");
  });

  it("blocks genuinely fractional legacy amounts from operator display", () => {
    expect(formatProductionQty("1.5000")).toBe("Perlu koreksi Qty");
  });

  it("uses the UoM from product and exposes mixed UoMs", () => {
    expect(productionQtyLabel("120.0000", "Lusin")).toBe("120 Lusin");
    expect(productionQtyLabel("1232.0000", "pcs")).toBe("1.232 pcs");
    expect(productionQtyLabel(null, null, [{uom:"Kg",qty:"1"},{uom:"gr",qty:"500"}])).toBe("1 Kg · 500 gr");
    expect(productionQtyLabel(null, null, [], true)).toBe("Perlu koreksi Qty");
  });
});
