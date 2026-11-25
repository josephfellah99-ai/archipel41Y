import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, getToken, setToken, type ApiError } from "./api";

export type User = { id: string; email: string; full_name: string; role: string; role_label: string; color?: string; job_title?: string; version: number };
export type Agency = { id: string; name: string; is_demo: boolean; siret?: string; address?: string; email?: string; phone?: string };
export type Perms = { read: boolean; write: boolean; delete: boolean; validate: boolean; admin: boolean };

type Toast = { id: number; kind: "ok" | "error" | "info"; text: string };

type Ctx = {
  user: User | null;
  agency: Agency | null;
  perms: Perms;
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

const NO_PERMS: Perms = { read: false, write: false, delete: false, validate: false, admin: false };

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
      setMode(me.mode);
      await reloadProjects();
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
      user, agency, perms, mode, loading, login, logout, refreshMe, projectId, setProjectId, projects, reloadProjects,
      theme, toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")), toast, toastError, assistantOpen, setAssistantOpen,
    }),
    [user, agency, perms, mode, loading, login, logout, refreshMe, projectId, setProjectId, projects, reloadProjects, theme, toast, toastError, assistantOpen],
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
