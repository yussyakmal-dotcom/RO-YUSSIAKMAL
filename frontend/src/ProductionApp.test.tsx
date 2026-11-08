import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductionApp from "./ProductionApp";
import {
  initializeSession, loadProductionDemand, loadProductionDeliveryQueue,
  loadConsolidationPreview, loadConsolidationDetail, saveConsolidation,
  loadProductionDraft, saveProductionDraft,
  type ProductionDemand, type ProductionDeliveryGroup,
  type ProductionDeliveryQueue, type SessionInfo,
} from "./api";

vi.mock("./api", () => ({
  initializeSession: vi.fn(),
  loadProductionDemand: vi.fn(),
  loadProductionDeliveryQueue: vi.fn(),
  loadConsolidationPreview: vi.fn(),
  loadConsolidationDetail: vi.fn(),
  saveConsolidation: vi.fn(),
  loadProductionDraft: vi.fn(),
  saveProductionDraft: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("./App", () => ({ LoginPage: () => null }));

const session: SessionInfo = {
  user: {
    username: "prod", full_name: "Admin Produksi",
    admin: true, can_access_production: true, can_access_store: true,
  },
  stores: [],
  kitchens: [{ code: "JP", name: "Dapur JP", item_count: 69 }],
  schedules: [{ code: "SUBUH", name: "Subuh" }, { code: "PAGI", name: "Pagi" }],
};

const oneScope: ProductionDeliveryGroup = {
  delivery_date: "2026-11-07",
  kitchen_code: "JP", kitchen_name: "Dapur JP",
  schedule_code: "SUBUH", schedule_name: "Subuh",
  status: "KIRIM", order_count: 2, store_count: 2,
  kirim_count: 2, proses_produksi_count: 0, plan_id: null,
  has_consolidation_draft: false, sku_count: 1,
  qty_total: "500", qty_uom: "Pcs",
  qty_by_uom: [{ uom: "Pcs", qty: "500" }], qty_invalid: false,
  stores: [
    { order_id: 1, store_code: "T_BAN", store_name: "Toko Bandara", status: "KIRIM" },
    { order_id: 2, store_code: "T_KD", store_name: "Toko Kedaton", status: "KIRIM" },
  ],
};
const secondScope: ProductionDeliveryGroup = {
  ...oneScope, delivery_date: "2026-11-08",
  schedule_code: "PAGI", schedule_name: "Pagi",
  order_count: 1, store_count: 1,
  kirim_count: 1, sku_count: 1,
  qty_total: "30", qty_by_uom: [{ uom: "Pcs", qty: "30" }],
  stores: [
    { order_id: 3, store_code: "T_BAN", store_name: "Toko Bandara", status: "KIRIM" },
  ],
};
const inbox: ProductionDeliveryQueue = {
  status_filter: "ALL", page: 1, page_size: 50, total: 2,
  has_more: false,
  counts: { all: 2, kirim: 2, proses_produksi: 0 },
  items: [oneScope, secondScope],
};
const recap: ProductionDemand = {
  delivery_date: "2026-11-07",
  kitchen: { code: "JP", name: "Dapur JP" },
  schedule: { code: "SUBUH", name: "Subuh" },
  basis: "KIRIM_AND_PROSES_PRODUKSI",
  production_date: null, note: "Baca saja",
  summary: {
    stores_total: 2, stores_sent: 2, stores_in_production: 0,
    sku_count: 1, qty_total: "500", qty_uom: "Pcs",
    qty_by_uom: [{ uom: "Pcs", qty: "500" }], qty_invalid: false,
  },
  store_statuses: [],
  items: [{
    product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "Pcs",
    qty_total: "500", store_count: 2,
    sources: [
      {
        store_code: "T_BAN", store_name: "Toko Bandara", order_id: 1,
        qty: "250", status: "KIRIM", auto_submitted: false,
      },
      {
        store_code: "T_KD", store_name: "Toko Kedaton", order_id: 2,
        qty: "250", status: "KIRIM", auto_submitted: false,
      },
    ],
  }],
};

beforeEach(() => {
  vi.mocked(initializeSession).mockResolvedValue(session);
  vi.mocked(loadProductionDeliveryQueue).mockResolvedValue(inbox);
  vi.mocked(loadProductionDemand).mockResolvedValue(recap);
  vi.mocked(loadConsolidationPreview).mockImplementation(async (scope) => ({
    kitchen: { code: "JP", name: "Dapur JP" },
    delivery_date: scope.delivery_date,
    delivery_schedule: { code: scope.delivery_schedule_code, name: "Subuh" },
    production_date: scope.production_date || null,
    production_schedule: scope.production_schedule_code
      ? { code: scope.production_schedule_code, name: "Pagi" } : null,
    production_schedules: [
      { code: "SUBUH", name: "Subuh" }, { code: "PAGI", name: "Pagi" },
    ],
    order_ids: [1, 2],
    orders: [
      { order_id: 1, store_code: "T_BAN", store_name: "Toko Bandara" },
      { order_id: 2, store_code: "T_KD", store_name: "Toko Kedaton" },
    ],
    items: [{
      product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "Pcs",
      qty_requested: "500", bom_output_qty: "100",
      capacity_qty: scope.production_schedule_code ? "400" : null,
      capacity_used: scope.production_date ? "0" : null,
      capacity_available: scope.production_date && scope.production_schedule_code ? "400" : null,
      sources: [],
    }],
  }));
  vi.mocked(loadProductionDraft).mockResolvedValue({ draft: null });
  vi.mocked(saveProductionDraft).mockResolvedValue({
    draft: {
      id: 10, version: 1, production_date: null,
      production_schedule_code: null,
      order_ids: [1, 2], items: [{ product_id: 10, qty_planned: "250" }],
      updated_at: "2026-11-08T12:00:00+07:00", updated_by: "prod",
    },
  });
  vi.mocked(saveConsolidation).mockResolvedValue({
    plan_id: 7, order_ids: [1, 2], shortfall_sku_count: 1,
    detail: "Konsolidasi tersimpan.",
  });
  vi.mocked(loadConsolidationDetail).mockResolvedValue({
    plan_id: 7, status: "DRAFT", kitchen: recap.kitchen,
    delivery_date: "2026-11-07",
    delivery_schedule: { code: "SUBUH", name: "Subuh" },
    production_date: "2026-11-06",
    production_schedule: { code: "PAGI", name: "Pagi" },
    sources: recap.items[0].sources.map((source) => ({
      order_id: source.order_id, store_code: source.store_code,
      store_name: source.store_name,
      lines_snapshot: [{
        product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "Pcs", qty: "250",
      }],
    })),
    items: [{
      product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "Pcs",
      qty_requested: "500", bom_output_qty: "100",
      capacity_qty: "400", capacity_used: "0", capacity_available: "400",
      qty_planned: "400", qty_shortfall: "100", qty_mo: null,
    }],
    shortfall_sku_count: 1, note: "Belum membuat MO Odoo.",
  });
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.removeAttribute("open"); },
  });
  Object.defineProperty(window, "requestAnimationFrame", {
    configurable: true,
    value: (callback: FrameRequestCallback) =>
      window.setTimeout(() => callback(0), 0),
  });
});
afterEach(() => {
  cleanup(); vi.clearAllMocks();
  document.body.style.overflow = "";
});

describe("Antrean produksi per tanggal kirim", () => {
  it("shows one row for two stores and groups by delivery date, kitchen and schedule", async () => {
    render(<ProductionApp />);
    await screen.findByText("Antrean Produksi per Tanggal Kirim");
    await screen.findByText("500 Pcs");
    expect(screen.getByText("Kelompok Tanggal Kirim")).toBeTruthy();
    expect(screen.getAllByText(/Tanggal Kirim —/).length).toBe(2);
    expect(screen.queryAllByText("7/11/2026")).toHaveLength(0);
    expect(screen.getByText("2 toko")).toBeTruthy();
    expect(screen.getByText("1 toko")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Rencanakan" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Lihat rekap" })).toHaveLength(2);
    expect(screen.getByText("2 kelompok pengiriman · Halaman 1 · 50 kelompok per halaman")).toBeTruthy();

    const details = screen.getByText("Lihat toko (2)").closest("details");
    expect(details).not.toBeNull();
    fireEvent.click(screen.getByText("Lihat toko (2)"));
    expect(details?.open).toBe(true);
    expect(screen.getByText(/Toko Bandara · T_BAN · #1/)).toBeTruthy();
    expect(screen.getByText(/Toko Kedaton · T_KD · #2/)).toBeTruthy();
    expect(vi.mocked(loadProductionDeliveryQueue)).toHaveBeenCalledWith(
      "ALL", 1, expect.any(AbortSignal),
    );
  });

  it("keeps separate UoM subtotals without showing a fake combined Qty", async () => {
    vi.mocked(loadProductionDeliveryQueue).mockResolvedValue({
      ...inbox, total: 1,
      items: [{
        ...oneScope, qty_total: null, qty_uom: null,
        qty_by_uom: [{ uom: "Kg", qty: "1" }, { uom: "gram", qty: "500" }],
      }],
    });
    render(<ProductionApp />);
    await screen.findByText("1 Kg · 500 gram");
    expect(screen.queryByText("501 Pcs")).toBeNull();
  });

  it("warns rather than rounding historical fractional quantities", async () => {
    vi.mocked(loadProductionDeliveryQueue).mockResolvedValue({
      ...inbox, total: 1,
      items: [{
        ...oneScope, qty_total: null, qty_uom: null,
        qty_by_uom: [], qty_invalid: true,
      }],
    });
    render(<ProductionApp />);
    await screen.findByText("Perlu koreksi Qty");
    expect(screen.queryByText("1,5000")).toBeNull();
  });

  it("opens one group recap popup and restores focus without reloading the queue", async () => {
    render(<ProductionApp />);
    const opener = (await screen.findAllByRole("button", {
      name: "Lihat rekap",
    }))[0];
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "Rekap Dapur JP" });
    expect(dialog.textContent).toContain("2 toko dalam kelompok pengiriman");
    expect(dialog.textContent).toContain("500 Pcs");
    expect(screen.getByText("Antrean Produksi per Tanggal Kirim")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tutup Rekap" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(loadProductionDeliveryQueue).toHaveBeenCalledTimes(1);
  });

  it("opens planning on group, saves draft and resumes it while scope stays KIRIM", async () => {
    vi.mocked(loadProductionDeliveryQueue).mockResolvedValueOnce(inbox).mockResolvedValue({
      ...inbox, items: [
        { ...oneScope, has_consolidation_draft: true }, secondScope,
      ],
    });
    vi.mocked(loadProductionDraft).mockResolvedValueOnce({ draft: null })
      .mockResolvedValue({
        draft: {
          id: 10, version: 1, production_date: null,
          production_schedule_code: null, order_ids: [1, 2],
          items: [{ product_id: 10, qty_planned: "250" }],
          updated_at: "2026-11-08T12:00:00+07:00", updated_by: "prod",
        },
      });
    render(<ProductionApp />);
    const opener = (await screen.findAllByRole("button", {
      name: "Rencanakan",
    }))[0];
    fireEvent.click(opener);
    const modal = await screen.findByRole("dialog", { name: "Rencanakan Produksi" });
    expect(modal.textContent).toContain("Tanggal kirim 2026-11-07");
    const input = await screen.findByRole("textbox", { name: "Qty Produksi 10005" });
    fireEvent.change(input, { target: { value: "250" } });
    const draftButton = screen.getByRole("button", { name: "Simpan Draft" });
    await waitFor(() => expect((draftButton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(draftButton);
    await waitFor(() => expect(saveProductionDraft).toHaveBeenCalledWith(
      expect.objectContaining({ order_ids: [1, 2] }),
    ));
    fireEvent.click(screen.getByRole("button", { name: "Batal / Tutup" }));
    await waitFor(() => expect(loadProductionDeliveryQueue).toHaveBeenCalledTimes(2));
    const resume = await screen.findByRole("button", { name: "Lanjutkan Draft" });
    expect(screen.getAllByText("Kirim").length).toBeGreaterThan(0);
    fireEvent.click(resume);
    await waitFor(() => expect(
      (screen.getByRole("textbox", { name: "Qty Produksi 10005" }) as HTMLInputElement).value,
    ).toBe("250"));
  });

  it("flags late-arriving KIRIM within an already consolidated group without re-plan button", async () => {
    vi.mocked(loadProductionDeliveryQueue).mockResolvedValue({
      ...inbox, items: [{
        ...oneScope, status: "CAMPURAN", kirim_count: 1,
        proses_produksi_count: 1, plan_id: 7, has_consolidation_draft: false,
        stores: [
          { ...oneScope.stores[0], status: "PROSES_PRODUKSI" },
          oneScope.stores[1],
        ],
      }], total: 1,
      counts: { all: 1, kirim: 1, proses_produksi: 1 },
    });
    render(<ProductionApp />);
    await screen.findByText("Pesanan Susulan");
    expect(screen.queryByRole("button", { name: "Rencanakan" })).toBeNull();
    expect(screen.getByRole("button", { name: "Lihat rencana" })).toBeTruthy();
    expect(screen.getByText(/jangan konsolidasi ulang/)).toBeTruthy();
  });

  it("preserves status tabs as delivery-group counts, not store-order counts", async () => {
    render(<ProductionApp />);
    const kirim = await screen.findByRole("button", { name: "Kirim (2)" });
    fireEvent.click(kirim);
    await waitFor(() => expect(loadProductionDeliveryQueue).toHaveBeenCalledWith(
      "KIRIM", 1, expect.any(AbortSignal),
    ));
    expect(screen.getByRole("button", { name: "Kirim (2)" }).className).toContain("selected");
  });
});
