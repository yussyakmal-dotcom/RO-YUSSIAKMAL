import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductionApp from "./ProductionApp";
import {
  initializeSession, loadProductionDemand, loadProductionInbox,
  type ProductionDemand, type ProductionInbox, type SessionInfo,
} from "./api";

vi.mock("./api", () => ({
  initializeSession: vi.fn(),
  loadProductionDemand: vi.fn(),
  loadProductionInbox: vi.fn(),
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
      order_id: 1, status: "KIRIM", store_code: "T_BAN",
      store_name: "Toko Bandara", kitchen_code: "JP", kitchen_name: "Dapur JP",
      delivery_date: "2026-11-07", schedule_code: "SUBUH",
      schedule_name: "Subuh", sku_count: 18, qty_total: "1232.0000", qty_uom: "pcs",
      auto_submitted: false,
    },
    {
      order_id: 2, status: "KIRIM", store_code: "T_KD",
      store_name: "Toko Kedaton", kitchen_code: "JP", kitchen_name: "Dapur JP",
      delivery_date: "2026-11-07", schedule_code: "SUBUH",
      schedule_name: "Subuh", sku_count: 6, qty_total: "413.0000", qty_uom: "pcs",
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
    sku_count: 1, qty_total: "1645", qty_uom: "pcs",
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
      summary: { ...recap.summary, qty_total: "120.0000", qty_uom: "Lusin" },
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
      items: [{ ...inbox.items[0], qty_uom: null }],
    });
    render(<ProductionApp />);
    await screen.findByText("1.232 beragam UoM");
    expect(screen.queryByText("1.232 pcs")).toBeNull();
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
