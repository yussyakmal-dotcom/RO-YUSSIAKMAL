import { useEffect, useMemo, useState } from "react";
import { LoginPage } from "./App";
import {
  initializeSession, loadProductionDemand, loadRecentSentOrders, logout,
  type ProductionDemand, type ProductionStoreStatus, type RecentSentOrder, type SessionInfo,
} from "./api";
import { deliveryDateInWib } from "./utils";

function readableInteger(value: string): string {
  try {
    return new Intl.NumberFormat("id-ID").format(BigInt(value));
  } catch {
    return value;
  }
}

function storeStatusLabel(status: ProductionStoreStatus): string {
  if (status === "KIRIM") return "Kirim";
  if (status === "NO_ORDER") return "No Order";
  if (status === "DRAFT") return "Draft belum dikirim";
  return "Belum membuat pesanan";
}

function ProductionApp() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [fatal, setFatal] = useState("");
  const [deliveryDate, setDeliveryDate] = useState(deliveryDateInWib(2));
  const [kitchenCode, setKitchenCode] = useState("");
  const [scheduleCode, setScheduleCode] = useState("");
  const [report, setReport] = useState<ProductionDemand | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [recentOrders, setRecentOrders] = useState<RecentSentOrder[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState("");
  const [showRecent, setShowRecent] = useState(false);

  const setCurrentSession = (info: SessionInfo) => {
    setSession(info);
    const firstWithItems = info.kitchens.find((k) => k.item_count > 0);
    setKitchenCode(firstWithItems?.code ?? info.kitchens[0]?.code ?? "");
    setScheduleCode(info.schedules[0]?.code ?? "");
  };

  useEffect(() => {
    let alive = true;
    initializeSession().then((info) => {
      if (!alive) return;
      if (info) setCurrentSession(info);
      setInitializing(false);
    }).catch((err: unknown) => {
      if (!alive) return;
      setFatal(err instanceof Error ? err.message : "Tidak bisa menghubungi server.");
      setInitializing(false);
    });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!session?.user.can_access_production || !kitchenCode || !scheduleCode || !deliveryDate) {
      setReport(null);
      return;
    }
    const controller = new AbortController();
    setError("");
    setReport(null);
    setExpanded(null);
    setLoading(true);
    loadProductionDemand(
      { delivery_date: deliveryDate, kitchen_code: kitchenCode, schedule_code: scheduleCode },
      controller.signal,
    ).then((data) => {
      if (!controller.signal.aborted) setReport(data);
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "Gagal memuat rekap.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [session, kitchenCode, scheduleCode, deliveryDate, refreshKey]);

  useEffect(() => {
    if (!session?.user.can_access_production) return;
    const controller = new AbortController();
    setRecentLoading(true);
    setRecentError("");
    loadRecentSentOrders(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setRecentOrders(data.items);
      }).catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setRecentError(err instanceof Error ? err.message : "Daftar pesanan tidak tersedia.");
        }
      }).finally(() => {
        if (!controller.signal.aborted) setRecentLoading(false);
      });
    return () => controller.abort();
  }, [session, refreshKey]);

  const openRecentScope = (order: RecentSentOrder) => {
    setDeliveryDate(order.delivery_date);
    setKitchenCode(order.kitchen_code);
    setScheduleCode(order.schedule_code);
    setSearch("");
    setShowRecent(false);
  };

  const visibleRows = useMemo(() => {
    if (!report) return [];
    const key = search.trim().toLocaleLowerCase("id-ID");
    return report.items.filter((row) =>
      !key || row.sku.toLocaleLowerCase("id-ID").includes(key) ||
      row.name.toLocaleLowerCase("id-ID").includes(key),
    );
  }, [report, search]);

  const signOut = async () => {
    setError("");
    try {
      await logout();
      setSession(null);
      setReport(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal keluar.");
    }
  };

  if (initializing) return <div className="boot-screen"><span className="spinner" /> Memuat Admin Produksi…</div>;
  if (fatal) return (
    <div className="boot-screen">
      <div className="error-box">
        <h2>Gagal membuka workspace</h2>
        <p>{fatal}</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Coba lagi</button>
      </div>
    </div>
  );
  if (!session) return <LoginPage onSuccess={setCurrentSession} />;

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
          <button type="button" onClick={signOut} className="ghost-btn logout">Keluar</button>
        </div>
      </header>
      <div className="shell-body">
        <aside className="sidebar">
          <div className="sidebar-eyebrow">WORKSPACE</div>
          <div className="side-link selected"><span className="side-icon">▤</span> Rekap Kebutuhan</div>
          <div className="sidebar-divider" />
          <div className="sidebar-caption">Rekap permintaan final</div>
          <div className="sidebar-help">
            <strong>Dasar perhitungan</strong>
            <p>Hanya pesanan berstatus Kirim. Draft, No Order dan toko yang belum mengirim tidak ikut total.</p>
            <p>Rekap menurut tanggal dan jadwal kirim. Tanggal produksi belum ditetapkan.</p>
          </div>
          <div className="sidebar-bottom">RO Middleware · V1</div>
        </aside>
        <main className="workspace">
          <div className="breadcrumb">Workspace <span>/</span> Admin Produksi <span>/</span> Rekap Kebutuhan</div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">ADMIN PRODUKSI</div>
              <h1>Rekap Kebutuhan Toko</h1>
              <p>Total permintaan final per SKU, dengan rincian asal toko.</p>
            </div>
            <span className="production-readonly">Baca saja · Tidak membuat MO</span>
          </div>

          {!session.user.can_access_production ? (
            <section className="card empty-config">
              <h2>Akses Admin Produksi diperlukan</h2>
              <p>Akun ini belum menjadi anggota Group PRODUCTION atau ADMIN. Minta Administrator mengatur hak akses di Django Admin.</p>
              {session.user.can_access_store && <p><a href="/toko/">Kembali ke Workspace Admin Toko</a></p>}
            </section>
          ) : (
            <>
              <section className="card selector-card">
                <div className="section-heading"><span className="step-number">01</span> Pilih Lingkup Rekap</div>
                <div className="production-selector-grid">
                  <label>Tanggal Pengiriman
                    <input type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
                  </label>
                  <label>Dapur Produksi
                    <select value={kitchenCode} onChange={(e) => setKitchenCode(e.target.value)}>
                      {session.kitchens.map((k) => <option key={k.code} value={k.code}>{k.name}</option>)}
                    </select>
                  </label>
                  <label>Jadwal Kirim
                    <select value={scheduleCode} onChange={(e) => setScheduleCode(e.target.value)}>
                      {session.schedules.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                    </select>
                  </label>
                  <button type="button" className="btn btn-secondary production-refresh" onClick={() => setRefreshKey((v) => v + 1)} disabled={loading}>
                    {loading ? "Memuat…" : "Muat Ulang"}
                  </button>
                </div>
              </section>

              <section className="card production-recent-card">
                <div className="production-recent-heading">
                  <div>
                    <div className="section-heading">Temukan Pesanan yang Sudah Kirim</div>
                    <p>Lintas tanggal, dapur dan jadwal. Klik “Lihat rekap” untuk menyamakan filter dengan pesanan.</p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowRecent((value) => !value)}
                  >{showRecent ? "Tutup daftar" : "Lihat Kirim terbaru"}</button>
                </div>
                {(showRecent || (report && report.summary.stores_sent === 0)) && (
                  <div className="production-recent-body">
                    {recentLoading && <p>Memuat pesanan Kirim terbaru…</p>}
                    {recentError && <div className="message error" role="alert">{recentError}</div>}
                    {!recentLoading && !recentError && !recentOrders.length &&
                      <p>Belum ada pesanan berstatus KIRIM di database middleware.</p>}
                    {!recentLoading && !recentError && !!recentOrders.length && (
                      <div className="production-recent-scroll">
                        <table className="production-recent-table">
                          <thead><tr><th>Toko</th><th>Tanggal Kirim</th><th>Dapur</th><th>Jadwal</th><th>SKU</th><th>Aksi</th></tr></thead>
                          <tbody>{recentOrders.map((order) => (
                            <tr key={order.order_id}>
                              <td><strong>{order.store_name}</strong><small>#{order.order_id} · {order.store_code}</small></td>
                              <td>{order.delivery_date}</td>
                              <td>{order.kitchen_name}</td>
                              <td>{order.schedule_name}</td>
                              <td>{order.sku_count}</td>
                              <td><button type="button" className="production-open-rekap" onClick={() => openRecentScope(order)}>Lihat rekap</button></td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    )}
                    <p className="production-recent-footnote">Maksimal 30 pesanan KIRIM terbaru. Tidak ada perubahan data saat membuka rekap.</p>
                  </div>
                )}
              </section>

              {error && <div className="message error" role="alert"><strong>Rekap belum dapat ditampilkan:</strong> {error}</div>}
              {loading && <div className="card table-placeholder"><span className="spinner" /> Menghitung rekap pesanan final…</div>}

              {report && !loading && (
                <>
                  <div className="summary-grid production-summary-grid">
                    <div className="summary-box"><span>Toko sudah Kirim</span><strong>{report.summary.stores_sent}</strong><small>Dari {report.summary.stores_total} toko</small></div>
                    <div className="summary-box"><span>SKU diminta</span><strong>{report.summary.sku_count}</strong><small>SKU unik pada rekap final</small></div>
                    <div className="summary-box"><span>Total Qty</span><strong>{readableInteger(report.summary.qty_total)}</strong><small>Unit seluruh SKU</small></div>
                  </div>

                  <section className="card production-status-card">
                    <div className="section-heading"><span className="step-number">02</span> Status Pesanan Tiap Toko</div>
                    <div className="production-status-counts">
                      <span>{report.summary.stores_sent} Kirim</span>
                      <span>{report.summary.stores_no_order} No Order</span>
                      <span>{report.summary.stores_draft} Draft</span>
                      <span>{report.summary.stores_not_entered} Belum dibuat</span>
                    </div>
                    <div className="production-stores">
                      {report.store_statuses.map((row) => (
                        <div key={row.store_code} className="production-store">
                          <div><strong>{row.store_name}</strong><small>{row.store_code}</small></div>
                          <span className={"production-store-status " + row.status.toLowerCase()}>
                            {storeStatusLabel(row.status)}
                            {row.status === "KIRIM" && row.auto_submitted ? " · Otomatis" : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="card order-card">
                    <div className="order-title-bar">
                      <div>
                        <div className="section-heading"><span className="step-number">03</span> Total Kebutuhan SKU</div>
                        <p>Hanya KIRIM · {report.kitchen.name} · {report.schedule.name} · {report.delivery_date}</p>
                      </div>
                    </div>
                    <div className="filters-row">
                      <label className="search-box">
                        <span aria-hidden="true">⌕</span>
                        <input type="search" placeholder="Cari SKU atau nama produk…" value={search} onChange={(e) => setSearch(e.target.value)} />
                      </label>
                      <span className="result-count">{visibleRows.length} SKU ditampilkan</span>
                    </div>
                    <div className="table-scroll production-table-scroll">
                      <table className="qty-table production-table">
                        <thead><tr>
                          <th>SKU</th><th>Nama Produk</th><th className="production-store-count">Toko pemesan</th><th className="qty-col">Total Qty</th>
                        </tr></thead>
                        <tbody>
                          {visibleRows.map((item) => (
                            <FragmentRow key={item.product_id} item={item} expanded={expanded === item.product_id} toggle={() => setExpanded(expanded === item.product_id ? null : item.product_id)} />
                          ))}
                          {!visibleRows.length && <tr><td colSpan={4} className="empty-table">Belum ada SKU final untuk filter ini.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    <div className="table-hint">
                      <span>Klik baris SKU untuk melihat rincian Qty tiap toko.</span>
                      <span>Draft/No Order tidak dihitung</span>
                    </div>
                  </section>
                  <div className="production-note">{report.note} Fitur revisi rencana, kapasitas dan pembuatan MO merupakan tahap berikutnya.</div>
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function FragmentRow({
  item, expanded, toggle,
}: {
  item: ProductionDemand["items"][number];
  expanded: boolean;
  toggle: () => void;
}) {
  return (
    <>
      <tr className={"production-data-row " + (expanded ? "production-expanded" : "")} onClick={toggle}>
        <td><button type="button" className="production-expand" aria-expanded={expanded} aria-label={"Rincian " + item.name}>{expanded ? "▾" : "▸"}</button><span className="sku">{item.sku || "—"}</span></td>
        <td><span className="product-name">{item.name}</span></td>
        <td className="production-store-count">{item.store_count}</td>
        <td className="qty-col"><strong className="qty-final">{readableInteger(item.qty_total)}</strong></td>
      </tr>
      {expanded && (
        <tr className="production-detail-row">
          <td colSpan={4}>
            <div className="production-detail">
              <div className="production-detail-heading">Rincian permintaan dari toko</div>
              {item.sources.map((source) => (
                <div className="production-detail-store" key={source.order_id}>
                  <div><strong>{source.store_name}</strong><span>{source.store_code} · Order #{source.order_id}{source.auto_submitted ? " · otomatis" : ""}</span></div>
                  <strong>{readableInteger(source.qty)}</strong>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default ProductionApp;
