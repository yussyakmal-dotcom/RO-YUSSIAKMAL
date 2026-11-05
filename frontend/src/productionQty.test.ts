import { describe, expect, it } from "vitest";
import { formatProductionQty, productionQtyLabel } from "./productionQty";

describe("production Qty display", () => {
  it("shows stored integral Decimal values as Indonesian integers", () => {
    expect(formatProductionQty("1232.0000")).toBe("1.232");
    expect(formatProductionQty("120.0000")).toBe("120");
    expect(formatProductionQty("0.0000")).toBe("0");
    expect(formatProductionQty("1645")).toBe("1.645");
  });

  it("keeps genuinely fractional legacy amounts visible, not rounded", () => {
    expect(formatProductionQty("1.5000")).toBe("1,5000");
  });

  it("uses the UoM from product and exposes mixed UoMs", () => {
    expect(productionQtyLabel("120.0000", "Lusin")).toBe("120 Lusin");
    expect(productionQtyLabel("1232.0000", "pcs")).toBe("1.232 pcs");
    expect(productionQtyLabel("1645.0000", null)).toBe("1.645 beragam UoM");
  });
});
