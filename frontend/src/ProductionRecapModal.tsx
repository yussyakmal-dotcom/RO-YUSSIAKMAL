import { useEffect, useRef } from "react";
import { formatProductionQty, productionQtyLabel } from "./productionQty";
import {
  type ProductionDemand, type ProductionScope,
} from "./api";

type ProductionRecapModalProps = {
  order: ProductionInboxOrder;
  report: ProductionDemand | null;
  loading: boolean;
  error: string;
  onClose: () => void;
};

/**
 * Native <dialog> keeps keyboard focus inside the recap and makes the list
 * underneath inert. The parent stores the opener and restores its focus when
 * this modal closes; no route changes or filters are applied by opening it.
 */
export default function ProductionRecapModal({
  order, report, loading, error, onClose,
}: ProductionRecapModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (!dialog.open) dialog.showModal();
    closeRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  // Never briefly render a previous order's recap while the new request starts.
  const matchingReport = report &&
    report.delivery_date === order.delivery_date &&
    report.kitchen.code === order.kitchen_code &&
    report.schedule.code === order.schedule_code ? report : null;

  return (
    <dialog
      ref={dialogRef}
      className="production-recap-dialog"
      aria-labelledby="production-recap-title"
      aria-describedby="production-recap-description"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="production-recap-content">
        <header className="production-recap-header">
          <div>
            <div className="eyebrow">ADMIN PRODUKSI · REKAP KEBUTUHAN</div>
            <h2 id="production-recap-title">Rekap {order.kitchen_name}</h2>
            <p id="production-recap-description">
              Tanggal kirim {order.delivery_date} · Jadwal {order.schedule_name}
            </p>
            <p className="production-recap-context">
              Dibuka dari {order.store_name} (Order #{order.order_id}). Rekap mencakup
              semua toko dengan dapur, tanggal, dan jadwal kirim yang sama.
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="production-recap-close"
            onClick={onClose}
            aria-label="Tutup rekap dan kembali ke daftar pesanan"
            title="Tutup rekap"
          >×</button>
        </header>

        <div className="production-recap-body">
          {loading && (
            <div className="table-placeholder" role="status">
              <span className="spinner" /> Menghitung rekap kebutuhan…
            </div>
          )}
          {error && <div className="message error" role="alert">{error}</div>}
          {!loading && !error && matchingReport && (
            <>
              <div className="production-recap-summary">
                <div><span>SKU unik</span><strong>{matchingReport.summary.sku_count}</strong></div>
                <div><span>Total Qty</span><strong>{productionQtyLabel(
                  matchingReport.summary.qty_total,
                  matchingReport.summary.qty_uom,
                  matchingReport.summary.qty_by_uom,
                  matchingReport.summary.qty_invalid,
                )}</strong></div>
                <div><span>Pesanan Kirim</span><strong>{matchingReport.summary.stores_sent}</strong></div>
                <div><span>Proses Produksi</span><strong>{matchingReport.summary.stores_in_production}</strong></div>
              </div>
              <div className="production-recap-list">
                {matchingReport.items.map((item) => (
                  <details key={item.product_id} className="production-recap-item">
                    <summary>
                      <span className="production-recap-product">
                        <span className="sku">{item.sku || "—"}</span>
                        <strong>{item.name}</strong>
                        <small>{item.store_count} toko</small>
                      </span>
                      <span className="production-recap-quantity">{productionQtyLabel(item.qty_total, item.uom)}</span>
                    </summary>
                    <div className="production-recap-sources">
                      {item.sources.map((source) => (
                        <div className="production-recap-source" key={source.order_id}>
                          <div>
                            <strong>{source.store_name}</strong>
                            <small>
                              {source.store_code} · Order #{source.order_id} ·
                              {source.status === "KIRIM" ? " Kirim" : " Proses Produksi"}
                            </small>
                          </div>
                          <strong>{formatProductionQty(source.qty)} {item.uom}</strong>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
                {!matchingReport.items.length && (
                  <p className="production-recap-empty">Belum ada baris SKU final pada lingkup ini.</p>
                )}
              </div>
              <p className="production-recap-disclaimer">
                Rekap hanya untuk melihat data. Tidak mengubah status pesanan,
                Qty, ProductionPlan, atau Odoo.
              </p>
            </>
          )}
        </div>

        <footer className="production-recap-footer">
          <span>Tekan Esc untuk menutup dan kembali ke daftar.</span>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Tutup Rekap
          </button>
        </footer>
      </div>
    </dialog>
  );
}
