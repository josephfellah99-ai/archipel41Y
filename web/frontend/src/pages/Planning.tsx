import { GanttChartSquare, Plus, CloudRain, Wind, Thermometer, Check, X, Flag, AlertTriangle, Link2, Snowflake } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { ACTIVITY_LABELS, addDays, dateFr, isoDate, toNum } from "../lib/format";
import { AsyncButton, Card, Empty, ErrorBox, Field, Modal, Notice, NumberInput, PageHeader, Select, Spinner, Tabs } from "../components/ui";
import { NeedProject } from "./Quotes";

const DAY_MS = 86400000;
const parse = (s: string) => new Date(s + "T00:00:00");
const diffDays = (a: Date, b: Date) => Math.round((a.getTime() - b.getTime()) / DAY_MS);

function TaskModal({ task, tasks, projectId, onClose, onSaved }: { task: any; tasks: any[]; projectId: string; onClose: () => void; onSaved: () => void }) {
  const { perms, toast, toastError } = useApp();
  const users = useApi<any[]>("/api/users");
  const companies = useApi<any[]>("/api/companies");
  const lots = useApi<any[]>(`/api/lots?project_id=${projectId}`);
  const [f, setF] = useState<any>({ ...task });
  const can = perms.write;
  const save = async () => {
    try {
      if (!f.start_date) throw new Error("Date de début : champ obligatoire.");
      const dur = toNum(f.duration_days, "Durée") ?? 0;
      if (!Number.isInteger(dur) || dur < 0) throw new Error("Durée : nombre entier de jours attendu (0 pour un jalon).");
      const body = { ...f, project_id: projectId, duration_days: dur, progress: toNum(f.progress, "Avancement") ?? 0, responsible_id: f.responsible_id || null,
        company_id: f.company_id || null, lot_id: f.lot_id || null, milestone: !!f.milestone || dur === 0 };
      for (const k of ["end_date", "earliest_start", "dependency_violation", "expected_progress", "late", "late_days", "critical", "baseline_drift"]) delete body[k];
      if (f.id) await api.put(`/api/tasks/${f.id}`, body, `Tâche ${f.name}`); else await api.post("/api/tasks", body, `Tâche ${f.name}`);
      toast("Tâche enregistrée."); onSaved(); onClose();
    } catch (e) { toastError(e); }
  };
  return (
    <Modal open onClose={onClose} title={f.id ? f.name : "Nouvelle tâche"} footer={<>
      {f.id && perms.delete && <button className="btn-ghost text-danger mr-auto" onClick={async () => { try { await api.del(`/api/tasks/${f.id}`); onSaved(); onClose(); } catch (e) { toastError(e); } }}>Supprimer</button>}
      <button className="btn-secondary" onClick={onClose}>Annuler</button>{can && <AsyncButton onClick={save} disabled={!f.name?.trim()}>Enregistrer</AsyncButton>}</>}>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Intitulé *" className="sm:col-span-2"><input className="input" disabled={!can} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Début" required><input className="input" type="date" disabled={!can} value={f.start_date || ""} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
        <Field label="Durée (jours, 0 = jalon)"><NumberInput integer min={0} disabled={!can} value={f.duration_days} onChange={(v) => setF({ ...f, duration_days: v })} /></Field>
        <Field label="Type d'activité (analyse météo)"><Select disabled={!can} value={f.activity} onChange={(v) => setF({ ...f, activity: v })} options={Object.entries(ACTIVITY_LABELS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Priorité"><Select disabled={!can} value={f.priority} onChange={(v) => setF({ ...f, priority: v })} options={[{ value: "basse", label: "Basse" }, { value: "normale", label: "Normale" }, { value: "haute", label: "Haute" }]} /></Field>
        <Field label="Responsable"><Select disabled={!can} value={f.responsible_id || ""} onChange={(v) => setF({ ...f, responsible_id: v })} placeholder="—" options={(users.data || []).map((u) => ({ value: u.id, label: u.full_name }))} /></Field>
        <Field label="Entreprise"><Select disabled={!can} value={f.company_id || ""} onChange={(v) => setF({ ...f, company_id: v })} placeholder="—" options={(companies.data || []).map((c) => ({ value: c.id, label: c.name }))} /></Field>
        <Field label="Lot"><Select disabled={!can} value={f.lot_id || ""} onChange={(v) => setF({ ...f, lot_id: v })} placeholder="—" options={(lots.data || []).map((l) => ({ value: l.id, label: `${l.code} ${l.name}` }))} /></Field>
        <Field label="Avancement (%)"><NumberInput min={0} max={100} suffix="%" disabled={!can} value={f.progress} onChange={(v) => setF({ ...f, progress: v })} /></Field>
        <Field label="Dépend de (fin → début)" className="sm:col-span-2">
          <select multiple className="input h-28" disabled={!can} value={f.depends_on || []} onChange={(e) => setF({ ...f, depends_on: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
            {tasks.filter((t) => t.id !== f.id).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select></Field>
        <Field label="Notes" className="sm:col-span-2"><textarea className="input" disabled={!can} value={f.notes || ""} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
    </Modal>
  );
}

function Gantt({ sched, onEdit, onMove, canEdit }: { sched: any; onEdit: (t: any) => void; onMove: (t: any, start: string, dur: number) => void; canEdit: boolean }) {
  const [zoom, setZoom] = useState(22);
  const [drag, setDrag] = useState<{ id: string; mode: "move" | "resize"; x0: number; dd: number } | null>(null);
  const tasks = sched.tasks.filter((t: any) => t.kind !== "todo");
  const start = useMemo(() => addDays(parse(sched.start || isoDate(new Date())), -3), [sched.start]);
  const end = useMemo(() => addDays(parse(sched.end || isoDate(new Date())), 10), [sched.end]);
  const ndays = Math.max(30, diffDays(end, start));
  const row = 38;
  const idx = Object.fromEntries(tasks.map((t: any, i: number) => [t.id, i]));
  const geom = (t: any) => {
    let s = diffDays(parse(t.start_date), start);
    let d = Math.max(t.milestone ? 0 : 1, t.duration_days);
    if (drag && drag.id === t.id) { if (drag.mode === "move") s += drag.dd; else d = Math.max(1, d + drag.dd); }
    return { x: s * zoom, w: Math.max(t.milestone ? 0 : zoom, d * zoom), s, d };
  };
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!drag) return;
    const mv = (e: PointerEvent) => setDrag((d) => (d ? { ...d, dd: Math.round((e.clientX - d.x0) / zoom) } : d));
    const up = () => {
      setDrag((d) => {
        if (d && d.dd !== 0) {
          const t = tasks.find((x: any) => x.id === d.id);
          if (t) {
            if (d.mode === "move") onMove(t, isoDate(addDays(parse(t.start_date), d.dd)), t.duration_days);
            else onMove(t, t.start_date, Math.max(1, t.duration_days + d.dd));
          }
        }
        return null;
      });
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
  }, [drag, zoom, tasks, onMove]);
  const todayX = diffDays(new Date(new Date().toDateString()), start) * zoom;
  const months: { x: number; label: string }[] = [];
  for (let i = 0; i < ndays; i++) { const d = addDays(start, i); if (d.getDate() === 1 || i === 0) months.push({ x: i * zoom, label: d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) }); }
  return (
    <div>
      <div className="flex items-center gap-3 px-5 pb-3 text-xs text-muted flex-wrap">
        <span>Zoom</span><input type="range" min={8} max={44} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} aria-label="Zoom" />
        <span className="flex items-center gap-1"><span className="h-2.5 w-5 rounded bg-sage" /> tâche</span>
        <span className="flex items-center gap-1"><span className="h-2.5 w-5 rounded border-2 border-danger" /> chemin critique</span>
        <span className="flex items-center gap-1"><span className="h-2.5 w-5 rounded bg-warn" /> en retard</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-5 rounded bg-muted/40" /> référence</span>
        {canEdit && <span>· Glissez une barre pour la déplacer, son bord droit pour changer la durée.</span>}
      </div>
      <div className="flex border-t border-line">
          <div className="shrink-0 bg-surface border-r border-line w-40 sm:w-[260px]">
            <div className="h-11 border-b border-line px-3 flex items-end pb-1 text-xs text-muted">Tâche</div>
            {tasks.map((t: any) => (
              <button key={t.id} onClick={() => onEdit(t)} className="w-full text-left px-3 flex items-center gap-2 border-b border-line/60 hover:bg-sunken text-sm" style={{ height: row }}>
                {t.milestone ? <Flag size={13} className="text-forest shrink-0" /> : <span className={`h-2 w-2 rounded-full shrink-0 ${t.late ? "bg-warn" : t.critical ? "bg-danger" : "bg-sage"}`} />}
                <span className="truncate flex-1">{t.name}</span>
                {t.dependency_violation && <span title="Dépendance non respectée"><Link2 size={13} className="text-danger" /></span>}
                <span className="text-[10px] text-muted">{t.progress}%</span>
              </button>))}
          </div>
        <div className="overflow-x-auto scrollbar-thin flex-1" ref={ref}>
          <div className="relative" style={{ width: ndays * zoom, height: 44 + tasks.length * row }}>
            <div className="h-11 border-b border-line relative">
              {months.map((m) => <div key={m.x} className="absolute top-1 text-[10px] text-muted capitalize" style={{ left: m.x + 3 }}>{m.label}</div>)}
              {Array.from({ length: ndays }, (_, i) => { const d = addDays(start, i); return (
                <div key={i} className={`absolute bottom-0 text-[9px] text-center ${d.getDay() === 0 || d.getDay() === 6 ? "text-muted/50" : "text-muted"}`} style={{ left: i * zoom, width: zoom }}>{zoom >= 16 ? d.getDate() : d.getDay() === 1 ? d.getDate() : ""}</div>); })}
            </div>
            {Array.from({ length: ndays }, (_, i) => { const d = addDays(start, i); return (d.getDay() === 0 || d.getDay() === 6) ? <div key={i} className="absolute bg-sunken/70" style={{ left: i * zoom, width: zoom, top: 44, bottom: 0 }} /> : null; })}
            {todayX > 0 && <div className="absolute w-px bg-danger/70 z-10" style={{ left: todayX, top: 30, bottom: 0 }}><span className="absolute -top-1 -left-5 text-[9px] text-danger">auj.</span></div>}
            <svg className="absolute inset-0 pointer-events-none z-10" width={ndays * zoom} height={44 + tasks.length * row}>
              <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="rgb(var(--muted))" /></marker></defs>
              {tasks.flatMap((t: any) => (t.depends_on || []).filter((d: string) => idx[d] !== undefined).map((d: string) => {
                const a = geom(tasks[idx[d]]), b = geom(t);
                const y1 = 44 + idx[d] * row + row / 2, y2 = 44 + idx[t.id] * row + row / 2;
                const x1 = a.x + a.w, x2 = b.x;
                const mid = Math.max(x1 + 8, x2 - 8);
                return <path key={d + t.id} d={`M${x1},${y1} H${mid} V${y2} H${x2 - 1}`} fill="none" stroke={t.dependency_violation ? "rgb(var(--danger))" : "rgb(var(--muted))"} strokeWidth={1.2} markerEnd="url(#arrow)" opacity={0.8} />;
              }))}
            </svg>
            {tasks.map((t: any, i: number) => {
              const g = geom(t);
              const y = 44 + i * row;
              const bs = t.baseline_start ? diffDays(parse(t.baseline_start), start) * zoom : null;
              const be = t.baseline_end ? (diffDays(parse(t.baseline_end), start) + 1) * zoom : null;
              return (
                <div key={t.id} className="absolute border-b border-line/40" style={{ top: y, height: row, left: 0, right: 0 }}>
                  {bs !== null && be !== null && !t.milestone && <div className="absolute h-1 rounded bg-muted/35" style={{ left: bs, width: Math.max(4, be - bs), top: row - 9 }} />}
                  {t.milestone ? (
                    <div className="absolute h-3.5 w-3.5 rotate-45 bg-forest cursor-pointer" style={{ left: g.x - 7, top: row / 2 - 7 }} onClick={() => onEdit(t)}
                      onPointerDown={(e) => canEdit && setDrag({ id: t.id, mode: "move", x0: e.clientX, dd: 0 })} title={`${t.name} – ${dateFr(t.start_date)}`} />
                  ) : (
                    <div className={`absolute rounded-md overflow-hidden select-none ${canEdit ? "cursor-grab active:cursor-grabbing" : ""} ${t.late ? "bg-warn/80" : "bg-sage/85"} ${t.critical ? "ring-2 ring-danger" : ""}`}
                      style={{ left: g.x, width: g.w, top: 8, height: row - 18, touchAction: "none" }} title={`${t.name}\n${dateFr(t.start_date)} → ${dateFr(t.end_date)} · ${t.duration_days} j · ${t.progress} %${t.late ? `\nEn retard (attendu ${t.expected_progress} %)` : ""}`}
                      onPointerDown={(e) => canEdit && setDrag({ id: t.id, mode: "move", x0: e.clientX, dd: 0 })} onDoubleClick={() => onEdit(t)}>
                      <div className="h-full bg-forest/70" style={{ width: `${t.progress}%` }} />
                      <span className="absolute inset-0 px-1.5 text-[10px] text-white flex items-center truncate">{g.w > 60 ? t.name : ""}</span>
                      {canEdit && <div className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize bg-black/10" onPointerDown={(e) => { e.stopPropagation(); setDrag({ id: t.id, mode: "resize", x0: e.clientX, dd: 0 }); }} />}
                    </div>
                  )}
                </div>);
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function WeatherPanel({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const { perms, toast, toastError } = useApp();
  const w = useApi<any>(`/api/projects/${projectId}/weather`);
  const props = useApi<any[]>(`/api/proposals?project_id=${projectId}`);
  const gen = async () => {
    try { const r = await api.call("POST", `/api/projects/${projectId}/weather/proposals`); toast(r.length ? `${r.length} proposition(s) d'ajustement créée(s) – à valider.` : "Aucune nouvelle proposition."); props.reload(); } catch (e) { toastError(e); }
  };
  const decide = async (id: string, d: "accept" | "reject") => {
    try { const r = await api.call("POST", `/api/proposals/${id}/${d}`); toast(d === "accept" ? `Proposition acceptée : ${r.moved_tasks.length} tâche(s) décalée(s).` : "Proposition refusée."); props.reload(); onChanged(); w.reload(); } catch (e) { toastError(e); }
  };
  const risky = new Set((w.data?.analysis || []).flatMap((a: any) => a.risky_days.map((d: any) => d.date)));
  return (
    <div className="space-y-6">
      {w.error ? <ErrorBox error={w.error} /> : !w.data ? <Spinner label="Prévisions météo…" /> : (
        <Card title={`Prévisions – ${w.data.location.label || "chantier"}`} actions={<span className={`chip ${w.data.forecast.simulated ? "bg-warn/15 text-warn" : "bg-sunken text-muted"}`}>{w.data.forecast.source}</span>}>
          <div className="grid grid-flow-col auto-cols-[minmax(88px,1fr)] gap-2 overflow-x-auto scrollbar-thin pb-1">
            {w.data.forecast.days.map((d: any) => (
              <div key={d.date} className={`rounded-lg p-2 text-center ${risky.has(d.date) ? "bg-warn/15 ring-1 ring-warn/50" : "bg-sunken"}`}>
                <div className="text-[11px] text-muted capitalize">{new Date(d.date + "T12:00").toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" })}</div>
                <div className="text-sm font-semibold mt-0.5">{Math.round(d.tmax)}°<span className="text-muted font-normal"> / {Math.round(d.tmin)}°</span></div>
                <div className="text-[10px] text-muted truncate">{d.label}</div>
                <div className="flex justify-center gap-2 text-[10px] text-muted mt-1"><span className="flex items-center"><CloudRain size={10} />{d.rain}</span><span className="flex items-center"><Wind size={10} />{Math.round(d.gust)}</span></div>
              </div>))}
          </div>
          <p className="text-xs text-muted mt-3">{w.data.disclaimer}</p>
        </Card>
      )}
      <Card title="Analyse des activités prévues" actions={perms.write && <button className="btn-primary" onClick={gen}>Proposer des ajustements</button>}>
        {!w.data?.analysis?.length ? <Empty title="Aucune activité sensible exposée" icon={<Thermometer size={18} />}>Aucune tâche sensible à la météo (béton, couverture, façade…) n'est concernée par des conditions défavorables dans l'horizon de prévision.</Empty> : (
          <ul className="space-y-3">{w.data.analysis.map((a: any) => (
            <li key={a.task_id} className="rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-2"><span className="font-medium text-sm">{a.task}</span><span className="chip bg-sunken text-muted">{a.activity_label}</span><span className="text-xs text-muted">{dateFr(a.start_date)} → {dateFr(a.end_date)}</span></div>
              <ul className="text-xs mt-2 space-y-0.5">{a.risky_days.map((d: any) => <li key={d.date}><b>{dateFr(d.date)}</b> : {d.risks.join(" · ")}</li>)}</ul>
              <div className="text-sm mt-2 text-forest">→ {a.recommendation}</div>
            </li>))}</ul>)}
      </Card>
      <Card title="Propositions en attente de validation">
        {!props.data?.length ? <Empty title="Aucune proposition en attente" /> : (
          <ul className="divide-y divide-line">{props.data.map((p: any) => (
            <li key={p.id} className="py-3 flex flex-col sm:flex-row gap-3 sm:items-center">
              <div className="flex-1 text-sm"><span className="chip bg-info/15 text-info mr-2">{p.source}</span>{p.reason}{p.payload?.simulated && <span className="chip bg-warn/15 text-warn ml-2">météo simulée</span>}</div>
              {perms.validate ? <div className="flex gap-2">
                {p.kind === "decaler_tache" && <button className="btn-primary" onClick={() => decide(p.id, "accept")}><Check size={15} /> Accepter</button>}
                <button className="btn-secondary" onClick={() => decide(p.id, "reject")}><X size={15} /> {p.kind === "decaler_tache" ? "Refuser" : "Classer"}</button></div>
                : <span className="text-xs text-muted">Validation réservée aux chefs de projet</span>}
            </li>))}</ul>)}
      </Card>
    </div>
  );
}

export default function Planning() {
  const { projectId, perms, toast, toastError } = useApp();
  const { data, loading, error, reload } = useApi<any>(projectId ? `/api/projects/${projectId}/schedule` : null);
  const [edit, setEdit] = useState<any>(null);
  const [tab, setTab] = useState("gantt");
  if (!projectId) return <><PageHeader title="Planning et météo" icon={<GanttChartSquare size={22} />} /><NeedProject what="Le planning" /></>;
  const move = async (t: any, start: string, dur: number) => {
    try { await api.put(`/api/tasks/${t.id}`, { start_date: start, duration_days: dur, version: t.version }, `Tâche ${t.name}`); reload(); } catch (e) { toastError(e); reload(); }
  };
  const newTask = () => setEdit({ name: "", start_date: isoDate(new Date()), duration_days: 5, activity: "autre", priority: "normale", progress: 0, depends_on: [], kind: "chantier" });
  const todos = (data?.tasks || []).filter((t: any) => t.kind === "todo");
  return (
    <div>
      <PageHeader title="Planning et météo" icon={<GanttChartSquare size={22} />}
        subtitle={data && <>{dateFr(data.start)} → {dateFr(data.end)} · {data.tasks.length} tâche(s){data.late_count ? <span className="text-warn"> · {data.late_count} en retard</span> : ""}{data.violations ? <span className="text-danger"> · {data.violations} dépendance(s) non respectée(s)</span> : ""}</>}
        actions={<>
          {perms.validate && <button className="btn-secondary" onClick={async () => { await api.call("POST", `/api/projects/${projectId}/baseline`); toast("Planning de référence enregistré."); reload(); }}>Figer la référence</button>}
          {perms.write && data?.violations > 0 && <button className="btn-secondary" onClick={async () => { const r = await api.call("POST", `/api/projects/${projectId}/schedule/propagate`); toast(`${r.length} proposition(s) de recalage à valider (onglet Météo et propositions).`); }}><AlertTriangle size={15} /> Proposer un recalage</button>}
          {perms.write && <button className="btn-primary" onClick={newTask}><Plus size={16} /> Tâche</button>}</>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "gantt", label: "Diagramme de Gantt" }, { id: "meteo", label: "Météo et propositions" }, { id: "liste", label: "Liste des tâches" }]} />
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : data && tab === "gantt" && (
        <Card pad={false} title=" ">
          {!data.tasks.length ? <Empty title="Aucune tâche">Ajoutez les tâches du chantier : durées, dépendances, responsables et entreprises.</Empty>
            : <Gantt sched={data} onEdit={setEdit} onMove={move} canEdit={perms.write} />}
          {data.cycles?.length > 0 && <div className="p-4"><Notice tone="danger">Dépendances circulaires détectées : corrigez les liens entre tâches.</Notice></div>}
        </Card>
      )}
      {data && tab === "meteo" && <WeatherPanel projectId={projectId} onChanged={reload} />}
      {data && tab === "liste" && (
        <Card pad={false}><div className="overflow-x-auto"><table className="table">
          <thead><tr><th>Tâche</th><th>Activité</th><th>Début</th><th>Fin</th><th>Durée</th><th>Avancement</th><th>État</th></tr></thead>
          <tbody>{[...data.tasks].sort((a: any, b: any) => a.start_date.localeCompare(b.start_date)).map((t: any) => (
            <tr key={t.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => setEdit(t)}>
              <td className="font-medium">{t.milestone && <Flag size={12} className="inline mr-1" />}{t.name}{t.kind === "todo" && <span className="chip bg-info/15 text-info ml-2">à faire</span>}</td>
              <td className="text-muted">{ACTIVITY_LABELS[t.activity]}</td><td>{dateFr(t.start_date)}</td><td>{dateFr(t.end_date)}</td><td>{t.duration_days} j</td>
              <td>{t.progress} % <span className="text-xs text-muted">(attendu {t.expected_progress} %)</span></td>
              <td>{t.late ? <span className="chip bg-warn/15 text-warn">En retard{t.late_days ? ` ${t.late_days} j` : ""}</span> : t.critical ? <span className="chip bg-danger/15 text-danger">Critique</span> : <span className="chip bg-ok/15 text-ok">Conforme</span>}
                {t.baseline_drift ? <span className="text-xs text-muted ml-1">({t.baseline_drift > 0 ? "+" : ""}{t.baseline_drift} j / réf.)</span> : null}</td>
            </tr>))}</tbody></table></div></Card>
      )}
      {todos.length > 0 && tab === "gantt" && <div className="mt-4"><Card title="Tâches à faire (hors Gantt)"><ul className="text-sm space-y-1">{todos.map((t: any) => <li key={t.id} className="cursor-pointer hover:text-sage" onClick={() => setEdit(t)}>• {t.name} – {dateFr(t.start_date)} {t.late && <span className="text-warn">(en retard)</span>}</li>)}</ul></Card></div>}
      {edit && <TaskModal task={edit} tasks={data?.tasks || []} projectId={projectId} onClose={() => setEdit(null)} onSaved={reload} />}
    </div>
  );
}
