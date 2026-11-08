import { Fragment, useEffect, useRef, useState } from "react";
import ProductionRecapModal from "./ProductionRecapModal";
import ProductionConsolidation from "./ProductionConsolidation";
import { productionQtyLabel } from "./productionQty";
import FontSizeControl from "./FontSizeControl";
import { LoginPage } from "./App";
import {
  initializeSession, loadProductionDemand, loadProductionDeliveryQueue, logout,
  type ProductionDemand, type ProductionDeliveryQueue, type ProductionInboxFilter,
  type ProductionDeliveryGroup, type SessionInfo,
} from "./api";

function deliveryScopeKey(group: ProductionDeliveryGroup): string {
  return [group.delivery_date, group.kitchen_code, group.schedule_code].join("|");
}

function deliveryDateLabel(value: string): string {
  return new Date(value + "T00:00:00").toLocaleDateString("id-ID", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

function ProductionApp() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [fatal, setFatal] = useState("");
  const [filter, setFilter] = useState<ProductionInboxFilter>("ALL");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [inbox, setInbox] = useState<ProductionDeliveryQueue | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ProductionDeliveryGroup | null>(null);
  const [report, setReport] = useState<ProductionDemand | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const recapOpenerRef = useRef<HTMLButtonElement | null>(null);
  const [activeConsolidation, setActiveConsolidation] = useState<{
    order: ProductionDeliveryGroup; planId: number | null;
  } | null>(null);
  const consolidationOpenerRef = useRef<HTMLButtonElement | null>(null);
  const consolidationSavedRef = useRef(false);
  const pendingPlanFocusRef = useRef<{
    scopeKey: string; previousInbox: ProductionDeliveryQueue | null;
  } | null>(null);

  useEffect(() => {
    let active = true;
    initializeSession().then((info) => {
      if (!active) return;
      setSession(info);
      setInitializing(false);
    }).catch((err: unknown) => {
      if (!active) return;
      setFatal(err instanceof Error ? err.message : "Gagal memuat sesi.");
      setInitializing(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!session?.user.can_access_production) {
      setInbox(null);
      return;
    }
    const controller = new AbortController();
    setError("");
    setLoading(true);
    // Keep the existing rows mounted during refresh, including while the
    // planning modal is open. No scroll jumps or disappearing opener buttons.
    loadProductionDeliveryQueue(filter, page, controller.signal).then((value) => {
      if (!controller.signal.aborted) setInbox(value);
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "Tidak dapat memuat pesanan.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [session, filter, page, refresh]);

  useEffect(() => {
    if (!session?.user.can_access_production || !selected) {
      setReport(null);
      return;
    }
    const controller = new AbortController();
    setReportLoading(true);
    setReportError("");
    setReport(null);
    loadProductionDemand({
      delivery_date: selected.delivery_date,
      kitchen_code: selected.kitchen_code,
      schedule_code: selected.schedule_code,
    }, controller.signal).then((value) => {
      if (!controller.signal.aborted) setReport(value);
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) {
        setReportError(err instanceof Error ? err.message : "Rekap tidak dapat ditampilkan.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setReportLoading(false);
    });
    return () => controller.abort();
  }, [session, selected, refresh]);

  const openRecap = (order: ProductionDeliveryGroup, opener: HTMLButtonElement) => {
    recapOpenerRef.current = opener;
    setSelected(order);
  };

  const closeRecap = () => {
    setSelected(null);
    // Preserve the exact row and list position; don't navigate or change filters.
    const opener = recapOpenerRef.current;
    window.requestAnimationFrame(() => {
      if (opener?.isConnected) opener.focus();
    });
  };

  useEffect(() => {
    const pending = pendingPlanFocusRef.current;
    if (!pending || activeConsolidation || !inbox ||
        inbox === pending.previousInbox) return;
    pendingPlanFocusRef.current = null;
    window.requestAnimationFrame(() => {
      const row = Array.from(document.querySelectorAll<HTMLTableRowElement>(
        "tr[data-delivery-scope]"
      )).find((item) => item.dataset.deliveryScope === pending.scopeKey);
      // A successful save changes KIRIM to PROSES_PRODUKSI. The original
      // Rencanakan button may be replaced or disappear under the KIRIM tab.
      const target = row?.querySelector<HTMLButtonElement>(".production-plan-trigger")
        ?? document.querySelector<HTMLButtonElement>(
          ".production-inbox-tabs .production-tab.selected"
        );
      target?.focus();
    });
  }, [inbox, activeConsolidation]);

  const openConsolidation = (
    order: ProductionDeliveryGroup, planId: number | null,
    opener: HTMLButtonElement,
  ) => {
    consolidationOpenerRef.current = opener;
    consolidationSavedRef.current = false;
    setActiveConsolidation({ order, planId });
  };

  const closeConsolidation = () => {
    const opener = consolidationOpenerRef.current;
    const wasSaved = consolidationSavedRef.current;
    consolidationSavedRef.current = false;
    if (wasSaved) {
      // Both finalization and Simpan Draft refresh the action label on close.
      // Only refresh after closing. The underlying list never navigates away;
      // after refresh, focus the new Lihat Rencana button (or selected tab).
      pendingPlanFocusRef.current = {
        scopeKey: activeConsolidation ? deliveryScopeKey(activeConsolidation.order) : "",
        previousInbox: inbox,
      };
    }
    setActiveConsolidation(null);
    if (wasSaved) {
      setRefresh((value) => value + 1);
    } else {
      window.requestAnimationFrame(() => {
        if (opener?.isConnected) opener.focus();
      });
    }
  };

  const chooseFilter = (value: ProductionInboxFilter) => {
    if (value === filter) return;
    setFilter(value);
    setPage(1);
  };

  const signOut = async () => {
    setError("");
    try {
      await logout();
      setSession(null);
      setSelected(null);
      setActiveConsolidation(null);
      setInbox(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal keluar.");
    }
  };

  if (initializing) return <div className="boot-screen"><span className="spinner" /> Memuat Admin Produksi…</div>;
  if (fatal) return <div className="boot-screen"><div className="error-box">
    <h2>Gagal memuat workspace</h2><p>{fatal}</p>
    <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>Coba lagi</button>
  </div></div>;
  if (!session) return <LoginPage onSuccess={setSession} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-symbol">RO</span>
          <div className="topbar-title">
            <strong>RO Middleware</strong><span>Production & Distribution</span>
          </div>
        </div>
        <div className="topbar-right">
          {session.user.can_access_store && <a href="/toko/" className="ghost-btn production-nav-link">Admin Toko</a>}
          <span className="topbar-workspace">Workspace Admin Produksi</span>
          <span className="user-initial">{session.user.full_name.slice(0, 1).toUpperCase()}</span>
          <span className="user-name">{session.user.full_name}</span>
          <button type="button" className="ghost-btn logout" onClick={signOut}>Keluar</button>
          <FontSizeControl />
        </div>
      </header>
      <div className="shell-body">
        <aside className="sidebar">
          <div className="sidebar-eyebrow">WORKSPACE</div>
          <div className="side-link selected"><span className="side-icon">▤</span> Antrean Produksi</div>
          <div className="sidebar-divider" />
          <div className="sidebar-caption">Alur pesanan toko</div>
          <div className="sidebar-help">
            <strong>Status untuk produksi</strong>
            <p><b>Kirim</b>: siap dikonsolidasi.</p>
            <p><b>Proses Produksi</b>: sudah masuk konsolidasi.</p>
            <p>Draft pesanan toko dan No Order tidak masuk antrean. Draft Rencana Produksi tetap terlihat sebagai pesanan KIRIM.</p>
          </div>
          <div className="sidebar-bottom">RO Middleware · V1</div>
        </aside>
        <main className="workspace">
          <div className="breadcrumb">Workspace <span>/</span> Admin Produksi <span>/</span> Antrean Pesanan</div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">ADMIN PRODUKSI</div>
              <h1>Antrean Produksi per Tanggal Kirim</h1>
              <p>Satu kelompok per tanggal kirim, dapur, dan jadwal kirim; pesanan toko tetap bisa ditelusuri di dalamnya.</p>
            </div>
            <span className="production-readonly">Belum membuat MO Odoo</span>
          </div>
          {!session.user.can_access_production ? (
            <section className="card empty-config">
              <h2>Akses Admin Produksi diperlukan</h2>
              <p>Akun ini memerlukan Group PRODUCTION atau ADMIN. Akun STORE tidak dapat melihat antrean ini.</p>
              {session.user.can_access_store && <a href="/toko/">Kembali ke Admin Toko</a>}
            </section>
          ) : (
            <>
              {error && <div className="message error" role="alert">{error}</div>}
              <div className="production-inbox-tabs" role="group" aria-label="Filter status pesanan produksi">
                <button className={"production-tab " + (filter === "ALL" ? "selected" : "")} type="button" onClick={() => chooseFilter("ALL")}>Semua ({inbox?.counts.all ?? "…" })</button>
                <button className={"production-tab " + (filter === "KIRIM" ? "selected" : "")} type="button" onClick={() => chooseFilter("KIRIM")}>Kirim ({inbox?.counts.kirim ?? "…" })</button>
                <button className={"production-tab " + (filter === "PROSES_PRODUKSI" ? "selected" : "")} type="button" onClick={() => chooseFilter("PROSES_PRODUKSI")}>Proses Produksi ({inbox?.counts.proses_produksi ?? "…" })</button>
              </div>
              <section className="card order-card">
                <div className="order-title-bar">
                  <div>
                    <div className="section-heading"><span className="step-number">01</span> Kelompok Tanggal Kirim</div>
                    <p>Diurutkan berdasarkan tanggal kirim. Setiap dapur dan jadwal tetap kelompok terpisah; jumlah di tab menghitung kelompok.</p>
                  </div>
                  <button type="button" className="btn btn-secondary" onClick={() => setRefresh((v) => v + 1)} disabled={loading}>Muat Ulang</button>
                </div>
                {loading && !inbox && <div className="table-placeholder"><span className="spinner" /> Memuat antrean…</div>}
                {inbox && (
                  <>
                    <div className="table-scroll">
                      <table className="production-inbox-table">
                        <thead><tr><th>Tanggal Kirim</th><th>Dapur / Jadwal</th><th>Pesanan Toko</th><th>SKU / Qty Gabungan</th><th>Status</th><th>Aksi</th></tr></thead>
                        <tbody>
                          {inbox.items.map((group, index) => (
                            <Fragment key={deliveryScopeKey(group)}>
                              {(index === 0 || inbox.items[index - 1].delivery_date !== group.delivery_date) && (
                                <tr className="production-delivery-date-row">
                                  <th colSpan={6} scope="rowgroup">
                                    <span className="production-delivery-date-icon" aria-hidden="true">▦</span>
                                    Tanggal Kirim — {deliveryDateLabel(group.delivery_date)}
                                  </th>
                                </tr>
                              )}
                              <tr data-delivery-scope={deliveryScopeKey(group)}>
                                <td>
                                  <strong>{group.delivery_date}</strong>
                                  <small>{group.order_count} pesanan final</small>
                                </td>
                                <td>
                                  <strong>{group.kitchen_name}</strong>
                                  <small>{group.kitchen_code} · Jadwal Kirim {group.schedule_name}</small>
                                </td>
                                <td>
                                  <strong>{group.store_count} toko</strong>
                                  <details className="production-queue-stores">
                                    <summary>Lihat toko ({group.store_count})</summary>
                                    <ul>
                                      {group.stores.map((store) => (
                                        <li key={store.order_id}>
                                          <span>{store.store_name} · {store.store_code} · #{store.order_id}</span>
                                          <small>{store.status === "KIRIM" ? "Kirim" : "Proses Produksi"}</small>
                                        </li>
                                      ))}
                                    </ul>
                                  </details>
                                </td>
                                <td>
                                  <strong>{group.sku_count} SKU unik</strong>
                                  <small className={group.qty_invalid ? "production-qty-warning" : undefined}>
                                    {productionQtyLabel(group.qty_total, group.qty_uom, group.qty_by_uom, group.qty_invalid)}
                                  </small>
                                </td>
                                <td>
                                  <span className={"production-state " + group.status.toLowerCase()}>
                                    {group.status === "KIRIM" ? "Kirim" :
                                      group.status === "PROSES_PRODUKSI" ? "Proses Produksi" : "Pesanan Susulan"}
                                  </span>
                                  {group.status === "CAMPURAN" && (
                                    <small className="production-queue-warning">
                                      {group.kirim_count} Kirim · {group.proses_produksi_count} sudah diproses.
                                      Perlu penanganan pesanan susulan; jangan konsolidasi ulang.
                                    </small>
                                  )}
                                </td>
                                <td className="production-inbox-actions">
                                  <button type="button" className="production-open-rekap"
                                    onClick={(event) => openRecap(group, event.currentTarget)}>Lihat rekap</button>
                                  {group.status === "KIRIM" && group.plan_id == null && (
                                    <button type="button" className="production-open-rekap production-plan-trigger"
                                      onClick={(event) => openConsolidation(group, null, event.currentTarget)}>
                                      {group.has_consolidation_draft ? "Lanjutkan Draft" : "Rencanakan"}
                                    </button>
                                  )}
                                  {group.plan_id != null && (
                                    <button type="button" className="production-open-rekap production-plan-trigger"
                                      onClick={(event) => openConsolidation(group, group.plan_id, event.currentTarget)}>
                                      Lihat rencana
                                    </button>
                                  )}
                                </td>
                              </tr>
                            </Fragment>
                          ))}
                          {!inbox.items.length && <tr><td colSpan={6} className="production-inbox-empty">Belum ada kelompok pengiriman untuk status ini.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    <div className="production-inbox-footer">
                      <span className="result-count">{inbox.total} kelompok pengiriman · Halaman {page} · {inbox.page_size} kelompok per halaman</span>
                      <div className="action-buttons">
                        <button className="btn btn-secondary" type="button" disabled={page === 1} onClick={() => setPage((v) => Math.max(1, v - 1))}>Sebelumnya</button>
                        <button className="btn btn-secondary" type="button" disabled={!inbox.has_more} onClick={() => setPage((v) => v + 1)}>Berikutnya</button>
                      </div>
                    </div>
                  </>
                )}
              </section>
              {selected && (
                <ProductionRecapModal
                  order={selected}
                  report={report}
                  loading={reportLoading}
                  error={reportError}
                  onClose={closeRecap}
                />
              )}
              <p className="production-note">Satu baris adalah satu kelompok tanggal kirim × dapur × jadwal kirim; rincian toko berada di Lihat toko atau Lihat rekap. Simpan Draft tidak mengubah KIRIM; Simpan Konsolidasi memfinalisasi kebutuhan kelompok tersebut. Belum membuat MO Odoo.</p>
            </>
          )}
          {activeConsolidation && (
            <ProductionConsolidation
              order={activeConsolidation.order}
              planId={activeConsolidation.planId}
              schedules={session.schedules}
              onBack={closeConsolidation}
              onSaved={() => { consolidationSavedRef.current = true; }}
              onDraftSaved={() => { consolidationSavedRef.current = true; }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
export default ProductionApp;
