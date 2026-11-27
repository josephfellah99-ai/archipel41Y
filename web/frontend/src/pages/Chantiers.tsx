import { HardHat, AlertTriangle, CalendarDays, GanttChartSquare, Clock } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi, useApp } from "../lib/app";
import { dateFr, dateTimeFr, STATUS_PROJECT } from "../lib/format";
import { Card, Empty, ErrorBox, PageHeader, Progress, Spinner } from "../components/ui";

/** Vue d'ensemble des chantiers en cours : ce qui demande une action sur le terrain. */
export default function Chantiers() {
  const [all, setAll] = useState(false);
  const { data, loading, error } = useApi<any[]>(`/api/chantiers${all ? "?all=true" : ""}`);
  const { setProjectId } = useApp();
  const nav = useNavigate();
  const open = (id: string, to: string) => { setProjectId(id); nav(to); };
  return (
    <div>
      <PageHeader title="Chantiers" icon={<HardHat size={22} />} subtitle="Avancement, incidents ouverts, tâches en retard et prochaines visites de chaque chantier."
        actions={<label className="text-sm flex items-center gap-2"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Inclure les projets en études</label>} />
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : !data?.length ? (
        <Empty title="Aucun chantier en cours" icon={<HardHat size={18} />}>Un projet apparaît ici lorsque son statut est « Chantier » ou « Réception » (fiche projet).</Empty>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{data.map((c) => (
          <Card key={c.id} className={c.incidents_graves ? "ring-1 ring-danger/40" : ""}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><Link to={`/projets/${c.id}`} className="font-semibold hover:text-sage">{c.code} – {c.name}</Link>
                <div className="text-xs text-muted">{c.city || "—"} · {STATUS_PROJECT[c.status]} · phase {c.current_phase || "—"}</div></div>
              <span className="text-lg font-semibold tabular-nums">{c.progress} %</span>
            </div>
            <div className="mt-2"><Progress value={c.progress} /></div>
            <div className="grid grid-cols-3 gap-2 mt-4 text-center">
              <button onClick={() => open(c.id, `/projets/${c.id}`)} className={`rounded-lg p-2 ${c.incidents ? "bg-danger/10 text-danger" : "bg-sunken text-muted"}`}>
                <div className="text-lg font-semibold">{c.incidents}</div><div className="text-[11px] flex items-center justify-center gap-1"><AlertTriangle size={11} /> incident(s)</div></button>
              <button onClick={() => open(c.id, "/planning")} className={`rounded-lg p-2 ${c.late_count ? "bg-warn/10 text-warn" : "bg-sunken text-muted"}`}>
                <div className="text-lg font-semibold">{c.late_count}</div><div className="text-[11px] flex items-center justify-center gap-1"><Clock size={11} /> en retard</div></button>
              <button onClick={() => open(c.id, "/planning")} className="rounded-lg p-2 bg-sunken text-muted">
                <div className="text-lg font-semibold text-ink">{c.tasks}</div><div className="text-[11px] flex items-center justify-center gap-1"><GanttChartSquare size={11} /> tâches</div></button>
            </div>
            {c.late.length > 0 && <div className="mt-3 text-xs"><div className="text-muted mb-1">Tâches en retard</div>
              <ul className="space-y-0.5">{c.late.map((t: any, i: number) => <li key={i} className="text-warn">· {t.name} (début {dateFr(t.start_date)})</li>)}</ul></div>}
            {c.upcoming.length > 0 && <div className="mt-3 text-xs"><div className="text-muted mb-1">Prochaines tâches</div>
              <ul className="space-y-0.5">{c.upcoming.map((t: any, i: number) => <li key={i}>· {t.name} — {dateFr(t.start_date)}</li>)}</ul></div>}
            <div className="mt-3 pt-3 border-t border-line text-xs flex items-center gap-1.5 text-muted"><CalendarDays size={12} />
              {c.next_event ? <span>Prochain rendez-vous : <b className="text-ink font-medium">{c.next_event.title}</b> · {dateTimeFr(c.next_event.start)}</span> : "Aucun rendez-vous planifié"}</div>
          </Card>))}</div>
      )}
    </div>
  );
}
