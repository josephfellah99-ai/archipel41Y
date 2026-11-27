import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, getToken, setToken, type ApiError } from "./api";

export type User = { id: string; email: string; full_name: string; role: string; role_label: string; color?: string; job_title?: string; version: number };
export type Agency = { id: string; name: string; is_demo: boolean; siret?: string; address?: string; email?: string; phone?: string };
export type Level = "none" | "read" | "write" | "full";
export type Perms = { read: boolean; write: boolean; delete: boolean; validate: boolean; admin: boolean; modules: Record<string, Level> };
export type GuestScope = { invitation: string; expires_at: string; modules: string[]; can_download: boolean; can_comment: boolean; projects: { id: string; code: string; name: string }[] };
const RANK: Record<string, number> = { none: 0, read: 1, write: 2, full: 3 };
/** Niveau d'accès à un module (affichage) — le serveur applique de toute façon le même contrôle. */
export const canModule = (p: Perms, module: string, need: Level = "read") => RANK[p.modules?.[module] ?? (p.admin ? "full" : p.write ? "write" : p.read ? "read" : "none")] >= RANK[need];

type Toast = { id: number; kind: "ok" | "error" | "info"; text: string };

type Ctx = {
  user: User | null;
  agency: Agency | null;
  perms: Perms;
  guest: GuestScope | null;
  mode: string;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
  projectId: string | null;
  setProjectId: (id: string | null) => void;
  projects: any[];
  reloadProjects: () => Promise<void>;
  theme: "light" | "dark";
  toggleTheme: () => void;
  toast: (text: string, kind?: Toast["kind"]) => void;
  toastError: (e: unknown) => void;
  assistantOpen: boolean;
  setAssistantOpen: (v: boolean) => void;
};

const AppCtx = createContext<Ctx>(null as any);
export const useApp = () => useContext(AppCtx);

const NO_PERMS: Perms = { read: false, write: false, delete: false, validate: false, admin: false, modules: {} };

function ls(key: string, fallback: string | null = null) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}
function lsSet(key: string, v: string | null) {
  try {
    if (v === null) localStorage.removeItem(key);
    else localStorage.setItem(key, v);
  } catch {
    /* ignoré */
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [agency, setAgency] = useState<Agency | null>(null);
  const [perms, setPerms] = useState<Perms>(NO_PERMS);
  const [guest, setGuest] = useState<GuestScope | null>(null);
  const [mode, setMode] = useState("server");
  const [loading, setLoading] = useState(true);
  const [projectId, setProjectIdState] = useState<string | null>(ls("a41.project"));
  const [projects, setProjects] = useState<any[]>([]);
  const [theme, setTheme] = useState<"light" | "dark">(
    (ls("a41.theme") as any) || (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  );
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const tid = useRef(0);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    lsSet("a41.theme", theme);
  }, [theme]);

  const toast = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    const id = ++tid.current;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  const toastError = useCallback((e: unknown) => toast((e as ApiError)?.message || "Une erreur est survenue.", "error"), [toast]);

  const reloadProjects = useCallback(async () => {
    try {
      const rows = await api.get<any[]>("/api/projects");
      setProjects(Array.isArray(rows) ? rows : []);
    } catch {
      /* hors connexion sans cache */
    }
  }, []);

  const refreshMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<any>("/api/auth/me");
      setUser(me.user);
      setAgency(me.agency);
      setPerms(me.permissions);
      setGuest(me.guest || null);
      setMode(me.mode);
      if (!me.guest) await reloadProjects();
    } catch (e: any) {
      if (e?.status === 401) setUser(null);
    } finally {
      setLoading(false);
    }
  }, [reloadProjects]);

  useEffect(() => {
    refreshMe();
    const out = () => {
      setUser(null);
      setPerms(NO_PERMS);
    };
    window.addEventListener("a41:logout", out);
    return () => window.removeEventListener("a41:logout", out);
  }, [refreshMe]);

  const login = useCallback(async (token: string) => {
    setToken(token);
    setLoading(true);
    await refreshMe();
  }, [refreshMe]);

  const logout = useCallback(() => {
    api.call("POST", "/api/auth/logout").catch(() => {});
    setGuest(null);
    setToken(null);
    setUser(null);
    setPerms(NO_PERMS);
    setProjects([]);
  }, []);

  const setProjectId = useCallback((id: string | null) => {
    setProjectIdState(id);
    lsSet("a41.project", id);
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      user, agency, perms, guest, mode, loading, login, logout, refreshMe, projectId, setProjectId, projects, reloadProjects,
      theme, toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")), toast, toastError, assistantOpen, setAssistantOpen,
    }),
    [user, agency, perms, guest, mode, loading, login, logout, refreshMe, projectId, setProjectId, projects, reloadProjects, theme, toast, toastError, assistantOpen],
  );

  return (
    <AppCtx.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-[80] flex flex-col gap-2 max-w-sm no-print" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id}
            className={`card px-4 py-3 text-sm border-l-4 ${t.kind === "error" ? "border-l-danger" : t.kind === "info" ? "border-l-info" : "border-l-ok"}`}>
            {t.text}
          </div>
        ))}
      </div>
    </AppCtx.Provider>
  );
}

/** Chargement de données avec rechargement et état hors connexion. */
export function useApi<T = any>(path: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!path) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const d: any = await api.get<T>(path);
      setCachedAt(d?.__cached || null);
      setData(d);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Erreur de chargement");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => {
    load();
  }, [load]);
  return { data, error, loading, reload: load, setData, cachedAt };
}

/**
 * État de formulaire alimenté par une donnée serveur, PROTÉGÉ contre les rechargements :
 * tant que l'utilisateur a des modifications non enregistrées, une nouvelle version reçue du serveur
 * (rechargement en arrière-plan, synchronisation…) ne remplace jamais sa saisie ; `stale` signale
 * qu'une version plus récente existe. Après un enregistrement réussi, appeler `markSaved()`.
 */
export function useEditable<S, T = S>(source: S | null | undefined, map?: (s: S) => T) {
  const conv = (s: S) => (map ? map(s) : (s as unknown as T));
  const [value, setRaw] = useState<T | null>(source ? conv(source) : null);
  const base = useRef<string>(source ? JSON.stringify(conv(source)) : "");
  const dirty = useRef(false);
  const [isDirty, setIsDirty] = useState(false);
  const [stale, setStale] = useState(false);
  useEffect(() => {
    if (!source) return;
    const next = conv(source);
    const key = JSON.stringify(next);
    if (key === base.current) return; // rechargement sans changement réel : rien à faire
    base.current = key;
    if (dirty.current) { setStale(true); return; }
    setRaw(next);
    setStale(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);
  const setValue = useCallback((v: T | ((prev: T) => T)) => {
    dirty.current = true;
    setIsDirty(true);
    setRaw((prev) => (typeof v === "function" ? (v as (p: T) => T)(prev as T) : v));
  }, []);
  const markSaved = useCallback(() => { dirty.current = false; setIsDirty(false); setStale(false); }, []);
  const discard = useCallback(() => {
    dirty.current = false; setIsDirty(false); setStale(false);
    if (source) { const next = conv(source); base.current = JSON.stringify(next); setRaw(next); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);
  return { value, setValue, dirty: isDirty, stale, markSaved, discard };
}
