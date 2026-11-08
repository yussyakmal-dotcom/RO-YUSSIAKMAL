import { useLayoutEffect, useState } from "react";

const STORAGE_KEY = "ro-font-size-adjustment";
const MIN_POINTS = -2;
const MAX_POINTS = 10;

function readPreference(): number {
  try {
    const value = Number(window.localStorage.getItem(STORAGE_KEY));
    return Number.isInteger(value) && value >= MIN_POINTS && value <= MAX_POINTS
      ? value : 0;
  } catch {
    return 0;
  }
}

export default function FontSizeControl() {
  const [points, setPoints] = useState(readPreference);

  useLayoutEffect(() => {
    document.documentElement.style.setProperty("--font-size-adjustment", `${points}pt`);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(points));
    } catch {
      // The control still works when browser storage is unavailable.
    }
  }, [points]);

  return (
    <div className="font-size-control" role="group" aria-label="Ukuran teks">
      <span className="font-size-label">Teks</span>
      <button
        type="button" disabled={points <= MIN_POINTS}
        aria-label="Perkecil semua teks 1 poin"
        title="Perkecil semua teks 1 poin"
        onClick={() => setPoints((value) => Math.max(MIN_POINTS, value - 1))}
      >−</button>
      <span className="font-size-value" role="status" aria-live="polite" aria-atomic="true">
        {points > 0 ? "+" : ""}{points} pt
      </span>
      <button
        type="button" disabled={points >= MAX_POINTS}
        aria-label="Perbesar semua teks 1 poin"
        title="Perbesar semua teks 1 poin"
        onClick={() => setPoints((value) => Math.min(MAX_POINTS, value + 1))}
      >+</button>
    </div>
  );
}
