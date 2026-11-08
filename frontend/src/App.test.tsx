import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import {
  initializeSession, loadOrder, logout, saveDraft, sendOrder,
  type SessionInfo, type StoreOrder,
} from "./api";

vi.mock("./api", () => ({
  initializeSession: vi.fn(), loadOrder: vi.fn(), login: vi.fn(),
  logout: vi.fn(), saveDraft: vi.fn(), sendOrder: vi.fn(),
}));

const session: SessionInfo = {
  user: {
    username: "store", full_name: "Admin Toko", admin: false,
    can_access_store: true, can_access_production: false,
  },
  stores: [{ code: "T_BAN", name: "Toko Bandara" }],
  kitchens: [{ code: "JP", name: "Dapur JP", item_count: 1 }],
  schedules: [{ code: "SUBUH", name: "Subuh" }, { code: "PAGI", name: "Pagi" }],
};

const draft: StoreOrder = {
  id: 1, status: "DRAFT", editable: true, auto_submitted: false,
  store: session.stores[0], kitchen: session.kitchens[0],
  delivery_date: "2026-11-09", schedule: "SUBUH",
  items: [{ product_id: 10, sku: "10005", name: "Risoles", qty: "0", active_in_template: true }],
};
const saved: StoreOrder = { ...draft, items: [{ ...draft.items[0], qty: "5" }] };

function unloadIsBlocked() {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

async function editQty() {
  fireEvent.change(await screen.findByRole("textbox", { name: "Qty Risoles" }), {
    target: { value: "5" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(initializeSession).mockResolvedValue(session);
  vi.mocked(loadOrder).mockResolvedValue(draft);
  vi.mocked(saveDraft).mockResolvedValue(saved);
  vi.mocked(logout).mockResolvedValue();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Admin Toko unsaved Qty protection", () => {
  it("allows leaving an unchanged form and warns after editing, without saving automatically", async () => {
    const view = render(<App />);
    await screen.findByRole("textbox", { name: "Qty Risoles" });
    expect(unloadIsBlocked()).toBe(false);
    await editQty();
    expect(unloadIsBlocked()).toBe(true);
    expect(saveDraft).not.toHaveBeenCalled();
    expect(sendOrder).not.toHaveBeenCalled();
    view.unmount();
    expect(unloadIsBlocked()).toBe(false);
  });

  it("keeps warning during a pending save and removes it only after successful saving", async () => {
    let completeSave!: (order: StoreOrder) => void;
    vi.mocked(saveDraft).mockReturnValue(new Promise((resolve) => { completeSave = resolve; }));
    render(<App />);
    await editQty();
    fireEvent.click(screen.getByRole("button", { name: "Simpan Draft" }));
    expect(unloadIsBlocked()).toBe(true);
    await act(async () => { completeSave(saved); });
    await screen.findByText("Draft tersimpan. Pesanan ini masih dapat dibuka dan Qty masih bisa diedit.");
    expect(unloadIsBlocked()).toBe(false);
    fireEvent.change(screen.getByRole("textbox", { name: "Qty Risoles" }), { target: { value: "6" } });
    expect(unloadIsBlocked()).toBe(true);
  });

  it("preserves Qty and the warning when saving fails", async () => {
    vi.mocked(saveDraft).mockRejectedValue(new Error("Koneksi terputus"));
    render(<App />);
    await editQty();
    fireEvent.click(screen.getByRole("button", { name: "Simpan Draft" }));
    await screen.findByRole("alert");
    expect((screen.getByRole("textbox", { name: "Qty Risoles" }) as HTMLInputElement).value).toBe("5");
    expect(unloadIsBlocked()).toBe(true);
  });

  it("removes the warning after Kirim succeeds and the final order is loaded", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(sendOrder).mockResolvedValue({
      id: 1, status: "KIRIM", editable: false, items_sent: 1, excluded_below_one: 0,
    });
    vi.mocked(loadOrder).mockResolvedValueOnce(draft).mockResolvedValue({ ...saved, status: "KIRIM", editable: false });
    render(<App />);
    await editQty();
    fireEvent.click(screen.getByRole("button", { name: "Kirim Pesanan" }));
    await screen.findByText("Pesanan berhasil dikirim: 1 SKU. Qty sekarang terkunci.");
    expect(saveDraft).toHaveBeenCalledOnce();
    expect(sendOrder).toHaveBeenCalledExactlyOnceWith(1);
    expect(unloadIsBlocked()).toBe(false);
    expect(screen.queryByRole("textbox", { name: "Qty Risoles" })).toBeNull();
  });

  it("keeps the existing context-switch and logout confirmations when edits are discarded or canceled", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<App />);
    await editQty();
    fireEvent.change(screen.getByLabelText("Jadwal Kirim"), { target: { value: "PAGI" } });
    fireEvent.click(screen.getByRole("button", { name: "Keluar" }));
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(logout).not.toHaveBeenCalled();
    expect(loadOrder).toHaveBeenCalledOnce();
    expect(unloadIsBlocked()).toBe(true);
    confirm.mockReturnValue(true);
    fireEvent.change(screen.getByLabelText("Jadwal Kirim"), { target: { value: "PAGI" } });
    await waitFor(() => expect(loadOrder).toHaveBeenCalledTimes(2));
    expect(unloadIsBlocked()).toBe(false);
  });

  it.each(["KIRIM", "PROSES_PRODUKSI", "NO_ORDER"] as const)("does not warn for a read-only %s order", async (status) => {
    vi.mocked(loadOrder).mockResolvedValue({ ...saved, status, editable: false });
    render(<App />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Simpan Draft" }) as HTMLButtonElement).disabled).toBe(true));
    await screen.findByText("Pesanan final bersifat hanya baca.");
    expect(unloadIsBlocked()).toBe(false);
  });
});
