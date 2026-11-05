import { memo, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  initializeSession, loadOrder, login, logout, saveDraft, sendOrder,
  type OrderContext, type OrderItem, type SessionInfo, type StoreOrder,
} from "./api";
import { deliveryDateInWib, hasPositiveQty, normalizeQty } from "./utils";

type Busy = "save" | "send" | null;

function StatusBadge({ status, automatic }: { status: "DRAFT" | "KIRIM" | "NO_ORDER"; automatic: boolean }) {
  return (
    <span className={"status-chip " + status.toLowerCase()}>
      <span className="status-dot" />
      {status === "DRAFT" ? "Draft · Bisa diedit" : status === "KIRIM" ? (automatic ? "Terkirim otomatis" : "Sudah dikirim") : (automatic ? "No Order otomatis" : "No Order")}
    </span>
  );
}

type QuantityRowProps = {
  item: OrderItem;
  value: string;
  editable: boolean;
  index: number;
  onChange: (id: number, value: string) => void;
  onEnter: (id: number) => void;
};

const QuantityRow = memo(function QuantityRow({
  item, value, editable, index, onChange, onEnter,
}: QuantityRowProps) {
  const belowOne = Number(value.replace(",", ".")) > 0 && !hasPositiveQty(value);
  return (
    <tr className={!item.active_in_template ? "inactive-row" : ""}>
      <td className="number-col">{index + 1}</td>
      <td><span className="sku">{item.sku || "—"}</span></td>
      <td>
        <div className="product-name">{item.name}</div>
        {!item.active_in_template && <span className="small-note">Sudah tidak aktif di template</span>}
      </td>
      <td className="qty-col">
        {editable ? (
          <div className="qty-wrapper">
            <input
              id={"qty-" + item.product_id}
              aria-label={"Qty " + item.name}
              className={"qty-input " + (belowOne ? "qty-below" : "")}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="off"
              spellCheck={false}
              value={value}
              onChange={(event) => {
                const next = event.target.value;
                if (next === "" || /^\d{0,14}$/.test(next)) {
                  onChange(item.product_id, next);
                }
              }}
              onFocus={(event) => event.currentTarget.select()}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onEnter(item.product_id);
                }
              }}
            />
          </div>
        ) : (
          <strong className="qty-final">{value || "0"}</strong>
        )}
      </td>
    </tr>
  );
});

function LoginPage({ onSuccess }: { onSuccess: (value: SessionInfo) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await login(username, password);
      onSuccess(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login gagal.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="brand-line">
          <span className="brand-symbol">RO</span>
          <span className="brand-name">Production Middleware</span>
        </div>
        <div className="login-divider" />
        <div className="eyebrow">WORKSPACE ADMIN TOKO</div>
        <h1>Selamat datang</h1>
        <p className="text-muted">Masuk menggunakan akun middleware untuk mengisi permintaan produk toko.</p>
        {error && <div className="message error" role="alert">{error}</div>}
        <form onSubmit={submit} className="login-form">
          <label htmlFor="username">Username</label>
          <input
            id="username" autoComplete="username" required
            value={username} onChange={(event) => setUsername(event.target.value)}
            placeholder="Username"
          />
          <label htmlFor="password">Password</label>
          <input
            id="password" type="password" autoComplete="current-password" required
            value={password} onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
          />
          <button className="btn btn-primary full" type="submit" disabled={busy}>
            {busy ? "Memeriksa akun…" : "Masuk ke Workspace"}
          </button>
        </form>
        <p className="login-footer">RO Middleware V1 · Admin Toko</p>
      </div>
    </main>
  );
}

function App() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [fatal, setFatal] = useState("");
  const [storeCode, setStoreCode] = useState("");
  const [kitchenCode, setKitchenCode] = useState("");
  const [scheduleCode, setScheduleCode] = useState("");
  const [deliveryDate, setDeliveryDate] = useState(deliveryDateInWib());
  const [order, setOrder] = useState<StoreOrder | null>(null);
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [search, setSearch] = useState("");
  const [onlyFilled, setOnlyFilled] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [loadingOrder, setLoadingOrder] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const visibleIds = useRef<number[]>([]);

  const loadSessionIntoForm = (info: SessionInfo) => {
    setSession(info);
    setStoreCode(info.stores[0]?.code ?? "");
    const firstWithItems = info.kitchens.find((kitchen) => kitchen.item_count > 0);
    setKitchenCode(firstWithItems?.code ?? info.kitchens[0]?.code ?? "");
    setScheduleCode(info.schedules[0]?.code ?? "");
  };

  useEffect(() => {
    let mounted = true;
    initializeSession().then((info) => {
      if (!mounted) return;
      if (info) loadSessionIntoForm(info);
      setInitializing(false);
    }).catch((err: unknown) => {
      if (!mounted) return;
      setFatal(err instanceof Error ? err.message : "Tidak dapat menghubungi server.");
      setInitializing(false);
    });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!session || !storeCode || !kitchenCode || !scheduleCode || !deliveryDate) {
      setOrder(null);
      return;
    }
    const controller = new AbortController();
    setLoadingOrder(true);
    setError("");
    setNotice("");
    setOrder(null);
    setQuantities({});
    loadOrder({ store_code: storeCode, kitchen_code: kitchenCode, delivery_date: deliveryDate, schedule_code: scheduleCode }, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setOrder(result);
        setQuantities(Object.fromEntries(result.items.map((item) => [item.product_id, item.qty])));
        setDirty(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Gagal memuat template pemesanan.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingOrder(false);
      });
    return () => controller.abort();
  }, [session, storeCode, kitchenCode, scheduleCode, deliveryDate]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const editable = order?.editable ?? false;
  const items = useMemo(() => {
    if (!order) return [];
    // Sent orders show exactly the lines that were sent, rather than 700 zero rows.
    if (!order.editable) return order.items.filter((item) => Number(item.qty) >= 1);
    return order.items;
  }, [order]);
  const visibleItems = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("id-ID");
    return items.filter((item) => {
      const qty = quantities[item.product_id] ?? "0";
      if (onlyFilled && !hasPositiveQty(qty)) return false;
      if (term && !(item.sku.toLocaleLowerCase("id-ID").includes(term) ||
        item.name.toLocaleLowerCase("id-ID").includes(term))) return false;
      return true;
    });
  }, [items, search, onlyFilled, quantities]);
  visibleIds.current = visibleItems.map((item) => item.product_id);

  const productCount = items.filter((item) => hasPositiveQty(quantities[item.product_id] ?? "0")).length;
  const totalQty = items.reduce((sum, item) => {
    const value = normalizeQty(quantities[item.product_id] ?? "0");
    return sum + (value === null ? 0 : Number(value));
  }, 0);
  const hasInvalid = items.some((item) => normalizeQty(quantities[item.product_id] ?? "0") === null);

  const changeContext = (
    setter: (value: string) => void, value: string, current: string,
  ) => {
    if (value === current) return;
    if (dirty && !window.confirm("Ada Qty yang belum disimpan. Pindah tanpa menyimpan perubahan?")) return;
    setter(value);
    setSearch("");
    setOnlyFilled(false);
    setDirty(false);
    setNotice("");
  };

  const changeQty = useCallback((id: number, value: string) => {
    setQuantities((current) => ({ ...current, [id]: value }));
    setDirty(true);
    setNotice("");
  }, []);

  const nextQty = useCallback((id: number) => {
    const index = visibleIds.current.indexOf(id);
    if (index < 0 || index >= visibleIds.current.length - 1) return;
    const next = visibleIds.current[index + 1];
    document.getElementById("qty-" + next)?.focus();
  }, []);

  const context: OrderContext = {
    store_code: storeCode,
    kitchen_code: kitchenCode,
    delivery_date: deliveryDate,
    schedule_code: scheduleCode,
  };

  const save = async () => {
    if (!order || !order.editable || busy) return;
    if (hasInvalid) {
      setError("Qty harus bilangan bulat 0, 1, 2, ... tanpa desimal (maksimal 14 digit).");
      return;
    }
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const saved = await saveDraft(context, quantities);
      setOrder(saved);
      setQuantities(Object.fromEntries(saved.items.map((item) => [item.product_id, item.qty])));
      setDirty(false);
      setNotice("Draft tersimpan. Pesanan ini masih dapat dibuka dan Qty masih bisa diedit.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan Draft.");
    } finally {
      setBusy(null);
    }
  };

  const send = async () => {
    if (!order || !order.editable || busy) return;
    if (hasInvalid) {
      setError("Periksa Qty: hanya bilangan bulat tanpa desimal yang dapat dikirim.");
      return;
    }
    const question = productCount === 0
      ? "Semua Qty kosong atau kurang dari 1. Kirim sebagai NO ORDER dan kunci pesanan?"
      : "Kirim " + productCount + " SKU dengan Qty ≥ 1? Setelah Kirim, pesanan tidak bisa diedit.";
    if (!window.confirm(question)) return;
    setBusy("send");
    setError("");
    setNotice("");
    try {
      const ready = dirty || order.id === null
        ? await saveDraft(context, quantities)
        : order;
      if (ready.id === null) throw new Error("Draft belum mempunyai nomor pesanan.");
      const result = await sendOrder(ready.id);
      const refreshed = await loadOrder(context);
      setOrder(refreshed);
      setQuantities(Object.fromEntries(refreshed.items.map((item) => [item.product_id, item.qty])));
      setDirty(false);
      setNotice(result.status === "NO_ORDER"
        ? "Pesanan selesai dengan status No Order (tidak ada Qty ≥ 1)."
        : "Pesanan berhasil dikirim: " + result.items_sent + " SKU. Qty sekarang terkunci.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Proses Kirim gagal. Periksa status pesanan.");
      // Do not auto-retry uncertain writes.
    } finally {
      setBusy(null);
    }
  };

  const signOut = async () => {
    if (dirty && !window.confirm("Perubahan Draft belum disimpan. Tetap keluar?")) return;
    setError("");
    try {
      await logout();
      setSession(null);
      setOrder(null);
      setDirty(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal keluar.");
    }
  };

  if (initializing) return <div className="boot-screen"><span className="spinner" /> Memuat RO Middleware…</div>;
  if (fatal) return (
    <div className="boot-screen">
      <div className="error-box">
        <h2>Tidak dapat membuka aplikasi</h2>
        <p>{fatal}</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Coba lagi</button>
      </div>
    </div>
  );
  if (!session) return <LoginPage onSuccess={loadSessionIntoForm} />;

  const chosenKitchen = session.kitchens.find((kitchen) => kitchen.code === kitchenCode);
  const chosenStore = session.stores.find((store) => store.code === storeCode);
  const isConfigured = !!(session.stores.length && session.kitchens.length && session.schedules.length);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-symbol">RO</div>
          <div className="topbar-title"><strong>RO Middleware</strong><span>Production & Distribution</span></div>
        </div>
        <div className="topbar-right">
          <span className="topbar-workspace">Workspace Admin Toko</span>
          <span className="user-initial">{session.user.full_name.slice(0, 1).toUpperCase()}</span>
          <span className="user-name">{session.user.full_name}</span>
          <button className="ghost-btn logout" onClick={signOut} title="Keluar dari aplikasi">Keluar</button>
        </div>
      </header>
      <div className="shell-body">
        <aside className="sidebar">
          <div className="sidebar-eyebrow">WORKSPACE</div>
          <div className="side-link selected"><span className="side-icon">▤</span> Pemesanan Toko</div>
          <div className="sidebar-divider" />
          <div className="sidebar-caption">Cepat dan terstruktur</div>
          <div className="sidebar-help">
            <strong>Petunjuk pengisian</strong>
            <p>Pilih dapur, tanggal, jadwal, lalu isi Qty. Tekan Enter untuk pindah ke baris berikutnya.</p>
            <p>Draft bisa diedit lagi. Kirim hanya memproses Qty ≥ 1.</p>
          </div>
          <div className="sidebar-bottom">RO Middleware · V1</div>
        </aside>
        <main className="workspace">
          <div className="breadcrumb">Workspace <span>/</span> Admin Toko <span>/</span> Pemesanan</div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">PEMESANAN PRODUK</div>
              <h1>Input Pesanan Toko</h1>
              <p>Daftar SKU otomatis mengikuti template dapur. Anda hanya perlu mengisi Qty.</p>
            </div>
            {order && <StatusBadge status={order.status} automatic={order.auto_submitted} />}
          </div>

          {error && <div className="message error" role="alert"><strong>Perhatian:</strong> {error}</div>}
          {notice && <div className="message success" role="status">{notice}</div>}

          {!isConfigured ? (
            <section className="card empty-config">
              <h2>Data pengaturan belum lengkap</h2>
              <p>Periksa akses toko, template dapur, dan jadwal pengiriman. Administrator dapat menyiapkan jadwal standar melalui perintah <code>python manage.py seed_order_schedules</code>.</p>
            </section>
          ) : (
            <>
              <section className="card selector-card">
                <div className="section-heading"><span className="step-number">01</span> Detail Pemesanan</div>
                <div className="selector-grid">
                  <label>Nama Toko
                    <select value={storeCode} disabled={!!busy} onChange={(e) => changeContext(setStoreCode, e.target.value, storeCode)}>
                      {session.stores.map((store) => <option key={store.code} value={store.code}>{store.name}</option>)}
                    </select>
                  </label>
                  <label>Dapur / Template
                    <select value={kitchenCode} disabled={!!busy} onChange={(e) => changeContext(setKitchenCode, e.target.value, kitchenCode)}>
                      {session.kitchens.map((kitchen) => <option key={kitchen.code} value={kitchen.code}>{kitchen.name} ({kitchen.item_count} SKU)</option>)}
                    </select>
                  </label>
                  <label>Tanggal Pengiriman
                    <input type="date" value={deliveryDate} disabled={!!busy} onChange={(e) => changeContext(setDeliveryDate, e.target.value, deliveryDate)} />
                  </label>
                  <label>Jadwal Kirim
                    <select value={scheduleCode} disabled={!!busy} onChange={(e) => changeContext(setScheduleCode, e.target.value, scheduleCode)}>
                      {session.schedules.map((schedule) => <option key={schedule.code} value={schedule.code}>{schedule.name}</option>)}
                    </select>
                  </label>
                </div>
              </section>

              <section className="summary-grid">
                <div className="summary-box"><span>SKU dalam template</span><strong>{items.length.toLocaleString("id-ID")}</strong><small>{chosenKitchen?.name ?? "Dapur"}</small></div>
                <div className="summary-box"><span>SKU dengan Qty ≥ 1</span><strong>{productCount.toLocaleString("id-ID")}</strong><small>Siap ikut Kirim</small></div>
                <div className="summary-box"><span>Total Qty diisi</span><strong>{totalQty.toLocaleString("id-ID", { maximumFractionDigits: 0 })}</strong><small>Perhitungan sementara</small></div>
              </section>

              <section className="card order-card">
                <div className="order-title-bar">
                  <div>
                    <div className="section-heading"><span className="step-number">02</span> Daftar SKU & Qty</div>
                    <p>Template {chosenKitchen?.name ?? ""} · {chosenStore?.name ?? ""}</p>
                  </div>
                  <div className="draft-indicator">
                    {dirty ? <span className="unsaved-dot" /> : <span className="saved-dot" />}
                    {dirty ? "Ada perubahan belum disimpan" : "Tidak ada perubahan"}
                  </div>
                </div>
                <div className="filters-row">
                  <label className="search-box">
                    <span aria-hidden="true">⌕</span>
                    <input type="search" placeholder="Cari SKU atau nama produk…" value={search} onChange={(e) => setSearch(e.target.value)} />
                  </label>
                  <label className="filter-switch">
                    <input type="checkbox" checked={onlyFilled} onChange={(e) => setOnlyFilled(e.target.checked)} />
                    Hanya Qty ≥ 1
                  </label>
                  <span className="result-count">{visibleItems.length.toLocaleString("id-ID")} ditampilkan</span>
                </div>
                {loadingOrder ? (
                  <div className="table-placeholder"><span className="spinner" /> Memuat template pesanan…</div>
                ) : !order ? (
                  <div className="table-placeholder">Formulir tidak tersedia. Periksa pilihan dan coba lagi.</div>
                ) : (
                  <div className="table-scroll">
                    <table className="qty-table">
                      <thead><tr>
                        <th className="number-col">No</th><th>SKU / ID</th><th>Nama Produk</th><th className="qty-col">Qty</th>
                      </tr></thead>
                      <tbody>
                        {visibleItems.map((item, index) => (
                          <QuantityRow
                            key={item.product_id} item={item} index={index}
                            value={quantities[item.product_id] ?? "0"} editable={editable && !busy}
                            onChange={changeQty} onEnter={nextQty}
                          />
                        ))}
                        {!visibleItems.length && (
                          <tr><td colSpan={4} className="empty-table">
                            {order.status === "NO_ORDER"
                              ? "Pesanan ini ditutup dengan status No Order."
                              : "Tidak ada SKU yang cocok dengan filter ini."}
                          </td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="table-hint">
                  <span>{order && order.editable ? "Tips: tekan Enter untuk pindah ke Qty berikutnya." : "Pesanan final bersifat hanya baca."}</span>
                  <span>Qty 0 tidak dikirim · Qty ≥ 1 diproses</span>
                </div>
              </section>

              <footer className="action-bar">
                <div className="action-info">
                  <strong>{order?.status === "KIRIM" ? "Pesanan telah dikirim" : order?.status === "NO_ORDER" ? "Tidak ada pesanan" : "Pesanan belum dikirim"}</strong>
                  <span>{order?.status === "DRAFT" ? "Simpan Draft untuk melanjutkan pengisian nanti." : "Pesanan sudah terkunci."}</span>
                </div>
                <div className="action-buttons">
                  <button className="btn btn-secondary" disabled={!order || !editable || !!busy || loadingOrder} onClick={save}>
                    {busy === "save" ? "Menyimpan…" : "Simpan Draft"}
                  </button>
                  <button className="btn btn-primary" disabled={!order || !editable || !!busy || loadingOrder} onClick={send}>
                    {busy === "send" ? "Mengirim…" : "Kirim Pesanan"}
                  </button>
                </div>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
