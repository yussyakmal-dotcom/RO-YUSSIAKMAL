import { useEffect, useMemo, useRef, useState } from "react";
import {
  loadConsolidationPreview, loadConsolidationDetail, saveConsolidation,
  loadProductionDraft, saveProductionDraft,
  type ConsolidationDetail, type ConsolidationPreview,
  type ConsolidationItem, type ProductionInboxOrder,
  type NamedOption,
} from "./api";
import { formatProductionQty } from "./productionQty";

type Props = {
  order: ProductionInboxOrder;
  planId: number | null;
  schedules: NamedOption[];
  onBack: () => void;
  onSaved: () => void;
  onDraftSaved?: () => void;
};

function qty(value: string | null, uom: string): string {
  return value === null ? "Belum diatur" : `${formatProductionQty(value)} ${uom}`;
}

function shortage(requested: string, planned: string): string | null {
  if (!/^\d+$/.test(requested) || !/^\d+$/.test(planned)) return null;
  const gap = BigInt(requested) - BigInt(planned);
  return gap > 0n ? String(gap) : "0";
}

function isValidPlan(item: ConsolidationItem, input: string): boolean {
  if (!/^\d+$/.test(input) || !item.capacity_available) return false;
  const n = BigInt(input);
  return n > 0n && n <= BigInt(item.capacity_available);
}

function draftSignature(
  date: string, schedule: string, values: Record<number, string>,
): string {
  return JSON.stringify({
    production_date: date,
    production_schedule_code: schedule,
    items: Object.entries(values)
      .filter(([, value]) => value !== "")
      .sort(([a], [b]) => Number(a) - Number(b)),
  });
}

/** Native modal: keep the inbox mounted, keyboard focus inside, and scroll in the popup. */
export default function ProductionConsolidation({
  order, planId, schedules, onBack, onSaved, onDraftSaved,
}: Props) {
  const [productionDate, setProductionDate] = useState("");
  const [productionScheduleCode, setProductionScheduleCode] = useState("");
  const [preview, setPreview] = useState<ConsolidationPreview | null>(null);
  const [detail, setDetail] = useState<ConsolidationDetail | null>(null);
  const [savedPlanId, setSavedPlanId] = useState<number | null>(planId);
  const [planned, setPlanned] = useState<Record<number, string>>({});
  const [draftLoading, setDraftLoading] = useState(planId === null);
  const [draftVersion, setDraftVersion] = useState(0);
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null);
  const [draftSavedBy, setDraftSavedBy] = useState<string | null>(null);
  const [savedDraftSignature, setSavedDraftSignature] = useState(
    draftSignature("", "", {}),
  );
  const [draftMessage, setDraftMessage] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
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

  const draftDirty = draftSignature(
    productionDate, productionScheduleCode, planned,
  ) !== savedDraftSignature;

  // A submitted plan must not be interrupted by closing the popup.
  const closeModal = () => {
    if (saving) return;
    if (!savedPlanId && draftDirty && !window.confirm(
      "Ada perubahan yang belum disimpan sebagai Draft. Tutup tanpa menyimpan?"
    )) return;
    onBack();
  };

  useEffect(() => {
    if (planId !== null) return;
    const controller = new AbortController();
    setDraftLoading(true);
    loadProductionDraft({
      kitchen_code: order.kitchen_code,
      delivery_date: order.delivery_date,
      delivery_schedule_code: order.schedule_code,
    }, controller.signal).then(({ draft }) => {
      if (controller.signal.aborted) return;
      if (draft) {
        const date = draft.production_date || "";
        const slot = draft.production_schedule_code || "";
        const items = Object.fromEntries(
          draft.items.map((item) => [item.product_id, item.qty_planned]),
        );
        setProductionDate(date);
        setProductionScheduleCode(slot);
        setPlanned(items);
        setSavedDraftSignature(draftSignature(date, slot, items));
        setDraftVersion(draft.version);
        setDraftSavedAt(draft.updated_at);
        setDraftSavedBy(draft.updated_by);
      }
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(
        reason instanceof Error ? reason.message : "Draft gagal dimuat."
      );
    }).finally(() => {
      if (!controller.signal.aborted) setDraftLoading(false);
    });
    return () => controller.abort();
  }, [
    order.kitchen_code, order.delivery_date, order.schedule_code, planId,
  ]);

  useEffect(() => {
    if (!savedPlanId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    loadConsolidationDetail(savedPlanId, controller.signal).then((result) => {
      if (!controller.signal.aborted) setDetail(result);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(
        reason instanceof Error ? reason.message : "Gagal memuat rencana produksi."
      );
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [savedPlanId]);

  useEffect(() => {
    if (savedPlanId || draftLoading) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setPreview(null);
    loadConsolidationPreview({
      kitchen_code: order.kitchen_code,
      delivery_date: order.delivery_date,
      delivery_schedule_code: order.schedule_code,
      ...(productionDate ? { production_date: productionDate } : {}),
      ...(productionScheduleCode ? {
        production_schedule_code: productionScheduleCode,
      } : {}),
    }, controller.signal).then((result) => {
      if (!controller.signal.aborted) {
        setPreview(result);
        setPlanned((prev) => Object.fromEntries(
          result.items.map((item) => [item.product_id, prev[item.product_id] ?? ""])
        ));
      }
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(
        reason instanceof Error ? reason.message : "Gagal menghitung kebutuhan."
      );
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [
    order.kitchen_code, order.delivery_date, order.schedule_code,
    productionDate, productionScheduleCode, savedPlanId, draftLoading,
  ]);

  const hasInvalidRows = useMemo(
    () => !preview || preview.items.length === 0 ||
      preview.items.some((item) => !isValidPlan(
        item, planned[item.product_id] || "",
      )),
    [preview, planned],
  );
  const canSave = !savedPlanId && !draftLoading && !loading && !saving &&
    !!productionDate && !!productionScheduleCode && !hasInvalidRows;
  const canSaveDraft = !savedPlanId && !draftLoading && !loading && !saving && !!preview;

  const saveDraft = async () => {
    if (!canSaveDraft || !preview) return;
    setSaving(true);
    setError("");
    setDraftMessage("");
    try {
      const values = preview.items.map((item) => ({
        product_id: item.product_id,
        qty_planned: planned[item.product_id] ?? "",
      }));
      const { draft } = await saveProductionDraft({
        kitchen_code: order.kitchen_code,
        delivery_date: order.delivery_date,
        delivery_schedule_code: order.schedule_code,
        production_date: productionDate || null,
        production_schedule_code: productionScheduleCode,
        order_ids: preview.order_ids,
        items: values,
        version: draftVersion,
      });
      setDraftVersion(draft.version);
      setDraftSavedAt(draft.updated_at);
      setDraftSavedBy(draft.updated_by);
      setSavedDraftSignature(draftSignature(
        productionDate, productionScheduleCode, planned,
      ));
      setDraftMessage("Draft tersimpan. Anda dapat menutup pop-up dan melanjutkan nanti.");
      onDraftSaved?.();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Gagal menyimpan draft."
      );
    } finally {
      setSaving(false);
    }
  };

  const submit = async () => {
    if (!canSave || !preview) return;
    setError("");
    setSaving(true);
    try {
      const result = await saveConsolidation({
        kitchen_code: order.kitchen_code,
        delivery_date: order.delivery_date,
        delivery_schedule_code: order.schedule_code,
        production_date: productionDate,
        production_schedule_code: productionScheduleCode,
        order_ids: preview.order_ids,
        draft_version: draftVersion,
        items: preview.items.map((item) => ({
          product_id: item.product_id,
          qty_planned: planned[item.product_id],
        })),
      });
      setSavedPlanId(result.plan_id);
      onSaved();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Gagal menyimpan konsolidasi."
      );
    } finally {
      setSaving(false);
    }
  };

  const viewing = savedPlanId !== null;
  const rows: (ConsolidationItem & {
    qty_planned?: string; qty_shortfall?: string;
  })[] = viewing ? (detail?.items || []) : (preview?.items || []);
  const searchTerm = search.trim().toLocaleLowerCase("id-ID");
  const visibleRows = rows.filter((item) =>
    item.sku.toLocaleLowerCase("id-ID").includes(searchTerm) ||
    item.name.toLocaleLowerCase("id-ID").includes(searchTerm)
  );
  const activeSchedules = viewing ? [] : (preview?.production_schedules || schedules);
  const shortfallCount = viewing
    ? detail?.shortfall_sku_count
    : rows.filter((row) => {
      const gap = shortage(row.qty_requested, planned[row.product_id] || "");
      return gap !== null && gap !== "0";
    }).length;

  return (
    <dialog
      ref={dialogRef}
      className="production-recap-dialog production-plan-dialog"
      aria-labelledby="production-plan-title"
      aria-describedby="production-plan-description"
      onCancel={(event) => { event.preventDefault(); closeModal(); }}
      onClick={(event) => {
        if (event.target === event.currentTarget) closeModal();
      }}
    >
      <div className="production-plan-modal-content">
        <header className="production-recap-header production-plan-modal-header">
          <div>
            <div className="eyebrow">ADMIN PRODUKSI · {viewing ? "RIWAYAT RENCANA" : (draftVersion ? "LANJUTKAN DRAFT" : "KONSOLIDASI BARU")}</div>
            <h2 id="production-plan-title">{viewing ? `Rencana Produksi #${savedPlanId}` : "Rencanakan Produksi"}</h2>
            <p id="production-plan-description">
              {order.kitchen_name} · Tanggal kirim {order.delivery_date} · Jadwal kirim {order.schedule_name}
            </p>
            <p>Qty pesan toko tetap terkunci. Kekurangan produksi boleh dicatat tanpa memindahkan jadwal kirim.</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="production-recap-close"
            disabled={saving}
            aria-label="Tutup rencana dan kembali ke daftar pesanan"
            title="Tutup rencana"
            onClick={closeModal}
          >×</button>
        </header>
        <div className="production-plan-modal-body">
          <div className="production-consolidation">
      <section className="card production-plan-scope">
        <div className="section-heading">Identitas pengiriman & produksi</div>
        <div className="production-plan-fields">
          <div><span>Dapur</span><strong>{order.kitchen_name}</strong></div>
          <div><span>Tanggal Kirim (toko)</span><strong>{order.delivery_date}</strong></div>
          <div><span>Jadwal Kirim (toko)</span><strong>{order.schedule_name}</strong></div>
          <div>
            <label htmlFor="production-date">Tanggal Produksi (manual)</label>
            {viewing ? <strong>{detail?.production_date || "—"}</strong> : (
              <input id="production-date" type="date" value={productionDate}
                onChange={(event) => setProductionDate(event.target.value)} disabled={draftLoading} required />
            )}
          </div>
          <div>
            <label htmlFor="production-schedule">Jadwal Produksi</label>
            {viewing ? <strong>{detail?.production_schedule?.name || "—"}</strong> : (
              <select id="production-schedule" value={productionScheduleCode}
                onChange={(event) => setProductionScheduleCode(event.target.value)} disabled={draftLoading} required>
                <option value="">Pilih jadwal produksi</option>
                {activeSchedules.map((schedule) => (
                  <option value={schedule.code} key={schedule.code}>
                    {schedule.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
        <p className="production-plan-scope-note">
          Tanggal/jadwal kirim ditetapkan Admin Toko dan tidak dapat dipindahkan oleh Admin Produksi.
          {viewing && detail ? ` Sumber: ${detail.sources.map((source) =>
            `${source.store_code} #${source.order_id}`).join(", ")}.` : (
              preview ? ` Pesanan KIRIM: ${preview.orders.map((source) =>
                `${source.store_code} #${source.order_id}`).join(", ")}.` : ""
            )}
        </p>
      </section>

      {!viewing && draftLoading && <div role="status" className="table-placeholder">
        <span className="spinner" /> Memuat draft tersimpan…
      </div>}
      {!viewing && !draftLoading && (
        <p role="status" className="production-draft-status">
          {draftDirty
            ? "Perubahan belum disimpan sebagai Draft."
            : draftSavedAt
              ? `Draft tersimpan ${new Date(draftSavedAt).toLocaleString("id-ID")}${draftSavedBy ? ` oleh ${draftSavedBy}` : ""}.`
              : "Belum ada draft tersimpan."}
        </p>
      )}
      {draftMessage && <div role="status" className="message success">{draftMessage}</div>}
      {error && <div role="alert" className="message error">{error}</div>}
      {loading && <div role="status" className="table-placeholder"><span className="spinner" /> Menghitung rencana dan kapasitas…</div>}
      {!loading && rows.length > 0 && (
        <section className="card production-plan-card">
          <div className="order-title-bar">
            <div>
              <div className="section-heading">Qty Pesan, Resep BoM & Qty Produksi</div>
              <p>{rows.length} SKU · {viewing ? "Histori rencana tersimpan" : "Qty Produksi ditentukan manual oleh Admin Produksi"}</p>
            </div>
            {!!shortfallCount && <span className="production-plan-alert">
              {shortfallCount} SKU memiliki kekurangan
            </span>}
          </div>
          <div className="filters-row">
            <label className="search-box">
              <span aria-hidden="true">⌕</span>
              <input
                type="search"
                aria-label="Cari SKU atau nama produk"
                placeholder="Cari SKU atau nama produk…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            {search && (
              <button type="button" className="ghost-btn" onClick={() => setSearch("")}>
                Hapus pencarian
              </button>
            )}
            <span className="result-count" role="status">
              {visibleRows.length} dari {rows.length} SKU ditampilkan
            </span>
          </div>
          <div className="table-scroll">
            <table className="production-plan-table">
              <thead><tr>
                <th>SKU / Nama</th><th>Qty Pesan</th><th>Hasil 1 Resep BoM</th><th>Kapasitas</th>
                <th>Terpakai</th><th>Tersisa</th><th>Qty Produksi</th>
                <th>Kekurangan</th><th>Kelebihan Produksi</th>
              </tr></thead>
              <tbody>
                {visibleRows.map((item) => {
                  const value = viewing ? item.qty_planned || "" : planned[item.product_id] || "";
                  const gap = viewing ? (item.qty_shortfall || "0") :
                    shortage(item.qty_requested, value);
                  const surplus = shortage(value, item.qty_requested);
                  const overCapacity = !!item.capacity_available &&
                    BigInt(item.qty_requested) > BigInt(item.capacity_available);
                  const invalid = !viewing && value !== "" && !isValidPlan(item, value);
                  return (
                    <tr key={item.product_id}>
                      <td><strong>{item.sku || "—"}</strong><small>{item.name}</small></td>
                      <td><strong>{qty(item.qty_requested, item.uom)}</strong></td>
                      <td>{item.bom_output_qty === null ? "Belum tersedia" : qty(item.bom_output_qty, item.uom)}</td>
                      <td>{qty(item.capacity_qty, item.uom)}</td>
                      <td>{item.capacity_used === null ? "—" : qty(item.capacity_used, item.uom)}</td>
                      <td className={overCapacity ? "production-plan-alert" : ""}>
                        {qty(item.capacity_available, item.uom)}
                      </td>
                      <td>{viewing ? (
                        <strong>{qty(value, item.uom)}</strong>
                      ) : (
                        <>
                          <input
                            aria-label={`Qty Produksi ${item.sku || item.name}`}
                            type="text" inputMode="numeric" pattern="[0-9]*"
                            className="production-qty-input"
                            value={value}
                            onChange={(event) => {
                              if (/^\d*$/.test(event.target.value)) {
                                setPlanned((prev) => ({
                                  ...prev, [item.product_id]: event.target.value,
                                }));
                              }
                            }}
                            aria-invalid={invalid}
                            disabled={draftLoading}
                            placeholder="Isi Qty"
                          />
                          <small>{item.uom}</small>
                        </>
                      )}</td>
                      <td className={gap && gap !== "0" ? "production-plan-alert" : ""}>
                        {gap === null ? "—" : qty(gap, item.uom)}
                        {invalid && <small>Periksa Qty / kapasitas</small>}
                      </td>
                      <td>{surplus === null ? "—" : qty(surplus, item.uom)}</td>
                    </tr>
                  );
                })}
                {visibleRows.length === 0 && (
                  <tr><td colSpan={9} className="empty-table">
                    Tidak ada SKU atau nama produk yang cocok dengan pencarian.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          {viewing ? (
            <p className="production-plan-scope-note">{detail?.note}</p>
          ) : (
            <p className="production-plan-scope-note">
              Hasil 1 Resep BoM adalah informasi untuk Admin Produksi.
              Qty Produksi diisi manual, boleh melebihi Qty Pesan, maksimal kapasitas tersisa.
              Sistem tidak menentukan jumlah resep atau membulatkan Qty.
              Kelebihan Produksi belum dialokasikan ke toko atau WIP.
              Pesanan toko tetap utuh; belum membuat MO Odoo.
            </p>
          )}
        </section>
      )}
      {viewing && <p className="production-plan-scope-note">
        Rencana tersimpan secara lokal. Status pesanan sumber sudah PROSES_PRODUKSI.
        Kekurangan tetap tercatat; belum membuat Manufacturing Order Odoo.
      </p>}
          </div>
        </div>
        <footer className="production-recap-footer production-plan-modal-footer">
          <span>{viewing ? "Tekan Esc untuk kembali ke daftar." : "Simpan Draft untuk melanjutkan nanti. Batal/Tutup tidak menyimpan perubahan."}</span>
          <div className="action-buttons">
            <button type="button" className="btn btn-secondary" disabled={saving} onClick={closeModal}>
              {viewing ? "Tutup Rencana" : "Batal / Tutup"}
            </button>
            {!viewing && (
              <>
                <button type="button" className="btn btn-secondary" disabled={!canSaveDraft}
                  onClick={saveDraft}>
                  {saving ? "Menyimpan…" : "Simpan Draft"}
                </button>
                <button type="button" className="btn btn-primary" disabled={!canSave}
                  onClick={submit}>
                  {saving ? "Menyimpan…" : "Simpan Konsolidasi"}
                </button>
              </>
            )}
          </div>
        </footer>
      </div>
    </dialog>
  );
}
