import {
  LayoutDashboard, FolderKanban, FileSpreadsheet, CalendarDays, GanttChartSquare, Map, Sparkles, Files, Users, Wallet, FileText,
  Settings, Search, Moon, Sun, LogOut, Menu, X, Wifi, WifiOff, RefreshCw, Bell, AlertTriangle, ChevronDown,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, conflictItems, flushOutbox, offline, onSyncChange, outboxItems } from "../lib/api";
import { useApp } from "../lib/app";
import logo from "../logo.svg";
import { AssistantDrawer } from "../pages/Assistant";

export const NAV = [
  { to: "/", label: "Tableau de bord", icon: LayoutDashboard, n: "01" },
  { to: "/projets", label: "Projets et chantiers", icon: FolderKanban, n: "02" },
  { to: "/devis", label: "Devis et comparateur", icon: FileSpreadsheet, n: "03" },
  { to: "/agenda", label: "Agenda", icon: CalendarDays, n: "04" },
  { to: "/planning", label: "Planning et météo", icon: GanttChartSquare, n: "05" },
  { to: "/urbanisme", label: "Urbanisme", icon: Map, n: "06" },
  { to: "/assistant", label: "Assistant IA", icon: Sparkles, n: "07" },
  { to: "/documents", label: "Documents", icon: Files, n: "08" },
  { to: "/annuaire", label: "Clients et entreprises", icon: Users, n: "09" },
  { to: "/finances", label: "Finances", icon: Wallet, n: "10" },
  { to: "/rapports", label: "Rapports", icon: FileText, n: "11" },
];

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

function Reminders() {
  const { user } = useApp();
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    if (!user) return;
    const seen = new Set<string>(JSON.parse(sessionStorage.getItem("a41.reminded") || "[]"));
    const check = async () => {
      try {
        const r: any[] = await api.get("/api/events/reminders");
        setItems(r);
        for (const ev of r) {
          if (seen.has(ev.reminder_key)) continue;
          seen.add(ev.reminder_key);
          sessionStorage.setItem("a41.reminded", JSON.stringify([...seen]));
          const body = `${new Date(ev.start).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}${ev.location ? " – " + ev.location : ""}`;
          const desktop = (window as any).archipelDesktop;
          if (desktop?.notify) desktop.notify(ev.title, body);
          else if ("Notification" in window && Notification.permission === "granted") new Notification(ev.title, { body, icon: "./icon-192.png" });
        }
      } catch { /* hors ligne */ }
    };
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
    check();
    const t = setInterval(check, 60000);
    return () => clearInterval(t);
  }, [user]);
  const nav = useNavigate();
  return (
    <button className="btn-ghost h-8 w-8 p-0 relative" title={items.length ? `${items.length} rappel(s)` : "Aucun rappel"} onClick={() => nav("/agenda")}>
      <Bell size={16} />
      {items.length > 0 && <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-danger" />}
    </button>
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
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={() => setMobile(false)}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-forest text-white dark:text-bg" : "text-ink/80 hover:bg-sunken"}`}>
            <n.icon size={17} strokeWidth={1.8} />
            <span className="flex-1 truncate">{n.label}</span>
            <span className="text-[10px] opacity-50 tabular-nums">{n.n}</span>
          </NavLink>
        ))}
      </div>
      <div className="p-3 border-t border-line space-y-0.5">
        <NavLink to="/parametres" onClick={() => setMobile(false)}
          className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? "bg-forest text-white dark:text-bg" : "text-ink/80 hover:bg-sunken"}`}>
          <Settings size={17} strokeWidth={1.8} /> Paramètres
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
        <header className="h-14 shrink-0 border-b border-line bg-surface/80 backdrop-blur flex items-center gap-2 px-3 sm:px-5 no-print">
          <button className="btn-ghost p-1.5 lg:hidden" onClick={() => setMobile(true)} aria-label="Menu"><Menu size={19} /></button>
          <ProjectPicker />
          <form className="flex-1 max-w-md relative" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/recherche?q=${encodeURIComponent(q.trim())}`); }}>
            <Search size={15} className="absolute left-3 top-2.5 text-muted" />
            <input className="input h-8 pl-9" placeholder="Rechercher dans l'agence…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Recherche globale" />
          </form>
          <div className="flex-1" />
          <ConnectionBadge />
          <Reminders />
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
