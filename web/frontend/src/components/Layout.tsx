import {
  LayoutDashboard, FolderKanban, CalendarDays, GanttChartSquare, Map, Sparkles, Files, Users, Wallet, FileText,
  Settings, Search, Moon, Sun, LogOut, Menu, X, Wifi, WifiOff, RefreshCw, Bell, AlertTriangle, ChevronDown, HardHat, Scale, History,
  Contact, CheckCheck, HelpCircle, BookOpen,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api, blobUrl, conflictItems, flushOutbox, offline, onSyncChange, outboxItems } from "../lib/api";
import { helpFor } from "../lib/help";
import { canModule, useApp, type Perms } from "../lib/app";
import { dateTimeFr } from "../lib/format";
import logo from "../logo.svg";
import { AssistantDrawer } from "../pages/Assistant";

type NavItem = { to: string; label: string; icon: any; n?: string; module?: string; admin?: boolean; sub?: NavItem[] };
/** Navigation principale : 12 entrées, sous-entrées pour les outils rattachés. Affichage selon les autorisations
 *  (le serveur applique de toute façon les mêmes contrôles). */
export const NAV: NavItem[] = [
  { to: "/", label: "Tableau de bord", icon: LayoutDashboard, n: "01" },
  { to: "/projets", label: "Projets", icon: FolderKanban, n: "02", module: "projets", sub: [{ to: "/annuaire", label: "Clients et entreprises", icon: Contact, module: "annuaire" }] },
  { to: "/chantiers", label: "Chantiers", icon: HardHat, n: "03", module: "projets", sub: [{ to: "/planning", label: "Planning et météo", icon: GanttChartSquare, module: "planning" }] },
  { to: "/devis", label: "Comparateur", icon: Scale, n: "04", module: "devis" },
  { to: "/documents", label: "Documents", icon: Files, n: "05", module: "documents", sub: [{ to: "/rapports", label: "Rapports", icon: FileText, module: "rapports" }] },
  { to: "/terrain", label: "Terrain et cartographie", icon: Map, n: "06", module: "terrain" },
  { to: "/agenda", label: "Agenda", icon: CalendarDays, n: "07", module: "agenda" },
  { to: "/equipe", label: "Équipe", icon: Users, n: "08", module: "equipe" },
  { to: "/finances", label: "Finances", icon: Wallet, n: "09", module: "finances" },
  { to: "/assistant", label: "Assistant IA", icon: Sparkles, n: "10", module: "assistant" },
  { to: "/historique", label: "Historique et activité", icon: History, n: "11" },
];
const visible = (n: NavItem, p: Perms) => (!n.module || canModule(p, n.module)) && (!n.admin || p.admin);

function ConnectionBadge() {
  const { mode, toast } = useApp();
  const [state, setState] = useState({ off: offline.value, queued: 0, conflicts: 0 });
  const [sync, setSync] = useState<any>(null);
  useEffect(() => {
    const refresh = async () => {
      setState({ off: offline.value || !navigator.onLine, queued: (await outboxItems()).length, conflicts: (await conflictItems()).length });
    };
    refresh();
    const un = onSyncChange(refresh);
    const t = setInterval(refresh, 5000);
    return () => { un(); clearInterval(t); };
  }, []);
  useEffect(() => {
    if (mode !== "desktop") return;
    const load = () => api.get("/api/sync/status").then(setSync).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [mode]);
  const runSync = async () => {
    if (mode === "desktop" && sync?.configured) {
      try {
        const r = await api.call("POST", "/api/sync/run");
        toast(`Synchronisation : ${r.push.accepted} envoyée(s), ${r.pull.applied || 0} reçue(s)${r.push.conflicts + (r.pull.conflicts || 0) ? `, ${r.push.conflicts + (r.pull.conflicts || 0)} conflit(s)` : ""}.`);
        setSync(await api.get("/api/sync/status"));
      } catch (e: any) {
        toast(e.message, "error");
      }
    } else {
      const r = await flushOutbox();
      toast(r.sent ? `${r.sent} modification(s) hors ligne envoyée(s).` : "Aucune modification en attente.", "info");
    }
  };
  const pending = state.queued + (sync?.pending_changes || 0);
  const conflicts = state.conflicts + (sync?.open_conflicts || 0);
  return (
    <button onClick={runSync} title={state.off ? "Hors connexion – vos modifications sont conservées sur cet appareil" : "Synchroniser"}
      className={`chip h-8 px-2.5 border ${state.off ? "border-warn/40 bg-warn/10 text-warn" : "border-line bg-surface text-muted"}`}>
      {state.off ? <WifiOff size={14} /> : <Wifi size={14} />}
      <span className="hidden md:inline">{state.off ? "Hors ligne" : mode === "desktop" ? (sync?.configured ? "Synchronisé" : "Local") : "En ligne"}</span>
      {pending > 0 && <span className="rounded-full bg-warn text-white px-1.5 text-[10px]">{pending}</span>}
      {conflicts > 0 && <AlertTriangle size={13} className="text-danger" />}
      <RefreshCw size={13} />
    </button>
  );
}

function ProjectPicker() {
  const { projects, projectId, setProjectId } = useApp();
  return (
    <div className="relative hidden sm:block">
      <select aria-label="Projet actif" className="input h-8 py-0 pr-8 pl-3 w-56 lg:w-72 appearance-none" value={projectId || ""}
        onChange={(e) => setProjectId(e.target.value || null)}>
        <option value="">Tous les projets</option>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.code} – {p.name}</option>)}
      </select>
      <ChevronDown size={14} className="absolute right-2.5 top-2 text-muted pointer-events-none" />
    </div>
  );
}

/** Centre de notifications : activité qui vous concerne + rappels de rendez-vous. */
function Notifications() {
  const { user } = useApp();
  const [data, setData] = useState<{ unread: number; items: any[] }>({ unread: 0, items: [] });
  const [reminders, setReminders] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const load = useCallback(async () => {
    try { setData(await api.get("/api/notifications?limit=30")); } catch { /* hors ligne */ }
  }, []);
  useEffect(() => {
    if (!user) return;
    const seen = new Set<string>(JSON.parse(sessionStorage.getItem("a41.reminded") || "[]"));
    const check = async () => {
      load();
      try {
        const r: any[] = await api.get("/api/events/reminders");
        setReminders(r);
        for (const ev of r) {
          if (seen.has(ev.reminder_key)) continue;
          seen.add(ev.reminder_key);
          sessionStorage.setItem("a41.reminded", JSON.stringify([...seen]));
          const body = `${new Date(ev.start).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}${ev.location ? " – " + ev.location : ""}`;
          const desktop = (window as any).archipelDesktop;
          if (desktop?.notify) desktop.notify(ev.title, body);
          else if ("Notification" in window && Notification.permission === "granted") new Notification(ev.title, { body, icon: "./icon-192.png" });
        }
      } catch { /* hors ligne ou agenda non autorisé */ }
    };
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
    check();
    const t = setInterval(check, 60000);
    return () => clearInterval(t);
  }, [user, load]);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  const markAll = async () => { try { await api.call("POST", "/api/notifications/read", {}); load(); } catch { /* */ } };
  const go = async (n: any) => {
    setOpen(false);
    if (!n.read_at) { try { await api.call("POST", "/api/notifications/read", { ids: [n.id] }); load(); } catch { /* */ } }
    if (n.link) nav(n.link);
  };
  const count = data.unread + reminders.length;
  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost h-8 w-8 p-0 relative" aria-label={`Notifications (${count})`} title="Notifications" onClick={() => setOpen(!open)}>
        <Bell size={16} />
        {count > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-danger text-white text-[10px] leading-4 text-center tabular-nums">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-[60] w-[min(92vw,380px)] card shadow-xl">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-line">
            <span className="text-sm font-semibold">Notifications</span>
            {data.unread > 0 && <button className="text-xs text-sage flex items-center gap-1" onClick={markAll}><CheckCheck size={13} /> Tout marquer comme lu</button>}
          </div>
          <div className="max-h-[60vh] overflow-y-auto scrollbar-thin">
            {reminders.map((r) => (
              <button key={r.reminder_key} onClick={() => { setOpen(false); nav("/agenda"); }} className="w-full text-left px-4 py-2.5 border-b border-line hover:bg-sunken/60 flex gap-2">
                <CalendarDays size={14} className="text-info mt-0.5 shrink-0" />
                <span className="text-sm"><b className="font-medium">Rappel</b> · {r.title}<span className="block text-xs text-muted">{dateTimeFr(r.start)}{r.location ? ` · ${r.location}` : ""}</span></span>
              </button>))}
            {!data.items.length && !reminders.length && <div className="px-4 py-8 text-sm text-muted text-center">Aucune notification.</div>}
            {data.items.map((n) => (
              <button key={n.id} onClick={() => go(n)} className={`w-full text-left px-4 py-2.5 border-b border-line hover:bg-sunken/60 flex gap-2 ${n.read_at ? "opacity-70" : ""}`}>
                <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${n.read_at ? "bg-transparent" : "bg-sage"}`} />
                <span className="min-w-0"><span className="block text-sm font-medium truncate">{n.title}</span>
                  {n.body && <span className="block text-xs text-muted line-clamp-2">{n.body}</span>}
                  <span className="block text-[11px] text-muted mt-0.5">{dateTimeFr(n.created_at)}</span></span>
              </button>))}
          </div>
        </div>)}
    </div>
  );
}

/** Aide contextuelle de l'écran affiché, avec accès au guide pratique embarqué. */
function HelpPanel() {
  const { toastError } = useApp();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const h = helpFor(loc.pathname);
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  const guide = async () => {
    try {
      const u = await blobUrl("/api/guides/guide-pratique");
      const desktop = (window as any).archipelDesktop;
      if (desktop?.openFile) { const b = new Uint8Array(await (await fetch(u)).arrayBuffer()); await desktop.openFile("ARCHIPEL41_GUIDE_PRATIQUE.pdf", b); }
      else window.open(u, "_blank", "noopener");
    } catch (e) { toastError(e); }
  };
  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost h-8 w-8 p-0" aria-label="Aide sur cet écran" title="Aide sur cet écran" aria-expanded={open} onClick={() => setOpen(!open)}><HelpCircle size={16} /></button>
      {open && (
        <div role="dialog" aria-label={`Aide — ${h.title}`} className="absolute right-0 top-10 z-[60] w-[min(92vw,400px)] card shadow-xl">
          <div className="px-4 pt-3 pb-2 border-b border-line">
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted">Aide{h.n ? ` · ${h.n}` : ""}</div>
            <div className="text-base font-semibold">{h.title}</div>
            <div className="text-sm text-muted mt-0.5">{h.but}</div>
          </div>
          <div className="px-4 py-3 space-y-3 max-h-[60vh] overflow-y-auto scrollbar-thin text-sm">
            <div><div className="text-[11px] uppercase tracking-wider text-muted mb-1">Comment faire</div>
              <ol className="list-decimal pl-5 space-y-1">{h.etapes.map((x, i) => <li key={i}>{x}</li>)}</ol></div>
            {h.savoir && h.savoir.length > 0 && <div><div className="text-[11px] uppercase tracking-wider text-muted mb-1">Bon à savoir</div>
              <ul className="space-y-1">{h.savoir.map((x, i) => <li key={i} className="pl-3 relative before:absolute before:left-0 before:top-2 before:h-1 before:w-1.5 before:bg-danger">{x}</li>)}</ul></div>}
          </div>
          <div className="px-4 py-2.5 border-t border-line"><button className="text-sm text-sage flex items-center gap-1.5" onClick={guide}><BookOpen size={14} /> Ouvrir le guide pratique complet</button></div>
        </div>)}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, agency, logout, theme, toggleTheme, setAssistantOpen, perms } = useApp();
  const [mobile, setMobile] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const side = (
    <nav className="flex flex-col h-full">
      <div className="flex items-center gap-2.5 px-5 h-16 shrink-0">
        <img src={logo} alt="" className="h-8 w-8" />
        <div className="leading-tight">
          <div className="font-semibold tracking-[0.18em] text-sm text-forest">ARCHIPEL41</div>
          <div className="text-[10.5px] text-muted truncate max-w-[150px]">{agency?.name}</div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-2 space-y-0.5">
        {NAV.filter((n) => visible(n, perms)).map((n) => (
          <div key={n.to}>
            <NavLink to={n.to} end={n.to === "/"} onClick={() => setMobile(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-forest text-white dark:text-bg" : "text-ink/80 hover:bg-sunken"}`}>
              <n.icon size={17} strokeWidth={1.8} />
              <span className="flex-1 truncate">{n.label}</span>
              <span className="text-[10px] opacity-50 tabular-nums">{n.n}</span>
            </NavLink>
            {n.sub?.filter((x) => visible(x, perms)).map((x) => (
              <NavLink key={x.to} to={x.to} onClick={() => setMobile(false)}
                className={({ isActive }) => `flex items-center gap-2.5 rounded-lg pl-9 pr-3 py-1.5 text-[13px] transition ${isActive ? "text-forest font-medium bg-forest/10" : "text-muted hover:text-ink hover:bg-sunken"}`}>
                <x.icon size={14} strokeWidth={1.8} /><span className="truncate">{x.label}</span>
              </NavLink>))}
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-line space-y-0.5">
        <NavLink to="/parametres" onClick={() => setMobile(false)}
          className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? "bg-forest text-white dark:text-bg" : "text-ink/80 hover:bg-sunken"}`}>
          <Settings size={17} strokeWidth={1.8} /> <span className="flex-1">Paramètres</span><span className="text-[10px] opacity-50 tabular-nums">12</span>
        </NavLink>
        <div className="flex items-center gap-2.5 px-3 py-2">
          <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold text-white" style={{ background: user?.color || "#718578" }}>
            {user?.full_name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-sm truncate">{user?.full_name}</div>
            <div className="text-[11px] text-muted">{user?.role_label}</div>
          </div>
          <button className="btn-ghost p-1.5" title="Se déconnecter" onClick={logout}><LogOut size={16} /></button>
        </div>
      </div>
    </nav>
  );
  return (
    <div className="h-full flex">
      <aside className="hidden lg:block w-64 shrink-0 border-r border-line bg-surface no-print">{side}</aside>
      {mobile && (
        <div className="fixed inset-0 z-50 lg:hidden" onClick={() => setMobile(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute left-0 top-0 bottom-0 w-72 bg-surface shadow-xl" onClick={(e) => e.stopPropagation()}>{side}</aside>
        </div>
      )}
      <div className="flex-1 min-w-0 flex flex-col">
        {agency?.is_demo && (
          <div className="bg-warn/15 text-warn text-xs text-center py-1 px-3 font-medium no-print">
            ESPACE DE DÉMONSTRATION – données entièrement fictives, séparées de vos données réelles
          </div>
        )}
        <header className="relative z-40 h-14 shrink-0 border-b border-line bg-surface/80 backdrop-blur flex items-center gap-2 px-3 sm:px-5 no-print">
          <button className="btn-ghost p-1.5 lg:hidden" onClick={() => setMobile(true)} aria-label="Menu"><Menu size={19} /></button>
          <ProjectPicker />
          <form className="flex-1 max-w-md relative" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/recherche?q=${encodeURIComponent(q.trim())}`); }}>
            <Search size={15} className="absolute left-3 top-2.5 text-muted" />
            <input className="input h-8 pl-9" placeholder="Rechercher dans l'agence…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Recherche globale" />
          </form>
          <div className="flex-1" />
          <ConnectionBadge />
          <HelpPanel />
          <Notifications />
          <button className="btn-ghost h-8 w-8 p-0" onClick={toggleTheme} title={theme === "dark" ? "Mode clair" : "Mode sombre"}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          {perms.read && (
            <button className="btn-primary h-8 px-3" onClick={() => setAssistantOpen(true)}>
              <Sparkles size={15} /> <span className="hidden sm:inline">Assistant</span>
            </button>
          )}
        </header>
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">{children}</div>
        </main>
      </div>
      <AssistantDrawer />
    </div>
  );
}

export function MobileClose({ onClick }: { onClick: () => void }) {
  return <button className="btn-ghost p-1.5" onClick={onClick}><X size={18} /></button>;
}
