import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductionConsolidation from "./ProductionConsolidation";
import {
  loadConsolidationPreview, loadConsolidationDetail, saveConsolidation,
  type ProductionInboxOrder, type ConsolidationPreview, type ConsolidationDetail,
} from "./api";

vi.mock("./api", () => ({
  loadConsolidationPreview: vi.fn(),
  loadConsolidationDetail: vi.fn(),
  saveConsolidation: vi.fn(),
}));

const order: ProductionInboxOrder = {
  order_id: 1, status: "KIRIM", plan_id: null,
  store_code: "T_BAN", store_name: "Bandara",
  kitchen_code: "JP", kitchen_name: "Jajan Pasar",
  delivery_date: "2026-11-07",
  schedule_code: "SUBUH", schedule_name: "Subuh",
  sku_count: 1, qty_total: "250",
  qty_uom: "Pcs",
  qty_by_uom: [{ uom: "Pcs", qty: "250" }],
  qty_invalid: false, auto_submitted: false,
};

const schedules = [
  { code: "SUBUH", name: "Subuh" },
  { code: "PAGI", name: "Pagi" },
];
const preview: ConsolidationPreview = {
  kitchen: { code: "JP", name: "Jajan Pasar" },
  delivery_date: "2026-11-07",
  delivery_schedule: schedules[0],
  production_date: null, production_schedule: null,
  production_schedules: schedules, order_ids: [1, 2],
  orders: [
    { order_id: 1, store_code: "T_BAN", store_name: "Bandara" },
    { order_id: 2, store_code: "T_KD", store_name: "Kedaton" },
  ],
  items: [{
    product_id: 5, sku: "10005", name: "Arem-arem Sultan Mini",
    uom: "Pcs", qty_requested: "500",
    capacity_qty: null, capacity_used: null, capacity_available: null,
    sources: [
      { order_id: 1, store_code: "T_BAN", store_name: "Bandara", qty: "250" },
      { order_id: 2, store_code: "T_KD", store_name: "Kedaton", qty: "250" },
    ],
  }],
};
const detail: ConsolidationDetail = {
  plan_id: 7, status: "DRAFT",
  kitchen: preview.kitchen,
  delivery_date: "2026-11-07",
  delivery_schedule: schedules[0],
  production_date: "2026-11-06",
  production_schedule: schedules[1],
  sources: preview.orders.map((o) => ({
    ...o, lines_snapshot: [{
      product_id: 5, sku: "10005", name: "Arem-arem Sultan Mini",
      uom: "Pcs", qty: "250",
    }],
  })),
  items: [{
    ...preview.items[0], qty_planned: "400", qty_shortfall: "100",
    capacity_qty: "400", capacity_used: "0", capacity_available: "400",
    qty_mo: null,
  }],
  shortfall_sku_count: 1,
  note: "Rencana belum membuat MO Odoo.",
};

beforeEach(() => {
  // jsdom does not implement the native <dialog> top layer.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.removeAttribute("open"); },
  });
  vi.mocked(loadConsolidationPreview).mockImplementation(async (scope) => ({
    ...preview,
    production_date: scope.production_date || null,
    production_schedule: scope.production_schedule_code ? schedules[1] : null,
    items: preview.items.map((item) => ({
      ...item,
      capacity_qty: scope.production_schedule_code ? "400" : null,
      capacity_used: scope.production_date ? "0" : null,
      capacity_available: scope.production_date && scope.production_schedule_code
        ? "400" : null,
    })),
  }));
  vi.mocked(loadConsolidationDetail).mockResolvedValue(detail);
  vi.mocked(saveConsolidation).mockResolvedValue({
    plan_id: 7, order_ids: [1, 2], shortfall_sku_count: 1,
    detail: "Konsolidasi tersimpan.",
  });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); document.body.style.overflow = ""; });

describe("Konsolidasi Produksi V1", () => {
  it("opens above the inbox as a native modal, focuses close, and supports Esc", async () => {
    const onBack = vi.fn();
    const previousOverflow = document.body.style.overflow;
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={onBack} onSaved={vi.fn()}
    />);
    const dialog = await screen.findByRole("dialog", { name: "Rencanakan Produksi" });
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(dialog.getAttribute("aria-describedby")).toBe("production-plan-description");
    expect(document.body.style.overflow).toBe("hidden");
    const close = screen.getByRole("button", {
      name: "Tutup rencana dan kembali ke daftar pesanan",
    });
    await waitFor(() => expect(document.activeElement).toBe(close));
    const canceled = fireEvent(dialog, new Event("cancel", {
      bubbles: false, cancelable: true,
    }));
    expect(canceled).toBe(false);
    expect(onBack).toHaveBeenCalledOnce();
    // This test passes an onBack spy rather than unmounting on close.
    expect(previousOverflow).toBe("");
  });

  it("closes when clicking the dialog backdrop, not its inner content", async () => {
    const onBack = vi.fn();
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={onBack} onSaved={vi.fn()}
    />);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(screen.getByText("Identitas pengiriman & produksi"));
    expect(onBack).not.toHaveBeenCalled();
    fireEvent.click(dialog);
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("requires manual production date and schedule, shows three quantities and saves shortfall", async () => {
    const onSaved = vi.fn();
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={onSaved}
    />);
    const saveButton = screen.getByRole("button", { name: "Simpan Konsolidasi" });
    expect((saveButton as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Tanggal Produksi (manual)") as HTMLInputElement).value).toBe("");
    expect(screen.getByText("2026-11-07")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Tanggal Produksi (manual)"), {
      target: { value: "2026-11-06" },
    });
    fireEvent.change(screen.getByLabelText("Jadwal Produksi"), {
      target: { value: "PAGI" },
    });
    await waitFor(() => expect(screen.getAllByText("400 Pcs").length).toBeGreaterThan(0));
    expect(screen.getByText("500 Pcs")).toBeTruthy();
    const input = screen.getByRole("textbox", { name: "Qty Produksi 10005" });
    fireEvent.change(input, { target: { value: "400" } });
    await waitFor(() => expect(screen.getByText("100 Pcs")).toBeTruthy());
    expect((saveButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(saveButton);
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledWith({
      kitchen_code: "JP", delivery_date: "2026-11-07",
      delivery_schedule_code: "SUBUH",
      production_date: "2026-11-06", production_schedule_code: "PAGI",
      order_ids: [1, 2],
      items: [{ product_id: 5, qty_planned: "400" }],
    }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByText("Rencana Produksi #7")).toBeTruthy());
    expect(screen.getByText("100 Pcs")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Simpan Konsolidasi" })).toBeNull();
  });

  it("does not allow Qty above capacity and does not silently change delivery schedule", async () => {
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()}
    />);
    fireEvent.change(screen.getByLabelText("Tanggal Produksi (manual)"), {
      target: { value: "2026-11-06" },
    });
    fireEvent.change(screen.getByLabelText("Jadwal Produksi"), {
      target: { value: "PAGI" },
    });
    await waitFor(() => expect(screen.getAllByText("400 Pcs").length).toBeGreaterThan(0));
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10005" }), {
      target: { value: "500" },
    });
    expect((screen.getByRole("button", {
      name: "Simpan Konsolidasi",
    }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Periksa Qty / kapasitas")).toBeTruthy();
    expect(saveConsolidation).not.toHaveBeenCalled();
    expect(screen.getAllByText("Subuh").length).toBeGreaterThan(0);
  });

  it("opens persisted plan as read-only history, including its shortage", async () => {
    render(<ProductionConsolidation
      order={{ ...order, status: "PROSES_PRODUKSI", plan_id: 7 }}
      planId={7} schedules={schedules} onBack={vi.fn()} onSaved={vi.fn()}
    />);
    await waitFor(() => expect(screen.getByText("Rencana Produksi #7")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("100 Pcs")).toBeTruthy());
    expect(screen.queryByRole("textbox", { name: "Qty Produksi 10005" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Simpan Konsolidasi" })).toBeNull();
    expect(screen.getByText("Subuh")).toBeTruthy();
    expect(screen.getByText("Pagi")).toBeTruthy();
  });
});
