import { useEffect, useRef, useState } from "react";
import ProductionRecapModal from "./ProductionRecapModal";
import { productionQtyLabel } from "./productionQty";
import { LoginPage } from "./App";
import {
  initializeSession, loadProductionDemand, loadProductionInbox, logout,
  type ProductionDemand, type ProductionInbox, type ProductionInboxFilter,
  type ProductionInboxOrder, type SessionInfo,
} from "./api";

function ProductionApp() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [fatal, setFatal] = useState("");
  const [filter, setFilter] = useState<ProductionInboxFilter>("ALL");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [inbox, setInbox] = useState<ProductionInbox | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ProductionInboxOrder | null>(null);
  const [report, setReport] = useState<ProductionDemand | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const recapOpenerRef = useRef<HTMLButtonElement | null>(null);

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
    setInbox(null);
    loadProductionInbox(filter, page, controller.signal).then((value) => {
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

  const openRecap = (order: ProductionInboxOrder, opener: HTMLButtonElement) => {
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
            <p>Draft dan No Order tidak masuk antrean produksi.</p>
          </div>
          <div className="sidebar-bottom">RO Middleware · V1</div>
        </aside>
        <main className="workspace">
          <div className="breadcrumb">Workspace <span>/</span> Admin Produksi <span>/</span> Antrean Pesanan</div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">ADMIN PRODUKSI</div>
              <h1>Antrean Pesanan Produksi</h1>
              <p>Semua pesanan Kirim dan Proses Produksi dari seluruh toko, tanggal, dapur, dan jadwal.</p>
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
                    <div className="section-heading"><span className="step-number">01</span> Daftar Pesanan</div>
                    <p>Prioritas pesanan Kirim lebih dahulu. Semua tanggal tercakup.</p>
                  </div>
                  <button type="button" className="btn btn-secondary" onClick={() => setRefresh((v) => v + 1)} disabled={loading}>Muat Ulang</button>
                </div>
                {loading && <div className="table-placeholder"><span className="spinner" /> Memuat antrean…</div>}
                {!loading && inbox && (
                  <>
                    <div className="table-scroll">
                      <table className="production-inbox-table">
                        <thead><tr><th>ID / Toko</th><th>Tanggal Kirim</th><th>Dapur</th><th>Jadwal</th><th>SKU / Total Qty</th><th>Status</th><th>Aksi</th></tr></thead>
                        <tbody>
                          {inbox.items.map((order) => (
                            <tr key={order.order_id}>
                              <td><strong>{order.store_name}</strong><small>Order #{order.order_id} · {order.store_code}</small></td>
                              <td>{order.delivery_date}</td>
                              <td>{order.kitchen_name}</td>
                              <td>{order.schedule_name}</td>
                              <td><strong>{order.sku_count} SKU</strong><small className={order.qty_invalid ? "production-qty-warning" : undefined}>{productionQtyLabel(order.qty_total, order.qty_uom, order.qty_by_uom, order.qty_invalid)}</small></td>
                              <td><span className={"production-state " + order.status.toLowerCase()}>{order.status === "KIRIM" ? "Kirim" : "Proses Produksi"}</span></td>
                              <td><button type="button" className="production-open-rekap" onClick={(event) => openRecap(order, event.currentTarget)}>Lihat rekap</button></td>
                            </tr>
                          ))}
                          {!inbox.items.length && <tr><td colSpan={7} className="production-inbox-empty">Belum ada pesanan untuk status ini.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    <div className="production-inbox-footer">
                      <span className="result-count">{inbox.total} pesanan · Halaman {page} · {inbox.page_size} per halaman</span>
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
              <p className="production-note">Status Proses Produksi hanya akan diberikan ketika langkah konsolidasi rencana benar-benar disimpan. Membuka rincian tidak mengubah status atau membuat MO.</p>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
export default ProductionApp;
