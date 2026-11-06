import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductionApp from "./ProductionApp";
import {
  initializeSession, loadProductionDemand, loadProductionInbox,
  loadConsolidationPreview, loadConsolidationDetail, saveConsolidation,
  type ProductionDemand, type ProductionInbox, type SessionInfo,
} from "./api";

vi.mock("./api", () => ({
  initializeSession: vi.fn(),
  loadProductionDemand: vi.fn(),
  loadProductionInbox: vi.fn(),
  loadConsolidationPreview: vi.fn(),
  loadConsolidationDetail: vi.fn(),
  saveConsolidation: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("./App", () => ({ LoginPage: () => null }));

const session: SessionInfo = {
  user: {
    username: "admin",
    full_name: "Admin Produksi",
    admin: true,
    can_access_production: true,
    can_access_store: true,
  },
  stores: [],
  kitchens: [{ code: "JP", name: "Dapur JP", item_count: 69 }],
  schedules: [{ code: "SUBUH", name: "Subuh" }],
};

const inbox: ProductionInbox = {
  status_filter: "ALL", page: 1, page_size: 50, total: 2,
  has_more: false,
  counts: { all: 2, kirim: 2, proses_produksi: 0 },
  items: [
    {
      order_id: 1, status: "KIRIM", plan_id: null, store_code: "T_BAN",
      store_name: "Toko Bandara", kitchen_code: "JP", kitchen_name: "Dapur JP",
      delivery_date: "2026-11-07", schedule_code: "SUBUH",
      schedule_name: "Subuh", sku_count: 18, qty_total: "1232.0000", qty_uom: "pcs", qty_by_uom: [{uom:"pcs",qty:"1232"}], qty_invalid:false,
      auto_submitted: false,
    },
    {
      order_id: 2, status: "KIRIM", plan_id: null, store_code: "T_KD",
      store_name: "Toko Kedaton", kitchen_code: "JP", kitchen_name: "Dapur JP",
      delivery_date: "2026-11-07", schedule_code: "SUBUH",
      schedule_name: "Subuh", sku_count: 6, qty_total: "413.0000", qty_uom: "pcs", qty_by_uom: [{uom:"pcs",qty:"413"}], qty_invalid:false,
      auto_submitted: false,
    },
  ],
};

const recap: ProductionDemand = {
  delivery_date: "2026-11-07",
  kitchen: { code: "JP", name: "Dapur JP" },
  schedule: { code: "SUBUH", name: "Subuh" },
  basis: "KIRIM_AND_PROSES_PRODUKSI",
  production_date: null,
  note: "Baca saja",
  summary: {
    stores_total: 2, stores_sent: 2, stores_in_production: 0,
    sku_count: 1, qty_total: "1645", qty_uom: "pcs", qty_by_uom: [{uom:"pcs",qty:"1645"}], qty_invalid:false,
  },
  store_statuses: [],
  items: [{
    product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "pcs",
    qty_total: "1645", store_count: 2,
    sources: [
      { store_code: "T_BAN", store_name: "Toko Bandara", order_id: 1, qty: "1232", status: "KIRIM", auto_submitted: false },
      { store_code: "T_KD", store_name: "Toko Kedaton", order_id: 2, qty: "413", status: "KIRIM", auto_submitted: false },
    ],
  }],
};

beforeEach(() => {
  vi.mocked(initializeSession).mockResolvedValue(session);
  vi.mocked(loadProductionInbox).mockResolvedValue(inbox);
  vi.mocked(loadProductionDemand).mockResolvedValue(recap);
  vi.mocked(loadConsolidationPreview).mockImplementation(async (scope) => ({
    kitchen: { code: "JP", name: "Dapur JP" },
    delivery_date: "2026-11-07",
    delivery_schedule: { code: "SUBUH", name: "Subuh" },
    production_date: scope.production_date || null,
    production_schedule: scope.production_schedule_code ? { code: "PAGI", name: "Pagi" } : null,
    production_schedules: [
      { code: "SUBUH", name: "Subuh" },
      { code: "PAGI", name: "Pagi" },
    ],
    order_ids: [1, 2],
    orders: [
      { order_id: 1, store_code: "T_BAN", store_name: "Toko Bandara" },
      { order_id: 2, store_code: "T_KD", store_name: "Toko Kedaton" },
    ],
    items: [{
      product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "pcs",
      qty_requested: "500",
      capacity_qty: scope.production_schedule_code ? "400" : null,
      capacity_used: scope.production_date ? "0" : null,
      capacity_available: scope.production_date && scope.production_schedule_code ? "400" : null,
      sources: [
        { order_id: 1, store_code: "T_BAN", store_name: "Toko Bandara", qty: "250" },
        { order_id: 2, store_code: "T_KD", store_name: "Toko Kedaton", qty: "250" },
      ],
    }],
  }));
  vi.mocked(loadConsolidationDetail).mockResolvedValue({
    plan_id: 7, status: "DRAFT",
    kitchen: { code: "JP", name: "Dapur JP" },
    delivery_date: "2026-11-07",
    delivery_schedule: { code: "SUBUH", name: "Subuh" },
    production_date: "2026-11-06",
    production_schedule: { code: "PAGI", name: "Pagi" },
    sources: [{
      order_id: 1, store_code: "T_BAN", store_name: "Toko Bandara",
      lines_snapshot: [{ product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "pcs", qty: "250" }],
    }],
    items: [{
      product_id: 10, sku: "10005", name: "Risoles Mayo", uom: "pcs",
      qty_requested: "500", capacity_qty: "400", capacity_used: "0",
      capacity_available: "400", qty_planned: "400", qty_shortfall: "100",
      qty_mo: null,
    }],
    shortfall_sku_count: 1, note: "Belum membuat MO.",
  });
  vi.mocked(saveConsolidation).mockResolvedValue({
    plan_id: 7, order_ids: [1, 2],
    shortfall_sku_count: 1, detail: "Tersimpan.",
  });

  // jsdom does not implement the native dialog top-layer APIs. Emulate their
  // open/close states while testing the React focus and return logic.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function(this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function(this: HTMLDialogElement) { this.removeAttribute("open"); },
  });
  Object.defineProperty(window, "requestAnimationFrame", {
    configurable: true,
    value: (callback: FrameRequestCallback) =>
      window.setTimeout(() => callback(0), 0),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  document.body.style.overflow = "";
});

describe("Admin Produksi rekap modal", () => {
  it("formats decimal-zero Qty as integers and displays original product UoM", async () => {
    vi.mocked(loadProductionDemand).mockResolvedValue({
      ...recap,
      summary: { ...recap.summary, qty_total: "120.0000", qty_uom: "Lusin", qty_by_uom: [{uom:"Lusin",qty:"120"}] },
      items: [{
        ...recap.items[0], uom: "Lusin", qty_total: "120.0000",
        sources: [{ ...recap.items[0].sources[0], qty: "120.0000" }],
      }],
    });
    render(<ProductionApp />);
    await screen.findAllByRole("button", { name: "Lihat rekap" });
    expect(screen.getByText("1.232 pcs")).toBeTruthy();
    expect(screen.getByText("413 pcs")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Lihat rekap" })[0]);
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog.textContent).toContain("120 Lusin"));
    expect(dialog.textContent).not.toContain("120.0000");
  });

  it("does not pretend a mixed-UoM order has a single pcs unit", async () => {
    vi.mocked(loadProductionInbox).mockResolvedValue({
      ...inbox,
      items: [{ ...inbox.items[0], qty_total: null, qty_uom: null, qty_by_uom: [{uom:"Kg",qty:"1"},{uom:"gr",qty:"500"}] }],
    });
    render(<ProductionApp />);
    await screen.findByText("1 Kg · 500 gr");
    expect(screen.queryByText("1.232 pcs")).toBeNull();
  });

  it("shows a correction warning, not a dangerous decimal value, for historical fractions", async () => {
    vi.mocked(loadProductionInbox).mockResolvedValue({
      ...inbox,
      items: [{
        ...inbox.items[0], qty_total: null, qty_uom: null,
        qty_by_uom: [], qty_invalid: true,
      }],
    });
    render(<ProductionApp />);
    await screen.findByText("Perlu koreksi Qty");
    expect(screen.queryByText("1,5000")).toBeNull();
  });

  it("keeps the inbox in place, renders scope recap, and restores focus on close", async () => {
    render(<ProductionApp />);
    const triggers = await screen.findAllByRole("button", { name: "Lihat rekap" });
    const opener = triggers[0];
    opener.focus();
    fireEvent.click(opener);

    const modal = await screen.findByRole("dialog");
    expect(modal.getAttribute("aria-labelledby")).toBe("production-recap-title");
    expect(screen.getByText("Rekap Dapur JP")).toBeTruthy();
    expect(screen.getByText(/Dibuka dari Toko Bandara/)).toBeTruthy();
    const closeIcon = screen.getByRole("button", {
      name: "Tutup rekap dan kembali ke daftar pesanan",
    });
    await waitFor(() => expect(document.activeElement).toBe(closeIcon));
    expect(await screen.findByText("Risoles Mayo")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Tutup Rekap" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(screen.getAllByRole("button", { name: "Lihat rekap" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Semua (2)" }).className).toContain("selected");
    expect(vi.mocked(loadProductionInbox)).toHaveBeenCalledTimes(1);
  });

  it("closes with Escape (native dialog cancel) and returns focus to its opener", async () => {
    render(<ProductionApp />);
    const triggers = await screen.findAllByRole("button", { name: "Lihat rekap" });
    const opener = triggers[1];
    fireEvent.click(opener);
    const modal = await screen.findByRole("dialog");

    const canceled = fireEvent(modal, new Event("cancel", {
      bubbles: false, cancelable: true,
    }));
    expect(canceled).toBe(false); // the default native Escape close was prevented
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(screen.getByText("Toko Kedaton")).toBeTruthy();
  });
});

describe("Admin Produksi planning modal", () => {
  it("keeps the inbox visible and returns focus to the exact Rencanakan button", async () => {
    render(<ProductionApp />);
    const buttons = await screen.findAllByRole("button", { name: "Rencanakan" });
    const opener = buttons[0];
    opener.focus();
    fireEvent.click(opener);

    const dialog = await screen.findByRole("dialog", { name: "Rencanakan Produksi" });
    expect(dialog.className).toContain("production-plan-dialog");
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(screen.getByText("Antrean Pesanan Produksi")).toBeTruthy();
    expect(screen.getByText("Toko Bandara")).toBeTruthy();
    expect(screen.getByText("Toko Kedaton")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Semua (2)" }).className).toContain("selected");
    expect(document.body.style.overflow).toBe("hidden");

    const closeIcon = screen.getByRole("button", {
      name: "Tutup rencana dan kembali ke daftar pesanan",
    });
    await waitFor(() => expect(document.activeElement).toBe(closeIcon));
    fireEvent.click(screen.getByRole("button", { name: "Batal / Tutup" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(screen.getAllByRole("button", { name: "Rencanakan" })).toHaveLength(2);
    expect(loadProductionInbox).toHaveBeenCalledTimes(1);
    expect(document.body.style.overflow).toBe("");
  });

  it("closes planning with Escape without changing filters, page or inbox", async () => {
    render(<ProductionApp />);
    const opener = (await screen.findAllByRole("button", { name: "Rencanakan" }))[1];
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "Rencanakan Produksi" });
    const canceled = fireEvent(dialog, new Event("cancel", {
      bubbles: false, cancelable: true,
    }));
    expect(canceled).toBe(false);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(screen.getByRole("button", { name: "Semua (2)" }).className).toContain("selected");
    expect(loadProductionInbox).toHaveBeenCalledTimes(1);
  });

  it("opens Lihat Rencana as a modal over the unchanged production inbox", async () => {
    vi.mocked(loadProductionInbox).mockResolvedValue({
      ...inbox,
      counts: { all: 2, kirim: 1, proses_produksi: 1 },
      items: [
        { ...inbox.items[0], status: "PROSES_PRODUKSI", plan_id: 7 },
        inbox.items[1],
      ],
    });
    render(<ProductionApp />);
    const opener = await screen.findByRole("button", { name: "Lihat rencana" });
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "Rencana Produksi #7" });
    expect(dialog.className).toContain("production-plan-dialog");
    expect(screen.getByText("Antrean Pesanan Produksi")).toBeTruthy();
    await waitFor(() => expect(dialog.textContent).toContain("100 pcs"));
    fireEvent.click(screen.getByRole("button", { name: "Tutup Rencana" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(loadProductionInbox).toHaveBeenCalledTimes(1);
  });

  it("refreshes the inbox after save and focuses the replacement Lihat Rencana action", async () => {
    const newInbox: ProductionInbox = {
      ...inbox,
      counts: { all: 2, kirim: 0, proses_produksi: 2 },
      items: inbox.items.map((row) => ({
        ...row, status: "PROSES_PRODUKSI" as const, plan_id: 7,
      })),
    };
    vi.mocked(loadProductionInbox).mockResolvedValueOnce(inbox).mockResolvedValue(newInbox);

    render(<ProductionApp />);
    const opener = (await screen.findAllByRole("button", { name: "Rencanakan" }))[0];
    fireEvent.click(opener);
    await screen.findByRole("dialog", { name: "Rencanakan Produksi" });
    fireEvent.change(screen.getByLabelText("Tanggal Produksi (manual)"), {
      target: { value: "2026-11-06" },
    });
    // The production schedules arrive with the async preview. Wait before
    // selecting PAGI, rather than firing onChange for a missing <option>.
    await screen.findByRole("option", { name: "Pagi" });
    fireEvent.change(screen.getByLabelText("Jadwal Produksi"), {
      target: { value: "PAGI" },
    });
    await waitFor(() => expect(screen.getAllByText("400 pcs").length).toBeGreaterThan(0));
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10005" }), {
      target: { value: "400" },
    });
    const saveButton = screen.getByRole("button", { name: "Simpan Konsolidasi" });
    await waitFor(() => expect((saveButton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(saveButton);
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledOnce());
    // Until the popup closes, the exact list/filter/page stays in place.
    expect(loadProductionInbox).toHaveBeenCalledTimes(1);
    await screen.findByRole("dialog", { name: "Rencana Produksi #7" });
    fireEvent.click(screen.getByRole("button", { name: "Tutup Rencana" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(loadProductionInbox).toHaveBeenCalledTimes(2));
    const historyActions = await screen.findAllByRole("button", { name: "Lihat rencana" });
    await waitFor(() => expect(document.activeElement).toBe(historyActions[0]));
    expect(screen.getByRole("button", { name: "Semua (2)" }).className).toContain("selected");
  });
});
