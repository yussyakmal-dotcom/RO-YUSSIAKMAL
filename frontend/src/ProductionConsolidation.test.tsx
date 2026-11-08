import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductionConsolidation from "./ProductionConsolidation";
import {
  loadConsolidationPreview, loadConsolidationDetail, saveConsolidation,
  loadProductionDraft, saveProductionDraft,
  type ProductionInboxOrder, type ConsolidationPreview, type ConsolidationDetail,
} from "./api";

vi.mock("./api", () => ({
  loadConsolidationPreview: vi.fn(),
  loadConsolidationDetail: vi.fn(),
  saveConsolidation: vi.fn(),
  loadProductionDraft: vi.fn(),
  saveProductionDraft: vi.fn(),
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
    uom: "Pcs", qty_requested: "500", bom_output_qty: "100",
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
  vi.mocked(loadProductionDraft).mockResolvedValue({ draft: null });
  vi.mocked(saveProductionDraft).mockResolvedValue({
    draft: { id: 12, version: 1, production_date: null,
      production_schedule_code: null, order_ids: [1, 2], items: [],
      updated_at: "2026-11-08T10:00:00+07:00", updated_by: "admin_produksi" },
  });
  vi.mocked(loadConsolidationDetail).mockResolvedValue(detail);
  vi.mocked(saveConsolidation).mockResolvedValue({
    plan_id: 7, order_ids: [1, 2], shortfall_sku_count: 1,
    detail: "Konsolidasi tersimpan.",
  });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); document.body.style.overflow = ""; });

describe("Konsolidasi Produksi V1", () => {
  it("only informs the recipe output and saves the operator's quantity without rounding or choosing recipes", async () => {
    vi.mocked(loadConsolidationPreview).mockImplementation(async (scope) => ({
      ...preview, production_date: scope.production_date || null,
      production_schedule: scope.production_schedule_code ? schedules[1] : null,
      items: [{ ...preview.items[0], qty_requested: "150", bom_output_qty: "100",
        capacity_qty: "300", capacity_used: "0", capacity_available: "300" }],
    }));
    render(<ProductionConsolidation order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Tanggal Produksi (manual)"), { target: { value: "2026-11-06" } });
    await screen.findByRole("option", { name: "Pagi" });
    fireEvent.change(screen.getByLabelText("Jadwal Produksi"), { target: { value: "PAGI" } });
    const input = await screen.findByRole("textbox", { name: "Qty Produksi 10005" });
    const save = screen.getByRole("button", { name: "Simpan Konsolidasi" });
    expect(screen.getByRole("columnheader", { name: "Hasil 1 Resep BoM" })).toBeTruthy();
    expect(screen.getByText("100 Pcs")).toBeTruthy();
    fireEvent.change(input, { target: { value: "150" } });
    expect((input as HTMLInputElement).value).toBe("150");
    expect(screen.queryByText("200 Pcs")).toBeNull();
    expect(screen.queryByText("2 resep")).toBeNull();
    expect((save as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(input, { target: { value: "300" } });
    expect((save as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(input, { target: { value: "301" } });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(input, { target: { value: "150" } });
    fireEvent.click(save);
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledWith(expect.objectContaining({
      items: [{ product_id: 5, qty_planned: "150" }],
    })));
  });

  it("searches SKU or name without losing Qty, bypassing hidden validation, or omitting hidden SKU on save", async () => {
    vi.mocked(loadConsolidationPreview).mockImplementation(async (scope) => ({
      ...preview,
      production_date: scope.production_date || null,
      production_schedule: scope.production_schedule_code ? schedules[1] : null,
      items: [preview.items[0], {
        ...preview.items[0], product_id: 6, sku: "10006", name: "Lemper Ayam",
      }].map((item) => ({
        ...item, capacity_qty: "400", capacity_used: "0", capacity_available: "400",
      })),
    }));
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()}
    />);
    fireEvent.change(screen.getByLabelText("Tanggal Produksi (manual)"), {
      target: { value: "2026-11-06" },
    });
    await screen.findByRole("option", { name: "Pagi" });
    fireEvent.change(screen.getByLabelText("Jadwal Produksi"), {
      target: { value: "PAGI" },
    });
    await screen.findByRole("textbox", { name: "Qty Produksi 10006" });
    const search = screen.getByRole("searchbox", { name: "Cari SKU atau nama produk" });
    const save = screen.getByRole("button", { name: "Simpan Konsolidasi" });
    const previewCalls = vi.mocked(loadConsolidationPreview).mock.calls.length;

    fireEvent.change(search, { target: { value: "10005" } });
    expect(screen.queryByText("Lemper Ayam")).toBeNull();
    expect(screen.getByText("1 dari 2 SKU ditampilkan")).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10005" }), {
      target: { value: "400" },
    });
    // A hidden, unfilled SKU must still prevent saving the entire consolidation.
    expect((save as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(search, { target: { value: "  LEMPER  " } });
    expect(screen.queryByText("Arem-arem Sultan Mini")).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10006" }), {
      target: { value: "300" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Hapus pencarian" }));
    expect((screen.getByRole("textbox", { name: "Qty Produksi 10005" }) as HTMLInputElement).value).toBe("400");
    expect((screen.getByRole("textbox", { name: "Qty Produksi 10006" }) as HTMLInputElement).value).toBe("300");

    fireEvent.change(search, { target: { value: "tidak ditemukan" } });
    expect(screen.getByText("0 dari 2 SKU ditampilkan")).toBeTruthy();
    expect(screen.getByText("Tidak ada SKU atau nama produk yang cocok dengan pencarian.")).toBeTruthy();
    expect((save as HTMLButtonElement).disabled).toBe(false);
    expect(loadConsolidationPreview).toHaveBeenCalledTimes(previewCalls);
    fireEvent.click(save);
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledWith(expect.objectContaining({
      order_ids: [1, 2],
      items: [
        { product_id: 5, qty_planned: "400" },
        { product_id: 6, qty_planned: "300" },
      ],
    })));
  });

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
    await waitFor(() => expect(screen.getByRole("row", { name: /Arem-arem Sultan Mini/ }).querySelectorAll("td")[7].textContent).toBe("100 Pcs"));
    expect((saveButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(saveButton);
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledWith({
      kitchen_code: "JP", delivery_date: "2026-11-07",
      delivery_schedule_code: "SUBUH",
      production_date: "2026-11-06", production_schedule_code: "PAGI",
      order_ids: [1, 2],
      draft_version: 0,
      items: [{ product_id: 5, qty_planned: "400" }],
    }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByText("Rencana Produksi #7")).toBeTruthy());
    expect(screen.getByRole("row", { name: /Arem-arem Sultan Mini/ }).querySelectorAll("td")[7].textContent).toBe("100 Pcs");
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
    await waitFor(() => expect(screen.getByRole("row", { name: /Arem-arem Sultan Mini/ }).querySelectorAll("td")[7].textContent).toBe("100 Pcs"));
    expect(screen.queryByRole("textbox", { name: "Qty Produksi 10005" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Simpan Konsolidasi" })).toBeNull();
    expect(screen.getByText("Subuh")).toBeTruthy();
    expect(screen.getByText("Pagi")).toBeTruthy();
  });
});


describe("Draft rencana produksi dapat dilanjutkan", () => {
  it("saves incomplete draft without requiring dates, slots, Qty or finalization", async () => {
    const onDraftSaved = vi.fn();
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()} onDraftSaved={onDraftSaved}
    />);
    const draftButton = screen.getByRole("button", { name: "Simpan Draft" });
    await waitFor(() => expect((draftButton as HTMLButtonElement).disabled).toBe(false));
    expect((screen.getByRole("button", {
      name: "Simpan Konsolidasi",
    }) as HTMLButtonElement).disabled).toBe(true);
    const qtyInput = screen.getByRole("textbox", { name: "Qty Produksi 10005" });
    fireEvent.change(qtyInput, { target: { value: "250" } });
    expect((qtyInput as HTMLInputElement).value).toBe("250");
    fireEvent.click(draftButton);
    await waitFor(() => expect(saveProductionDraft).toHaveBeenCalledWith({
      kitchen_code: "JP",
      delivery_date: "2026-11-07",
      delivery_schedule_code: "SUBUH",
      production_date: null,
      production_schedule_code: "",
      order_ids: [1, 2],
      items: [{ product_id: 5, qty_planned: "250" }],
      version: 0,
    }));
    await waitFor(() => expect(onDraftSaved).toHaveBeenCalledOnce());
    expect(saveConsolidation).not.toHaveBeenCalled();
    expect(screen.getByText(/Draft tersimpan. Anda dapat menutup pop-up/)).toBeTruthy();
    expect(screen.getByRole("dialog", { name: "Rencanakan Produksi" })).toBeTruthy();
  });

  it("restores saved date, production slot and partial Qty after reopening the popup", async () => {
    vi.mocked(loadProductionDraft).mockResolvedValue({
      draft: {
        id: 33, version: 5,
        production_date: "2026-11-06",
        production_schedule_code: "PAGI",
        order_ids: [1, 2],
        items: [{ product_id: 5, qty_planned: "325" }],
        updated_at: "2026-11-08T10:00:00+07:00",
        updated_by: "admin_produksi",
      },
    });
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()} onDraftSaved={vi.fn()}
    />);
    await waitFor(() => expect(
      (screen.getByLabelText("Tanggal Produksi (manual)") as HTMLInputElement).value
    ).toBe("2026-11-06"));
    await waitFor(() => expect(
      (screen.getByLabelText("Jadwal Produksi") as HTMLSelectElement).value
    ).toBe("PAGI"));
    await waitFor(() => expect(
      (screen.getByRole("textbox", { name: "Qty Produksi 10005" }) as HTMLInputElement).value
    ).toBe("325"));
    expect(screen.getByText(/Draft tersimpan/)).toBeTruthy();
    expect(screen.getByText(/admin_produksi/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Simpan Konsolidasi" }));
    await waitFor(() => expect(saveConsolidation).toHaveBeenCalledWith(
      expect.objectContaining({
        draft_version: 5,
        production_date: "2026-11-06",
        production_schedule_code: "PAGI",
        items: [{ product_id: 5, qty_planned: "325" }],
      })
    ));
  });

  it("prevents accidental discarding of unsaved changes", async () => {
    const onBack = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={onBack} onSaved={vi.fn()}
    />);
    await screen.findByRole("textbox", { name: "Qty Produksi 10005" });
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10005" }), {
      target: { value: "250" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Batal / Tutup" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(onBack).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("keeps modal open on draft save conflicts, instead of losing inputs", async () => {
    vi.mocked(saveProductionDraft).mockRejectedValueOnce(
      new Error("Draft diperbarui operator lain.")
    );
    render(<ProductionConsolidation
      order={order} planId={null} schedules={schedules}
      onBack={vi.fn()} onSaved={vi.fn()}
    />);
    const saveDraftButton = screen.getByRole("button", { name: "Simpan Draft" });
    await waitFor(() => expect((saveDraftButton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Produksi 10005" }), {
      target: { value: "300" },
    });
    fireEvent.click(saveDraftButton);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain(
      "Draft diperbarui operator lain"
    ));
    expect((screen.getByRole("textbox", {
      name: "Qty Produksi 10005",
    }) as HTMLInputElement).value).toBe("300");
    expect(saveConsolidation).not.toHaveBeenCalled();
  });
});
