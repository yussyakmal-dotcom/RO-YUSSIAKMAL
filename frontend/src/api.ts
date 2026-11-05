export type NamedOption = { code: string; name: string };
export type KitchenOption = NamedOption & { item_count: number };

export interface SessionInfo {
  user: { username: string; full_name: string; admin: boolean; can_access_production: boolean; can_access_store: boolean };
  stores: NamedOption[];
  kitchens: KitchenOption[];
  schedules: NamedOption[];
}

export type OrderStatus = "DRAFT" | "KIRIM" | "PROSES_PRODUKSI" | "NO_ORDER";
export interface OrderItem {
  product_id: number;
  sku: string;
  name: string;
  qty: string;
  active_in_template: boolean;
}
export interface StoreOrder {
  id: number | null;
  status: OrderStatus;
  auto_submitted: boolean;
  editable: boolean;
  store: NamedOption;
  kitchen: NamedOption;
  delivery_date: string;
  schedule: string;
  items: OrderItem[];
}
export interface OrderContext {
  store_code: string;
  kitchen_code: string;
  delivery_date: string;
  schedule_code: string;
}
export interface SendResult {
  id: number;
  status: OrderStatus;
  editable: boolean;
  items_sent: number;
  excluded_below_one: number;
}

function cookieValue(name: string): string {
  const prefix = name + "=";
  const hit = document.cookie.split(";").map((item) => item.trim()).find(
    (item) => item.startsWith(prefix),
  );
  return hit ? decodeURIComponent(hit.slice(prefix.length)) : "";
}

function errorDetail(data: unknown, fallback: string): string {
  if (data && typeof data === "object") {
    const json = data as Record<string, unknown>;
    if (typeof json.detail === "string") return json.detail;
    for (const [field, value] of Object.entries(json)) {
      if (typeof value === "string") return field + ": " + value;
      if (Array.isArray(value)) return field + ": " + value.join(", ");
    }
  }
  return fallback;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  url: string, options: RequestInit = {},
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRFToken", cookieValue("csrftoken"));
  }
  const response = await fetch(url, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers,
  });
  const contentType = response.headers.get("content-type") || "";
  let data: unknown = null;
  if (contentType.includes("application/json")) {
    data = await response.json();
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      errorDetail(data, "Permintaan gagal. Silakan coba lagi."),
    );
  }
  return data as T;
}

export async function initializeSession(): Promise<SessionInfo | null> {
  await apiRequest<{ ok: boolean }>("/api/v1/auth/csrf/");
  try {
    return await apiRequest<SessionInfo>("/api/v1/auth/me/");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function login(username: string, password: string): Promise<SessionInfo> {
  await apiRequest<{ ok: boolean }>("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return apiRequest<SessionInfo>("/api/v1/auth/me/");
}

export async function logout(): Promise<void> {
  await apiRequest<{ ok: boolean }>("/api/v1/auth/logout/", { method: "POST" });
}

export async function loadOrder(
  context: OrderContext, signal?: AbortSignal,
): Promise<StoreOrder> {
  const query = new URLSearchParams(context as unknown as Record<string, string>);
  return apiRequest<StoreOrder>("/api/v1/store-orders/?" + query.toString(), { signal });
}

export async function saveDraft(
  context: OrderContext, quantities: Record<number, string>,
): Promise<StoreOrder> {
  const items = Object.entries(quantities).map(([product_id, qty]) => ({
    product_id: Number(product_id),
    qty: qty.trim() || "0",
  }));
  return apiRequest<StoreOrder>("/api/v1/store-orders/", {
    method: "POST",
    body: JSON.stringify({ ...context, items }),
  });
}

export async function sendOrder(orderId: number): Promise<SendResult> {
  return apiRequest<SendResult>("/api/v1/store-orders/" + orderId + "/send/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type ProductionStoreStatus = "KIRIM" | "PROSES_PRODUKSI";

export interface ProductionDemand {
  delivery_date: string;
  kitchen: NamedOption;
  schedule: NamedOption;
  basis: "KIRIM_AND_PROSES_PRODUKSI";
  production_date: null;
  note: string;
  summary: {
    stores_total: number;
    stores_sent: number;
    stores_in_production: number;
    sku_count: number;
    qty_total: string | null;
    qty_uom: string | null;
    qty_by_uom: { uom: string; qty: string }[];
    qty_invalid: boolean;
  };
  store_statuses: {
    store_code: string;
    store_name: string;
    status: ProductionStoreStatus;
    order_id: number | null;
    auto_submitted: boolean;
  }[];
  items: {
    product_id: number;
    sku: string;
    name: string;
    uom: string;
    qty_total: string;
    store_count: number;
    sources: {
      store_code: string;
      store_name: string;
      order_id: number;
      qty: string;
      auto_submitted: boolean;
      status: ProductionQueueStatus;
    }[];
  }[];
}

export function loadProductionDemand(
  params: { delivery_date: string; kitchen_code: string; schedule_code: string },
  signal?: AbortSignal,
): Promise<ProductionDemand> {
  const query = new URLSearchParams(params);
  return apiRequest<ProductionDemand>(
    "/api/v1/production/demand/?" + query.toString(),
    { signal },
  );
}

export interface RecentSentOrder {
  order_id: number;
  store_code: string;
  store_name: string;
  kitchen_code: string;
  kitchen_name: string;
  schedule_code: string;
  schedule_name: string;
  delivery_date: string;
  submitted_at: string | null;
  auto_submitted: boolean;
  sku_count: number;
  qty_total: string | null;
  qty_uom: string | null;
  qty_by_uom: { uom: string; qty: string }[];
  qty_invalid: boolean;
}

export function loadRecentSentOrders(signal?: AbortSignal): Promise<{ limit: number; items: RecentSentOrder[] }> {
  return apiRequest<{ limit: number; items: RecentSentOrder[] }>(
    "/api/v1/production/recent-orders/", { signal },
  );
}

export type ProductionQueueStatus = "KIRIM" | "PROSES_PRODUKSI";
export type ProductionInboxFilter = "ALL" | ProductionQueueStatus;
export interface ProductionInboxOrder {
  order_id: number;
  status: ProductionQueueStatus;
  store_code: string;
  store_name: string;
  kitchen_code: string;
  kitchen_name: string;
  delivery_date: string;
  schedule_code: string;
  schedule_name: string;
  sku_count: number;
  qty_total: string;
  qty_uom: string | null;
  auto_submitted: boolean;
}
export interface ProductionInbox {
  status_filter: ProductionInboxFilter;
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  counts: { all: number; kirim: number; proses_produksi: number };
  items: ProductionInboxOrder[];
}
export function loadProductionInbox(
  status: ProductionInboxFilter = "ALL", page = 1, signal?: AbortSignal,
): Promise<ProductionInbox> {
  const query = new URLSearchParams({ status, page: String(page) });
  return apiRequest<ProductionInbox>(
    "/api/v1/production/orders/?" + query.toString(), { signal },
  );
}
