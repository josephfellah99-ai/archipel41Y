/**
 * Accès à l'API Archipel41 – stratégie « local-first » côté navigateur :
 *  - chaque réponse GET est conservée dans IndexedDB (lecture hors connexion) ;
 *  - hors connexion, les créations/modifications/suppressions sont placées dans
 *    une file d'attente (outbox) persistante, puis rejouées au retour du réseau ;
 *  - une création hors ligne reçoit un identifiant client (X-Client-Id) : le rejeu
 *    est idempotent ;
 *  - un rejeu refusé pour conflit de version (HTTP 409) est conservé et présenté
 *    à l'utilisateur, jamais écrasé silencieusement.
 */
import { openDB, type IDBPDatabase } from "idb";

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

type OutboxItem = { id: string; method: string; url: string; body: any; createdAt: string; label: string; clientId?: string };
type ConflictItem = OutboxItem & { error: string; current?: any };

let dbPromise: Promise<IDBPDatabase> | null = null;
function db() {
  if (!dbPromise) {
    dbPromise = openDB("archipel41", 1, {
      upgrade(d) {
        d.createObjectStore("cache");
        d.createObjectStore("outbox", { keyPath: "id" });
        d.createObjectStore("conflicts", { keyPath: "id" });
      },
    });
  }
  return dbPromise;
}

const listeners = new Set<() => void>();
export function onSyncChange(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const emit = () => listeners.forEach((f) => f());

export function getToken(): string | null {
  try {
    return localStorage.getItem("a41.token");
  } catch {
    return null;
  }
}
export function setToken(t: string | null) {
  try {
    if (t) localStorage.setItem("a41.token", t);
    else localStorage.removeItem("a41.token");
  } catch {
    /* stockage indisponible */
  }
}

export const apiBase = (window as any).ARCHIPEL_API_BASE || "";
export function apiUrl(path: string, withToken = false) {
  const u = apiBase + path;
  if (!withToken) return u;
  const t = getToken();
  return u + (u.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(t || "");
}

function uuid() {
  return (crypto as any).randomUUID ? crypto.randomUUID() : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function errorMessage(data: any, status: number): string {
  if (!data) return `Erreur ${status}`;
  if (typeof data.detail === "string") return data.detail;
  if (data.detail?.message) return data.detail.message;
  return `Erreur ${status}`;
}

async function raw(method: string, path: string, body?: any, extraHeaders: Record<string, string> = {}) {
  const headers: Record<string, string> = { ...extraHeaders };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(apiBase + path, { method, headers, body: payload });
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json().catch(() => null) : null;
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    setToken(null);
    window.dispatchEvent(new Event("a41:logout"));
  }
  if (!res.ok) {
    if (res.status >= 500 && !data?.ref && !path.includes("/client-errors")) {
      // erreur serveur non consignée par le moteur (ex. proxy, moteur indisponible) : signalée depuis l'interface
      import("./errors").then((m) => m.reportClientError("api", errorMessage(data, res.status), { api: path, status: res.status })).catch(() => {});
    }
    throw new ApiError(res.status, errorMessage(data, res.status), data);
  }
  return data;
}

export function isNetworkError(e: unknown) {
  return e instanceof TypeError || (e instanceof ApiError && e.status === 0);
}

export const offline = { value: typeof navigator !== "undefined" ? !navigator.onLine : false, cachedAt: null as string | null };

export async function get<T = any>(path: string): Promise<T & { __cached?: string }> {
  try {
    const data = await raw("GET", path);
    offline.value = false;
    db().then((d) => d.put("cache", { data, at: new Date().toISOString() }, path)).catch(() => {});
    return data;
  } catch (e) {
    if (isNetworkError(e)) {
      offline.value = true;
      emit();
      const hit = await db().then((d) => d.get("cache", path)).catch(() => null);
      if (hit) {
        offline.cachedAt = hit.at;
        if (Array.isArray(hit.data)) return Object.assign([...hit.data], { __cached: hit.at }) as any;
        return { ...hit.data, __cached: hit.at };
      }
      throw new ApiError(0, "Hors connexion : cette page n'a pas encore été consultée sur cet appareil.");
    }
    throw e;
  }
}

/** Mutation JSON pouvant être mise en file d'attente hors connexion. */
export async function mutate<T = any>(method: "POST" | "PUT" | "DELETE", path: string, body?: any, label = "Modification"): Promise<T & { __queued?: boolean }> {
  const clientId = method === "POST" ? uuid() : undefined;
  try {
    const data = await raw(method, path, body, clientId ? { "X-Client-Id": clientId } : {});
    offline.value = false;
    return data;
  } catch (e) {
    if (isNetworkError(e) && !(body instanceof FormData)) {
      offline.value = true;
      const item: OutboxItem = { id: uuid(), method, url: path, body, createdAt: new Date().toISOString(), label, clientId };
      await (await db()).put("outbox", item);
      emit();
      return { ...(body || {}), id: clientId, __queued: true } as any;
    }
    throw e;
  }
}

export const api = {
  get,
  post: <T = any>(p: string, b?: any, label?: string) => mutate<T>("POST", p, b, label),
  put: <T = any>(p: string, b?: any, label?: string) => mutate<T>("PUT", p, b, label),
  del: <T = any>(p: string, label?: string) => mutate<T>("DELETE", p, undefined, label),
  /** Appel direct, sans mise en file (uploads, actions serveur). */
  call: <T = any>(method: string, p: string, b?: any) => raw(method, p, b) as Promise<T>,
  upload: <T = any>(p: string, form: FormData) => raw("POST", p, form) as Promise<T>,
};

export async function outboxItems(): Promise<OutboxItem[]> {
  return (await db()).getAll("outbox");
}
export async function conflictItems(): Promise<ConflictItem[]> {
  return (await db()).getAll("conflicts");
}
export async function dropConflict(id: string) {
  await (await db()).delete("conflicts", id);
  emit();
}

let flushing = false;
/** Rejoue la file d'attente dans l'ordre chronologique. */
export async function flushOutbox(): Promise<{ sent: number; conflicts: number }> {
  if (flushing) return { sent: 0, conflicts: 0 };
  flushing = true;
  let sent = 0;
  let conflicts = 0;
  try {
    const d = await db();
    const items = (await d.getAll("outbox")).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    for (const it of items) {
      try {
        await raw(it.method, it.url, it.body, it.clientId ? { "X-Client-Id": it.clientId } : {});
        await d.delete("outbox", it.id);
        sent++;
      } catch (e) {
        if (isNetworkError(e)) break;
        const err = e as ApiError;
        await d.put("conflicts", { ...it, error: err.message, current: err.data?.detail?.current });
        await d.delete("outbox", it.id);
        conflicts++;
      }
    }
    if (sent) offline.value = false;
  } finally {
    flushing = false;
    emit();
  }
  return { sent, conflicts };
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    offline.value = false;
    flushOutbox();
  });
  window.addEventListener("offline", () => {
    offline.value = true;
    emit();
  });
  setInterval(() => {
    if (navigator.onLine) flushOutbox();
  }, 30000);
}

export async function download(path: string, filename?: string, body?: any) {
  const token = getToken();
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(apiBase + path, body !== undefined ? { method: "POST", headers, body: JSON.stringify(body) } : { headers });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, errorMessage(data, res.status), data);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = /filename\*=UTF-8''([^;]+)/.exec(cd) || /filename="([^"]+)"/.exec(cd);
  const name = filename || (m ? decodeURIComponent(m[1]) : "export");
  const desktop = (window as any).archipelDesktop;
  if (desktop?.saveFile) {
    await desktop.saveFile(name, new Uint8Array(await blob.arrayBuffer()));
    return;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** Bureau (Windows) : ouvre une copie du document dans le logiciel associé à son format. */
export async function openNative(path: string, filename: string): Promise<{ ok: boolean; error?: string }> {
  const desktop = (window as any).archipelDesktop;
  if (!desktop?.openFile) return { ok: false, error: "Disponible dans l'application Windows uniquement." };
  const token = getToken();
  const res = await fetch(apiBase + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "Fichier indisponible");
  return desktop.openFile(filename, new Uint8Array(await (await res.blob()).arrayBuffer()));
}

export async function blobUrl(path: string): Promise<string> {
  const token = getToken();
  const res = await fetch(apiBase + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "Prévisualisation indisponible");
  return URL.createObjectURL(await res.blob());
}
