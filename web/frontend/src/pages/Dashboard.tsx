import { AlertTriangle, CalendarDays, CloudRain, FileSpreadsheet, FolderKanban, HardHat, ListTodo, Sparkles, Wind } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr, eur, EVENT_COLORS, STATUS_PROJECT, timeFr } from "../lib/format";
import { Card, Empty, ErrorBox, Markdown, PageHeader, Progress, Select, Spinner, Stat } from "../components/ui";

const ACTIONS: Record<string, string> = { create: "a créé", update: "a modifié", delete: "a supprimé", validate: "a validé", new_version: "a ajouté une version de" };
const ENTITIES: Record<string, string> = {
  projects: "le projet", quotes: "le devis", quote_lines: "une ligne de devis", tasks: "la tâche", events: "le rendez-vous", documents: "le document",
  clients: "le client", companies: "l'entreprise", finance_entries: "l'écriture", lots: "le lot", incidents: "l'incident", comparisons: "le comparatif",
  document_versions: "la version", dpgf_items: "une ligne DPGF", proposals: "la proposition", budget_lines: "la ligne budgétaire", reports: "le rapport",
  parcel_analyses: "l'analyse urbanistique", users: "l'utilisateur", conversations: "la conversation", cctp_requirements: "une exigence CCTP",
};

function Weather() {
  const { data, loading } = useApi<any[]>("/api/dashboard/weather");
  if (loading) return <Spinner />;
  if (!data?.length) return <Empty title="Aucun chantier en cours">La météo s'affiche pour les projets au statut « Chantier ».</Empty>;
  return (
    <div className="space-y-3">
      {data.map((w) => (
        <div key={w.project_id}>
          <div className="text-xs text-muted mb-1">{w.code} – {w.name}{w.simulated && <span className="chip bg-warn/15 text-warn ml-2">simulée</span>}</div>
          {w.error ? <div className="text-sm text-warn">{w.error}</div> : (
            <div className="grid grid-cols-3 gap-2">
              {w.days.map((d: any, i: number) => (
                <div key={d.date} className="rounded-lg bg-sunken px-2.5 py-2">
                  <div className="text-[11px] text-muted">{i === 0 ? "Aujourd'hui" : i === 1 ? "Demain" : dateFr(d.date)}</div>
                  <div className="text-sm font-medium">{Math.round(d.tmin)}° / {Math.round(d.tmax)}°</div>
                  <div className="text-[11px] text-muted truncate">{d.label}</div>
                  <div className="flex gap-2 text-[11px] text-muted mt-0.5"><span className="flex items-center gap-0.5"><CloudRain size={11} />{d.rain} mm</span><span className="flex items-center gap-0.5"><Wind size={11} />{Math.round(d.gust)}</span></div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function DailySummary() {
  const [s, setS] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try { setS(await api.get("/api/dashboard/daily-summary")); } catch { /* ignoré */ } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);
  return (
    <Card title={<span className="flex items-center gap-2"><Sparkles size={15} className="text-sage" /> Synthèse du jour</span>}
      actions={<button className="btn-ghost text-xs px-2 py-1" onClick={load} disabled={busy}>Actualiser</button>}>
      {busy && !s ? <Spinner label="Analyse de la journée…" /> : s ? (
        <>
          <Markdown text={s.summary} />
          <div className="text-[11px] text-muted mt-2">{s.source === "ia" ? "Rédigée par l'assistant IA à partir des données de l'agence." : "Synthèse automatique (moteur de règles – aucun fournisseur d'IA configuré)."}</div>
        </>
      ) : null}
    </Card>
  );
}

export default function Dashboard() {
  const { user, projectId, projects } = useApp();
  const users = useApi<any[]>("/api/users");
  const [period, setPeriod] = useState("30");
  const [pid, setPid] = useState<string>(projectId || "");
  const [uid, setUid] = useState("");
  useEffect(() => { setPid(projectId || ""); }, [projectId]);
  const q = new URLSearchParams({ period, ...(pid ? { project_id: pid } : {}), ...(uid ? { user_id: uid } : {}) });
  const { data, error, loading } = useApi<any>(`/api/dashboard?${q}`);
  const hello = new Date().getHours() < 18 ? "Bonjour" : "Bonsoir";
  return (
    <div>
      <PageHeader title={`${hello} ${user?.full_name.split(" ")[0]}`}
        subtitle={new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        actions={<>
          <Select className="h-9 py-1 w-40" value={period} onChange={setPeriod} aria-label="Période"
            options={[{ value: "7", label: "7 prochains jours" }, { value: "30", label: "30 jours" }, { value: "90", label: "90 jours" }]} />
          <Select className="h-9 py-1 w-48" value={pid} onChange={setPid} placeholder="Tous les projets" aria-label="Projet"
            options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} />
          <Select className="h-9 py-1 w-44" value={uid} onChange={setUid} placeholder="Tous les collaborateurs" aria-label="Collaborateur"
            options={(users.data || []).map((u) => ({ value: u.id, label: u.full_name }))} />
        </>} />
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
            <Stat label="Projets actifs" value={data.kpis.projets_actifs} icon={<FolderKanban size={18} />} />
            <Stat label="Chantiers en cours" value={data.kpis.chantiers} icon={<HardHat size={18} />} tone="sage" />
            <Stat label="Devis à vérifier" value={data.kpis.devis_en_attente} icon={<FileSpreadsheet size={18} />} tone="info" />
            <Stat label="Rendez-vous" value={data.kpis.rendez_vous} hint={`sur ${period} jours`} icon={<CalendarDays size={18} />} tone="forest" />
            <Stat label="Tâches prioritaires" value={data.kpis.taches_prioritaires} icon={<ListTodo size={18} />} tone="warn" />
            <Stat label="Alertes" value={data.kpis.alertes} icon={<AlertTriangle size={18} />} tone="danger" />
          </div>
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <DailySummary />
              <Card title="Alertes" actions={<span className="text-xs text-muted">{data.alerts.length}</span>}>
                {data.alerts.length === 0 ? <Empty title="Aucune alerte">Tout est sous contrôle.</Empty> : (
                  <ul className="divide-y divide-line">
                    {data.alerts.slice(0, 10).map((a: any, i: number) => (
                      <li key={i} className="py-2 flex items-start gap-3 text-sm">
                        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.level === "haute" ? "bg-danger" : a.level === "moyenne" ? "bg-warn" : "bg-info"}`} />
                        <span className="flex-1">{a.message}</span>
                        {a.project && <span className="chip bg-sunken text-muted">{a.project}</span>}
                        <span className="chip bg-sunken text-muted hidden sm:inline-flex">{a.module}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title="Projets actifs" actions={<Link to="/projets" className="text-xs text-sage">Tous les projets</Link>}>
                <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {data.projects.map((p: any) => (
                    <Link key={p.id} to={`/projets/${p.id}`} className="rounded-lg border border-line p-3 hover:border-sage transition">
                      <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: p.color || "#718578" }} />
                        <span className="text-xs text-muted">{p.code}</span><span className="chip bg-sunken text-muted ml-auto">{STATUS_PROJECT[p.status]}</span></div>
                      <div className="text-sm font-medium mt-1.5 line-clamp-2">{p.name}</div>
                      <div className="text-xs text-muted mt-1">{p.city || "—"} · phase {p.current_phase || "—"}</div>
                      <div className="mt-2"><Progress value={p.progress} /></div>
                    </Link>
                  ))}
                </div>
              </Card>
              <Card title="Budgets (HT)">
                <div className="overflow-x-auto"><table className="table">
                  <thead><tr><th>Projet</th><th className="text-right">Budget actualisé</th><th className="text-right">Engagé</th><th className="text-right">Facturé</th><th className="text-right">Écart</th></tr></thead>
                  <tbody>{data.budgets.map((b: any) => (
                    <tr key={b.project_id}><td>{b.code} – {b.name}</td><td className="text-right tabular-nums">{eur(b.budget, 0)}</td>
                      <td className="text-right tabular-nums">{eur(b.engage, 0)}</td><td className="text-right tabular-nums">{eur(b.facture, 0)}</td>
                      <td className={`text-right tabular-nums ${b.ecart_pct > 0 ? "text-danger" : "text-muted"}`}>{b.ecart_pct === null ? "—" : `${b.ecart_pct > 0 ? "+" : ""}${b.ecart_pct} %`}</td></tr>
                  ))}</tbody>
                </table></div>
              </Card>
            </div>
            <div className="space-y-6">
              <Card title="Météo des chantiers"><Weather /></Card>
              <Card title="Prochains rendez-vous" actions={<Link to="/agenda" className="text-xs text-sage">Agenda</Link>}>
                {data.events.length === 0 ? <Empty title="Aucun rendez-vous" /> : (
                  <ul className="space-y-2.5">{data.events.slice(0, 7).map((e: any) => (
                    <li key={e.id} className="flex gap-3 text-sm">
                      <div className="w-1 rounded-full" style={{ background: EVENT_COLORS[e.kind] }} />
                      <div className="min-w-0"><div className="font-medium truncate">{e.title}</div>
                        <div className="text-xs text-muted">{dateFr(e.start)} · {timeFr(e.start)}–{timeFr(e.end)}{e.location ? ` · ${e.location}` : ""}</div></div>
                    </li>))}</ul>
                )}
              </Card>
              <Card title="Tâches prioritaires" actions={<Link to="/planning" className="text-xs text-sage">Planning</Link>}>
                {data.tasks.length === 0 ? <Empty title="Aucune tâche prioritaire" /> : (
                  <ul className="space-y-2">{data.tasks.slice(0, 8).map((t: any) => (
                    <li key={t.id} className="text-sm flex items-start gap-2">
                      <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${t.late ? "bg-danger" : t.priority === "haute" ? "bg-warn" : "bg-sage"}`} />
                      <div className="min-w-0"><div className="truncate">{t.name}</div>
                        <div className="text-xs text-muted">{t.project} · {dateFr(t.start_date)}{t.late ? " · en retard" : ""} · {t.progress} %</div></div>
                    </li>))}</ul>
                )}
              </Card>
              <Card title="Devis en attente" actions={<Link to="/devis" className="text-xs text-sage">Devis</Link>}>
                {data.quotes.length === 0 ? <Empty title="Aucun devis à vérifier" /> : (
                  <ul className="space-y-2">{data.quotes.map((q: any) => (
                    <li key={q.id}><Link to={`/devis/${q.id}`} className="text-sm flex justify-between gap-2 hover:text-sage">
                      <span className="truncate">{q.company || "Entreprise ?"} {q.reference ? `· ${q.reference}` : ""}</span>
                      <span className="tabular-nums text-muted">{eur(q.total_ht, 0)}</span></Link>
                      {q.anomalies > 0 && <div className="text-xs text-warn">{q.anomalies} anomalie(s) détectée(s)</div>}</li>))}</ul>
                )}
              </Card>
              <Card title="Activité récente">
                <ul className="space-y-2">{data.activity.map((a: any, i: number) => (
                  <li key={i} className="text-xs"><span className="font-medium">{a.user}</span> {ACTIONS[a.action] || a.action} {ENTITIES[a.entity] || ""} <span className="text-ink/80">{(a.summary || "").split(" : ")[0]}</span>
                    <div className="text-muted">{dateFr(a.at)} {timeFr(a.at)}</div></li>))}</ul>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
