import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import FontSizeControl from "./FontSizeControl";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.style.removeProperty("--font-size-adjustment");
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Font size preference", () => {
  it("changes all text by one point per click and restores the preference on remount", () => {
    const view = render(<FontSizeControl />);
    const increase = screen.getByRole("button", { name: "Perbesar semua teks 1 poin" });
    fireEvent.click(increase);
    fireEvent.click(increase);
    expect(document.documentElement.style.getPropertyValue("--font-size-adjustment")).toBe("2pt");
    fireEvent.click(screen.getByRole("button", { name: "Perkecil semua teks 1 poin" }));
    expect(screen.getByRole("status").textContent).toBe("+1 pt");
    view.unmount();
    render(<FontSizeControl />);
    expect(screen.getByRole("status").textContent).toBe("+1 pt");
    expect(document.documentElement.style.getPropertyValue("--font-size-adjustment")).toBe("1pt");
  });

  it("limits the preference and ignores invalid saved values", () => {
    localStorage.setItem("ro-font-size-adjustment", "invalid");
    render(<FontSizeControl />);
    expect(screen.getByRole("status").textContent).toBe("0 pt");
    const increase = screen.getByRole("button", { name: "Perbesar semua teks 1 poin" });
    for (let i = 0; i < 15; i++) fireEvent.click(increase);
    expect((increase as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("+10 pt");
    const decrease = screen.getByRole("button", { name: "Perkecil semua teks 1 poin" });
    for (let i = 0; i < 20; i++) fireEvent.click(decrease);
    expect((decrease as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("-2 pt");
  });

  it("works when the browser blocks preference storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<FontSizeControl />);
    fireEvent.click(screen.getByRole("button", { name: "Perbesar semua teks 1 poin" }));
    expect(document.documentElement.style.getPropertyValue("--font-size-adjustment")).toBe("1pt");
  });
});
