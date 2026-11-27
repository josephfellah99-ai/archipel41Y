import { CalendarDays, ChevronLeft, ChevronRight, Plus, AlertTriangle, Sparkles, Trash2, FileText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { addDays, EVENT_COLORS, EVENT_KINDS, isoDate, startOfWeek, timeFr } from "../lib/format";
import { AsyncButton, Field, Markdown, Modal, Notice, PageHeader, Select, Spinner } from "../components/ui";

type View = "jour" | "semaine" | "mois";
const HOURS = Array.from({ length: 13 }, (_, i) => i + 7); // 7h → 19h

function localInput(iso: string) {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function EventModal({ ev, onClose, onSaved }: { ev: any; onClose: () => void; onSaved: () => void }) {
  const { perms, user, projects, toast, toastError } = useApp();
  const users = useApi<any[]>("/api/users");
  const clients = useApi<any[]>("/api/clients");
  const companies = useApi<any[]>("/api/companies");
  const docs = useApi<any[]>(ev.project_id ? `/api/documents?project_id=${ev.project_id}` : "/api/documents?limit=100");
  const [f, setF] = useState<any>({ ...ev, start: localInput(ev.start), end: localInput(ev.end) });
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [extName, setExtName] = useState("");
  const canEdit = perms.write;
  const valid = (v: string) => !!v && !Number.isNaN(new Date(v).getTime());
  const dateError = !valid(f.start) ? "Date et heure de début à renseigner." : !valid(f.end) ? "Date et heure de fin à renseigner."
    : new Date(f.end) <= new Date(f.start) ? "La fin doit être postérieure au début." : null;
  const payload = () => ({ ...f, start: new Date(f.start).toISOString(), end: new Date(f.end).toISOString(), project_id: f.project_id || null,
    client_id: f.client_id || null, company_id: f.company_id || null,
    reminder_minutes: f.reminder_minutes === "" || f.reminder_minutes === null ? null : Number(f.reminder_minutes) });
  useEffect(() => {
    if (!valid(f.start) || !valid(f.end)) return;
    const t = setTimeout(() => {
      const p = payload();
      api.call("POST", "/api/events/check", { start: p.start, end: p.end, participants: p.participants, organizer_id: p.organizer_id || user?.id, exclude_id: f.id })
        .then(setConflicts).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.start, f.end, f.participants]);
  const save = async () => {
    try {
      if (dateError) throw new Error(dateError);
      const p = payload();
      const r = f.id ? await api.put(`/api/events/${f.id}`, { ...p, version: ev.version }, `RDV ${f.title}`) : await api.post("/api/events", p, `RDV ${f.title}`);
      if (r.__queued) toast("Rendez-vous enregistré hors ligne.", "info");
      else if (r.conflicts?.length) toast(`Enregistré – attention : ${r.conflicts.length} conflit(s) d'agenda.`, "info");
      else toast("Rendez-vous enregistré.");
      onSaved(); onClose();
    } catch (e) { toastError(e); }
  };
  const toggleUser = (u: any) => {
    const has = f.participants.some((p: any) => p.user_id === u.id);
    setF({ ...f, participants: has ? f.participants.filter((p: any) => p.user_id !== u.id) : [...f.participants, { user_id: u.id, name: u.full_name }] });
  };
  const summarize = async () => {
    try {
      if (f.id && f.minutes !== ev.minutes) await api.put(`/api/events/${f.id}`, { minutes: f.minutes, version: ev.version });
      const r = await api.call("POST", `/api/events/${f.id}/summarize`);
      setSummary(r.summary);
    } catch (e) { toastError(e); }
  };
  return (
    <Modal open onClose={onClose} title={f.id ? f.title : "Nouveau rendez-vous"} wide footer={<>
      {f.id && perms.write && <button className="btn-ghost text-danger mr-auto" onClick={async () => { try { await api.del(`/api/events/${f.id}`); onSaved(); onClose(); } catch (e) { toastError(e); } }}><Trash2 size={15} /> Supprimer</button>}
      {f.id && <button className="btn-secondary" onClick={async () => { try { const r = await api.call("POST", "/api/reports", { kind: "compte_rendu", fmt: "pdf", event_id: f.id }); await download(r.download_url); } catch (e) { toastError(e); } }}><FileText size={15} /> Compte rendu PDF</button>}
      <button className="btn-secondary" onClick={onClose}>Fermer</button>
      {canEdit && <AsyncButton onClick={save} disabled={!f.title?.trim() || !!dateError}>Enregistrer</AsyncButton>}</>}>
      {conflicts.length > 0 && <div className="mb-4"><Notice tone="warn"><div className="flex items-center gap-2 font-medium"><AlertTriangle size={15} /> Conflit d'agenda détecté</div>
        <ul className="list-disc pl-5 mt-1">{conflicts.map((c) => <li key={c.event_id}>{c.title} ({new Date(c.start).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}) – {c.participants.join(", ")}</li>)}</ul></Notice></div>}
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Objet *" className="sm:col-span-2"><input className="input" disabled={!canEdit} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Type"><Select disabled={!canEdit} value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={Object.entries(EVENT_KINDS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Projet / chantier"><Select disabled={!canEdit} value={f.project_id || ""} onChange={(v) => setF({ ...f, project_id: v })} placeholder="— Aucun —" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} /></Field>
        <Field label="Client"><Select disabled={!canEdit} value={f.client_id || ""} onChange={(v) => setF({ ...f, client_id: v || null })} placeholder="— Aucun —" options={(clients.data || []).map((c) => ({ value: c.id, label: c.name }))} /></Field>
        <Field label="Entreprise"><Select disabled={!canEdit} value={f.company_id || ""} onChange={(v) => setF({ ...f, company_id: v || null })} placeholder="— Aucune —" options={(companies.data || []).map((c) => ({ value: c.id, label: c.name }))} /></Field>
        <Field label="Début" required><input className="input" type="datetime-local" disabled={!canEdit} value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} /></Field>
        <Field label="Fin" required error={valid(f.start) && dateError ? dateError : null}><input className="input" type="datetime-local" disabled={!canEdit} value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} /></Field>
        <Field label="Lieu"><input className="input" disabled={!canEdit} value={f.location || ""} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
        <Field label="Rappel"><Select disabled={!canEdit} value={f.reminder_minutes === null || f.reminder_minutes === undefined ? "" : String(f.reminder_minutes)} onChange={(v) => setF({ ...f, reminder_minutes: v })}
          placeholder="Aucun rappel" options={[["10", "10 minutes avant"], ["30", "30 minutes avant"], ["60", "1 heure avant"], ["1440", "La veille"]].map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <div className="sm:col-span-2"><div className="label">Participants de l'agence</div>
          <div className="flex flex-wrap gap-2">{(users.data || []).map((u) => {
            const on = f.participants.some((p: any) => p.user_id === u.id);
            return <button key={u.id} type="button" disabled={!canEdit} onClick={() => toggleUser(u)} className={`chip border ${on ? "bg-forest text-white border-forest dark:text-bg" : "border-line"}`}>{u.full_name}</button>;
          })}</div>
          <div className="flex flex-wrap gap-2 mt-2">{f.participants.filter((p: any) => !p.user_id).map((p: any, i: number) => (
            <span key={i} className="chip bg-sunken">{p.name}{canEdit && <button onClick={() => setF({ ...f, participants: f.participants.filter((x: any) => x !== p) })} className="ml-1">×</button>}</span>))}</div>
          {canEdit && <div className="flex gap-2 mt-2 max-w-md"><input className="input py-1" placeholder="Participant externe (client, entreprise…)" value={extName} onChange={(e) => setExtName(e.target.value)} />
            <button className="btn-secondary py-1" onClick={() => { if (extName.trim()) { setF({ ...f, participants: [...f.participants, { name: extName.trim() }] }); setExtName(""); } }}>Ajouter</button></div>}
        </div>
        <Field label="Ordre du jour / description" className="sm:col-span-2"><textarea className="input min-h-[60px]" disabled={!canEdit} value={f.description || ""} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <Field label="Compte rendu" className="sm:col-span-2"><textarea className="input min-h-[120px]" disabled={!canEdit} value={f.minutes || ""} onChange={(e) => setF({ ...f, minutes: e.target.value })} placeholder="Présents, décisions, actions (qui / quoi / quand)…" /></Field>
        {f.id && <div className="sm:col-span-2"><button className="btn-secondary" onClick={summarize} disabled={!f.minutes}><Sparkles size={15} /> Résumer le compte rendu</button>
          {summary && <div className="mt-3 rounded-lg bg-sunken p-3"><Markdown text={summary} /></div>}</div>}
        <Field label="Documents associés" className="sm:col-span-2">
          <select multiple className="input h-28" disabled={!canEdit} value={f.document_ids || []} onChange={(e) => setF({ ...f, document_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
            {(docs.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select></Field>
      </div>
    </Modal>
  );
}

export default function Agenda() {
  const { user, perms, projectId } = useApp();
  const [params] = useSearchParams();
  const [view, setView] = useState<View>(window.innerWidth < 640 ? "jour" : "semaine");
  const [cursor, setCursor] = useState(new Date());
  const [who, setWho] = useState("");
  const [onlyProject, setOnlyProject] = useState(false);
  const [edit, setEdit] = useState<any>(null);
  const users = useApi<any[]>("/api/users");
  const range = useMemo(() => {
    if (view === "jour") { const s = new Date(cursor); s.setHours(0, 0, 0, 0); return [s, addDays(s, 1)]; }
    if (view === "semaine") { const s = startOfWeek(cursor); return [s, addDays(s, 7)]; }
    const s = startOfWeek(new Date(cursor.getFullYear(), cursor.getMonth(), 1)); return [s, addDays(s, 42)];
  }, [view, cursor]);
  const [deadlines, setDeadlines] = useState(true);
  const nav = useNavigate();
  const qs = new URLSearchParams({ start: range[0].toISOString(), end: range[1].toISOString(), ...(who ? { participant: who } : {}), ...(onlyProject && projectId ? { project_id: projectId } : {}),
    ...(deadlines ? { include_deadlines: "true" } : {}) });
  const { data, loading, reload } = useApi<any[]>(`/api/events?${qs}`);
  useEffect(() => { const id = params.get("event"); if (id) api.get(`/api/events/${id}`).then(setEdit).catch(() => {}); }, [params]);
  const move = (n: number) => setCursor(view === "jour" ? addDays(cursor, n) : view === "semaine" ? addDays(cursor, 7 * n) : new Date(cursor.getFullYear(), cursor.getMonth() + n, 1));
  const newEvent = (d: Date, h = 9) => {
    const s = new Date(d); s.setHours(h, 0, 0, 0);
    setEdit({ title: "", kind: "rdv_client", start: s.toISOString(), end: new Date(s.getTime() + 3600000).toISOString(), participants: user ? [{ user_id: user.id, name: user.full_name }] : [],
      reminder_minutes: 30, project_id: projectId || "", document_ids: [], organizer_id: user?.id });
  };
  const events = data || [];
  // conflits visibles : chevauchements partagés entre au moins un participant
  const overlapping = useMemo(() => {
    const ids = new Set<string>();
    for (const a of events) for (const b of events) {
      if (a.id >= b.id) continue;
      if (new Date(a.start) < new Date(b.end) && new Date(b.start) < new Date(a.end)) {
        const pa = new Set(a.participants.map((p: any) => p.user_id || p.name));
        if (b.participants.some((p: any) => pa.has(p.user_id || p.name))) { ids.add(a.id); ids.add(b.id); }
      }
    }
    return ids;
  }, [events]);
  const days = view === "jour" ? [range[0]] : Array.from({ length: 7 }, (_, i) => addDays(range[0], i));
  const title = view === "mois" ? cursor.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })
    : view === "semaine" ? `Semaine du ${range[0].toLocaleDateString("fr-FR", { day: "numeric", month: "long" })}` : cursor.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  const evBlock = (e: any) => (
    <button key={e.id} onClick={() => (e.readonly ? nav(e.kind === "echeance_tache" ? "/planning" : `/projets/${e.project_id}`) : setEdit(e))}
      title={e.readonly ? "Échéance (lecture seule) : ouvrir le planning ou le projet" : e.source && e.source !== "archipel" ? `Synchronisé avec ${e.source === "google" ? "Google Agenda" : "Outlook"}` : undefined}
      className={`w-full text-left rounded-md px-2 py-1 text-[11px] leading-tight text-white mb-1 hover:opacity-90 relative ${e.readonly ? "opacity-90 border border-dashed border-white/60" : ""}`}
      style={{ background: EVENT_COLORS[e.kind] || EVENT_COLORS.autre }}>
      {overlapping.has(e.id) && <AlertTriangle size={11} className="absolute right-1 top-1" />}
      <div className="font-medium truncate pr-3">{e.title}</div><div className="opacity-80">{e.readonly ? "échéance" : `${timeFr(e.start)}–${timeFr(e.end)}`}{e.source && e.source !== "archipel" ? ` · ${e.source === "google" ? "Google" : "Outlook"}` : ""}</div>
    </button>
  );
  return (
    <div>
      <PageHeader title="Agenda et rendez-vous" icon={<CalendarDays size={22} />} subtitle={<span className="first-letter:uppercase inline-block">{title}</span>}
        actions={<>
          <div className="flex rounded-lg border border-line overflow-hidden">{(["jour", "semaine", "mois"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`px-3 py-1.5 text-sm capitalize ${view === v ? "bg-forest text-white dark:text-bg" : "bg-surface hover:bg-sunken"}`}>{v}</button>))}</div>
          <button className="btn-secondary px-2" onClick={() => move(-1)} aria-label="Précédent"><ChevronLeft size={16} /></button>
          <button className="btn-secondary" onClick={() => setCursor(new Date())}>Aujourd'hui</button>
          <button className="btn-secondary px-2" onClick={() => move(1)} aria-label="Suivant"><ChevronRight size={16} /></button>
          {perms.write && <button className="btn-primary" onClick={() => newEvent(cursor)}><Plus size={16} /> Rendez-vous</button>}
        </>} />
      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <Select className="w-56" value={who} onChange={setWho} placeholder="Tous les collaborateurs" options={(users.data || []).map((u) => ({ value: u.id, label: u.full_name }))} />
        {projectId && <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={onlyProject} onChange={(e) => setOnlyProject(e.target.checked)} /> Projet actif uniquement</label>}
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={deadlines} onChange={(e) => setDeadlines(e.target.checked)} /> Échéances (tâches, remises de phase)</label>
        <div className="flex flex-wrap gap-2 text-xs">{Object.entries(EVENT_KINDS).map(([k, l]) => <span key={k} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: EVENT_COLORS[k] }} />{l}</span>)}</div>
        {overlapping.size > 0 && <span className="chip bg-warn/15 text-warn"><AlertTriangle size={12} /> {overlapping.size} rendez-vous en conflit</span>}
      </div>
      {loading && !data ? <Spinner /> : view === "mois" ? (
        <div className="card overflow-hidden">
          <div className="grid grid-cols-7 bg-sunken text-xs text-muted">{["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."].map((d) => <div key={d} className="px-2 py-1.5">{d}</div>)}</div>
          <div className="grid grid-cols-7">{Array.from({ length: 42 }, (_, i) => {
            const d = addDays(range[0], i);
            const list = events.filter((e) => isoDate(new Date(e.start)) === isoDate(d));
            const out = d.getMonth() !== cursor.getMonth();
            return (
              <div key={i} className={`min-h-[96px] border-t border-l border-line p-1 ${out ? "bg-sunken/50 text-muted" : ""}`} onDoubleClick={() => perms.write && newEvent(d)}>
                <div className={`text-xs mb-1 ${isoDate(d) === isoDate(new Date()) ? "font-semibold text-forest" : ""}`}>{d.getDate()}</div>
                {list.slice(0, 3).map(evBlock)}{list.length > 3 && <div className="text-[10px] text-muted">+{list.length - 3} autre(s)</div>}
              </div>);
          })}</div>
        </div>
      ) : (
        <div className="card overflow-x-auto scrollbar-thin">
          <div className={`grid min-w-[640px]`} style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0,1fr))` }}>
            <div />{days.map((d) => <div key={d.toISOString()} className={`px-2 py-2 text-xs border-l border-line ${isoDate(d) === isoDate(new Date()) ? "text-forest font-semibold" : "text-muted"}`}>
              {d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" })}</div>)}
            {HOURS.map((h) => (
              <div key={h} className="contents">
                <div className="text-[10px] text-muted text-right pr-2 pt-1 border-t border-line">{h}:00</div>
                {days.map((d) => {
                  const list = events.filter((e) => { const s = new Date(e.start); return isoDate(s) === isoDate(d) && (s.getHours() === h || (h === 7 && s.getHours() < 7)); });
                  return <div key={d.toISOString() + h} className="border-t border-l border-line min-h-[52px] p-1 hover:bg-sunken/40" onDoubleClick={() => perms.write && newEvent(d, h)}>{list.map(evBlock)}</div>;
                })}
              </div>))}
          </div>
          <div className="text-xs text-muted px-4 py-2 border-t border-line">Double-cliquez sur un créneau pour créer un rendez-vous.</div>
        </div>
      )}
      {edit && <EventModal ev={edit} onClose={() => setEdit(null)} onSaved={reload} />}
    </div>
  );
}
