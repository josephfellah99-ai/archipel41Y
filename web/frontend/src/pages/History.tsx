import { History as HistoryIcon, Download, ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, LogIn, Bug, Search, ChevronRight, ChevronDown } from "lucide-react";
import { Fragment, useState } from "react";
import { api, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateTimeFr } from "../lib/format";
import { AsyncButton, Card, Empty, ErrorBox, Field, Modal, Notice, NumberInput, PageHeader, Select, Spinner, Stat, Tabs } from "../components/ui";

const SEV: Record<string, { label: string; cls: string }> = {
  info: { label: "Information", cls: "bg-info/15 text-info" },
  avertissement: { label: "Avertissement", cls: "bg-warn/15 text-warn" },
  erreur: { label: "Erreur", cls: "bg-danger/15 text-danger" },
  critique: { label: "Critique", cls: "bg-danger text-white" },
};
const SRC: Record<string, string> = {
  api: "API", sync: "Synchronisation", import: "Importation", validation: "Validation de formulaire", calcul: "Calcul", chargement: "Chargement",
  base: "Base de données", python: "Moteur (Python)", javascript: "Interface (JavaScript)", document: "Génération de document", agenda: "Agenda externe",
};
const KIND: Record<string, string> = { admin: "Administrateur", collaborateur: "Collaborateur", invite: "Invité", deconnexion: "Déconnexion" };

function qs(o: Record<string, any>) {
  return new URLSearchParams(Object.entries(o).filter(([, v]) => v !== "" && v !== null && v !== undefined).map(([k, v]) => [k, String(v)])).toString();
}

function Pager({ page, total, limit, onPage }: { page: number; total: number; limit: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="flex items-center justify-between px-5 py-3 border-t border-line text-xs text-muted">
      <span>{total} entrée(s)</span>
      <span className="flex items-center gap-2"><button className="btn-secondary py-1" disabled={page <= 1} onClick={() => onPage(page - 1)}>Précédent</button>
        page {page} / {pages}<button className="btn-secondary py-1" disabled={page >= pages} onClick={() => onPage(page + 1)}>Suivant</button></span>
    </div>
  );
}

function Changes({ changes }: { changes: any }) {
  if (!changes) return <div className="text-xs text-muted">Aucun détail de valeur pour cette opération.</div>;
  const show = (v: any) => (v === null || v === undefined || v === "" ? <span className="text-muted">—</span> : typeof v === "object" ? <code className="text-[11px] break-all">{JSON.stringify(v).slice(0, 300)}</code> : String(v));
  return (
    <table className="table text-xs"><thead><tr><th>Champ</th><th>Ancienne valeur</th><th>Nouvelle valeur</th></tr></thead>
      <tbody>{Object.entries(changes).map(([k, v]: any) => (
        <tr key={k}><td className="font-medium">{k}</td><td className="text-danger/90">{show(v?.avant)}</td><td className="text-ok">{show(v?.apres ?? v)}</td></tr>))}</tbody></table>
  );
}

function Activity() {
  const { projects, toastError } = useApp();
  const users = useApi<any[]>("/api/users");
  const [f, setF] = useState({ user_id: "", project_id: "", module: "", action: "", date_from: "", date_to: "", q: "" });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const query = qs({ ...f, page, limit: 50 });
  const { data, loading, error } = useApi<any>(`/api/history/activity?${query}`);
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPage(1); };
  const exp = async (fmt: string) => { try { await download(`/api/history/activity/export?${qs({ ...f, fmt })}`); } catch (e) { toastError(e); } };
  return (
    <Card pad={false} title="Journal d'activité" actions={<><button className="btn-secondary py-1" onClick={() => exp("csv")}><Download size={14} /> CSV</button><button className="btn-secondary py-1" onClick={() => exp("pdf")}><Download size={14} /> PDF</button></>}>
      <div className="px-5 pb-3 grid sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-2">
        <Select value={f.user_id} onChange={(v) => set("user_id", v)} placeholder="Tous les utilisateurs" options={(users.data || []).map((u) => ({ value: u.id, label: u.full_name }))} aria-label="Utilisateur" />
        <Select value={f.project_id} onChange={(v) => set("project_id", v)} placeholder="Tous les projets" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} aria-label="Projet" />
        <Select value={f.module} onChange={(v) => set("module", v)} placeholder="Tous les modules" options={Object.entries(data?.filters?.modules || {}).map(([v, l]: any) => ({ value: v, label: l }))} aria-label="Module" />
        <Select value={f.action} onChange={(v) => set("action", v)} placeholder="Toutes les opérations" options={Object.entries(data?.filters?.actions || {}).map(([v, l]: any) => ({ value: v, label: l }))} aria-label="Opération" />
        <input className="input" type="date" value={f.date_from} onChange={(e) => set("date_from", e.target.value)} aria-label="Du" title="Du" />
        <input className="input" type="date" value={f.date_to} onChange={(e) => set("date_to", e.target.value)} aria-label="Au" title="Au" />
        <div className="relative"><Search size={14} className="absolute left-3 top-3 text-muted" /><input className="input pl-8" placeholder="Rechercher…" value={f.q} onChange={(e) => set("q", e.target.value)} aria-label="Recherche" /></div>
      </div>
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : !data?.items.length ? <Empty title="Aucune opération ne correspond aux filtres" /> : (
        <div className="overflow-x-auto"><table className="table text-sm">
          <thead><tr><th className="w-6" /><th>Date et heure</th><th>Auteur</th><th>Module</th><th>Projet</th><th>Opération</th><th>Élément</th><th>Résultat</th></tr></thead>
          <tbody>{data.items.map((a: any) => (
            <Fragment key={a.id}>
              <tr className="hover:bg-sunken/50 cursor-pointer" onClick={() => setOpen(open === a.id ? null : a.id)}>
                <td>{a.changes ? (open === a.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}</td>
                <td className="whitespace-nowrap tabular-nums text-muted">{dateTimeFr(a.at)}</td><td>{a.user}</td><td className="text-muted">{a.module_label}</td>
                <td className="text-muted max-w-[180px] truncate">{a.project || "—"}</td><td>{a.action_label}</td><td className="max-w-[320px] truncate">{a.summary}</td>
                <td>{a.result === "succes" ? <span className="chip bg-ok/15 text-ok">réussi</span> : <span className="chip bg-danger/15 text-danger">{a.result}</span>}</td>
              </tr>
              {open === a.id && <tr><td /><td colSpan={7} className="bg-sunken/40"><Changes changes={a.changes} /></td></tr>}
            </Fragment>))}</tbody></table></div>)}
      {data && <Pager page={page} total={data.total} limit={50} onPage={setPage} />}
    </Card>
  );
}

function Connections() {
  const { toastError } = useApp();
  const users = useApi<any[]>("/api/users");
  const [f, setF] = useState({ user_id: "", kind: "", success: "", date_from: "", date_to: "", q: "" });
  const [page, setPage] = useState(1);
  const { data, loading } = useApi<any>(`/api/history/connections?${qs({ ...f, page, limit: 50 })}`);
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPage(1); };
  return (
    <Card pad={false} title="Historique des connexions" actions={<button className="btn-secondary py-1" onClick={async () => { try { await download(`/api/history/connections/export?${qs({ ...f, fmt: "csv" })}`); } catch (e) { toastError(e); } }}><Download size={14} /> CSV</button>}>
      <div className="px-5 pb-3 grid sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <Select value={f.user_id} onChange={(v) => set("user_id", v)} placeholder="Tous les utilisateurs" options={(users.data || []).map((u) => ({ value: u.id, label: u.full_name }))} aria-label="Utilisateur" />
        <Select value={f.kind} onChange={(v) => set("kind", v)} placeholder="Tous les types" options={Object.entries(KIND).map(([v, l]) => ({ value: v, label: l }))} aria-label="Type" />
        <Select value={f.success} onChange={(v) => set("success", v)} placeholder="Réussies et échouées" options={[{ value: "true", label: "Réussies" }, { value: "false", label: "Échouées" }]} aria-label="Résultat" />
        <input className="input" type="date" value={f.date_from} onChange={(e) => set("date_from", e.target.value)} aria-label="Du" />
        <input className="input" type="date" value={f.date_to} onChange={(e) => set("date_to", e.target.value)} aria-label="Au" />
        <input className="input" placeholder="E-mail, adresse IP…" value={f.q} onChange={(e) => set("q", e.target.value)} aria-label="Recherche" />
      </div>
      {loading && !data ? <Spinner /> : !data?.items.length ? <Empty title="Aucune connexion" icon={<LogIn size={18} />} /> : (
        <div className="overflow-x-auto"><table className="table text-sm">
          <thead><tr><th>Date et heure</th><th>Utilisateur / identifiant</th><th>Type</th><th>Résultat</th><th>Appareil</th><th>Adresse IP</th><th>Sécurité</th></tr></thead>
          <tbody>{data.items.map((c: any) => (
            <tr key={c.id}><td className="whitespace-nowrap tabular-nums text-muted">{dateTimeFr(c.at)}</td><td>{c.user || c.identity || "—"}{c.user && c.identity && <div className="text-xs text-muted">{c.identity}</div>}</td>
              <td>{KIND[c.kind] || c.kind}</td><td>{c.success ? <span className="chip bg-ok/15 text-ok">réussie</span> : <span className="chip bg-danger/15 text-danger" title={c.reason}>échouée</span>}{!c.success && c.reason && <div className="text-xs text-muted">{c.reason}</div>}</td>
              <td className="text-muted">{c.device}</td><td className="text-muted tabular-nums">{c.ip}</td><td>{c.security_event && <span className="chip bg-warn/15 text-warn">{c.security_event.replace(/_/g, " ")}</span>}</td></tr>))}</tbody></table></div>)}
      {data && <Pager page={page} total={data.total} limit={50} onPage={setPage} />}
    </Card>
  );
}

function ErrorDetail({ ref_, onClose, onResolved }: { ref_: string; onClose: () => void; onResolved: () => void }) {
  const { toastError } = useApp();
  const { data, loading } = useApi<any>(`/api/history/errors/${ref_}`);
  return (
    <Modal open onClose={onClose} title={`Erreur ${ref_}`} wide dismissable footer={data && !data.resolved ? <AsyncButton onClick={async () => { try { await api.call("POST", `/api/history/errors/${ref_}/resolve`); onResolved(); onClose(); } catch (e) { toastError(e); } }}><CheckCircle2 size={15} /> Marquer comme résolue</AsyncButton> : undefined}>
      {loading || !data ? <Spinner /> : (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2"><span className={`chip ${SEV[data.severity]?.cls}`}>{SEV[data.severity]?.label}</span><span className="chip bg-sunken">{SRC[data.source] || data.source}</span>
            {data.module_label && <span className="chip bg-sunken">{data.module_label}</span>}<span className="text-muted">{dateTimeFr(data.at)}{data.user ? ` · ${data.user}` : ""}</span></div>
          {data.explanation && <Notice tone="info"><b>En clair :</b> {data.explanation}</Notice>}
          <div><div className="label">Message technique</div><pre className="text-xs bg-sunken rounded-lg p-3 whitespace-pre-wrap break-all">{data.message}</pre></div>
          {data.path && <div><div className="label">Contexte</div><div className="text-xs">{data.path}</div></div>}
          {data.context && Object.keys(data.context).length > 0 && <details><summary className="cursor-pointer text-xs text-muted">Détails techniques</summary><pre className="text-[11px] bg-sunken rounded-lg p-3 whitespace-pre-wrap break-all max-h-72 overflow-auto">{JSON.stringify(data.context, null, 2)}</pre></details>}
          <div><div className="label">Opérations effectuées juste avant (même utilisateur, 10 minutes)</div>
            {!data.related_activity.length ? <div className="text-xs text-muted">Aucune.</div> : <ul className="text-xs space-y-1">{data.related_activity.map((a: any) => <li key={a.id}><span className="text-muted">{dateTimeFr(a.at)}</span> — {a.user} · {a.action_label} · {a.summary}</li>)}</ul>}</div>
        </div>)}
    </Modal>
  );
}

function Diagnostic() {
  const { toastError } = useApp();
  const d = useApi<any>("/api/history/diagnostic");
  const [f, setF] = useState({ severity: "", source: "", resolved: "false", q: "" });
  const [page, setPage] = useState(1);
  const errs = useApi<any>(`/api/history/errors?${qs({ ...f, page, limit: 30 })}`);
  const [sel, setSel] = useState<string | null>(null);
  const [refq, setRefq] = useState("");
  if (d.loading && !d.data) return <Spinner />;
  if (!d.data) return <ErrorBox error={d.error} />;
  const x = d.data;
  const max = Math.max(1, ...x.daily.map((v: any) => v.n));
  return (
    <div className="space-y-6">
      {x.alerts.length > 0 && <div className="space-y-2">{x.alerts.map((a: any, i: number) => <Notice key={i} tone={a.tone}><AlertTriangle size={14} className="inline mr-1" />{a.message}</Notice>)}</div>}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat label="Erreurs (24 h)" value={x.errors_24h} />
        <Stat label="Erreurs (7 jours)" value={x.errors_7d} hint={`${x.unresolved} non résolue(s)`} />
        <Stat label="Critiques (7 jours)" value={x.by_severity.critique} tone="danger" />
        <Stat label="Connexions échouées (7 j)" value={x.failed_logins_7d} hint={`${x.connections_7d} connexion(s)`} />
        <Stat label="Espace disque libre" value={x.disk ? `${x.disk.libre_go} Go` : "—"} hint={x.disk ? `${x.disk.libre_pct} %` : undefined} />
        <Stat label="Journal d'activité" value={x.integrity.intact ? "Intègre" : "Anomalies"} hint={`${x.integrity.entries} entrée(s) vérifiée(s)`} tone={x.integrity.intact ? "ok" : "danger"} />
      </div>
      <div className="grid lg:grid-cols-3 gap-6">
        <Card title="Erreurs sur 7 jours"><div className="flex items-end gap-2 h-28">{x.daily.map((v: any) => (
          <div key={v.date} className="flex-1 flex flex-col items-center gap-1"><div className="w-full bg-danger/60 rounded-t" style={{ height: `${(v.n / max) * 90}%`, minHeight: v.n ? 3 : 0 }} title={`${v.n} erreur(s)`} />
            <span className="text-[10px] text-muted">{new Date(v.date).toLocaleDateString("fr-FR", { weekday: "short" })}</span></div>))}</div></Card>
        <Card title="Par gravité et par origine"><ul className="text-sm space-y-1">{Object.entries(x.by_severity).map(([k, n]: any) => <li key={k} className="flex justify-between"><span className={`chip ${SEV[k].cls}`}>{SEV[k].label}</span><b>{n}</b></li>)}</ul>
          <ul className="text-xs text-muted mt-3 space-y-0.5">{Object.entries(x.by_source).map(([k, n]: any) => <li key={k} className="flex justify-between"><span>{SRC[k] || k}</span><span>{n}</span></li>)}</ul></Card>
        <Card title="Système"><ul className="text-sm space-y-1.5">
          <li className="flex justify-between"><span className="text-muted">Base de données</span>{x.database}</li>
          <li className="flex justify-between"><span className="text-muted">Dernière sauvegarde</span>{x.last_backup_at ? dateTimeFr(x.last_backup_at) : "jamais"}</li>
          <li className="flex justify-between"><span className="text-muted">Synchronisation</span>{x.sync_configured ? (x.last_sync_at ? dateTimeFr(x.last_sync_at) : "jamais") : "non configurée"}</li>
          <li className="flex justify-between"><span className="text-muted">Modules les plus concernés</span><span className="text-right">{Object.keys(x.by_module).slice(0, 2).join(", ") || "—"}</span></li></ul></Card>
      </div>
      <Card pad={false} title="Journal technique des erreurs" actions={<><div className="flex gap-1"><input className="input py-1 w-36" placeholder="Référence E-…" value={refq} onChange={(e) => setRefq(e.target.value.toUpperCase())} aria-label="Référence d'erreur" />
        <button className="btn-secondary py-1" disabled={!refq} onClick={() => setSel(refq.trim())}>Ouvrir</button></div>
        <button className="btn-secondary py-1" onClick={async () => { try { await download(`/api/history/errors/export?${qs({ ...f, fmt: "csv" })}`); } catch (e) { toastError(e); } }}><Download size={14} /> CSV</button></>}>
        <div className="px-5 pb-3 grid sm:grid-cols-4 gap-2">
          <Select value={f.severity} onChange={(v) => { setF({ ...f, severity: v }); setPage(1); }} placeholder="Toutes gravités" options={Object.entries(SEV).map(([v, s]) => ({ value: v, label: s.label }))} aria-label="Gravité" />
          <Select value={f.source} onChange={(v) => { setF({ ...f, source: v }); setPage(1); }} placeholder="Toutes origines" options={Object.entries(SRC).map(([v, l]) => ({ value: v, label: l }))} aria-label="Origine" />
          <Select value={f.resolved} onChange={(v) => { setF({ ...f, resolved: v }); setPage(1); }} placeholder="Résolues et non résolues" options={[{ value: "false", label: "Non résolues" }, { value: "true", label: "Résolues" }]} aria-label="État" />
          <input className="input" placeholder="Rechercher dans les messages…" value={f.q} onChange={(e) => { setF({ ...f, q: e.target.value }); setPage(1); }} aria-label="Recherche" />
        </div>
        {!errs.data?.items.length ? <Empty title="Aucune erreur" icon={<Bug size={18} />}>Aucune erreur ne correspond aux filtres.</Empty> : (
          <div className="overflow-x-auto"><table className="table text-sm">
            <thead><tr><th>Référence</th><th>Date et heure</th><th>Gravité</th><th>Origine</th><th>Module</th><th>Explication</th></tr></thead>
            <tbody>{errs.data.items.map((e: any) => (
              <tr key={e.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => setSel(e.ref)}>
                <td className="font-mono text-xs">{e.ref}</td><td className="whitespace-nowrap tabular-nums text-muted">{dateTimeFr(e.at)}</td>
                <td><span className={`chip ${SEV[e.severity]?.cls}`}>{SEV[e.severity]?.label}</span></td><td>{SRC[e.source] || e.source}</td><td className="text-muted">{e.module_label || "—"}</td>
                <td className="max-w-[380px] truncate" title={e.message}>{e.explanation || e.message}</td></tr>))}</tbody></table></div>)}
        {errs.data && <Pager page={page} total={errs.data.total} limit={30} onPage={setPage} />}
      </Card>
      {sel && <ErrorDetail ref_={sel} onClose={() => setSel(null)} onResolved={() => { errs.reload(); d.reload(); }} />}
    </div>
  );
}

function Integrity() {
  const { toast, toastError } = useApp();
  const d = useApi<any>("/api/history/diagnostic");
  const integ = useApi<any>("/api/history/integrity");
  const [ret, setRet] = useState<any>(null);
  const r = ret || d.data?.retention;
  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card title="Intégrité du journal d'activité" actions={<button className="btn-secondary py-1" onClick={() => integ.reload()}>Vérifier maintenant</button>}>
        {!integ.data ? <Spinner /> : integ.data.intact ? (
          <div className="flex gap-3"><ShieldCheck className="text-ok shrink-0" /><div className="text-sm"><b>Journal intègre</b> : {integ.data.entries} entrée(s) vérifiée(s).
            <p className="text-muted mt-1">Chaque entrée contient l'empreinte de la précédente : toute modification ou suppression hors de l'application est détectée. La modification directe en base est en outre bloquée par la base de données.</p></div></div>
        ) : (
          <div className="flex gap-3"><ShieldAlert className="text-danger shrink-0" /><div className="text-sm"><b>{integ.data.anomalies.length} anomalie(s) détectée(s)</b>
            <ul className="mt-2 space-y-1 text-xs">{integ.data.anomalies.map((a: any) => <li key={a.id}>{dateTimeFr(a.at)} — {a.probleme}</li>)}</ul></div></div>)}
      </Card>
      <Card title="Conservation des journaux">
        {!r ? <Spinner /> : (<>
          <div className="grid sm:grid-cols-3 gap-3">
            <Field label="Activité (jours)"><NumberInput integer min={90} max={3650} value={r.activity_days} onChange={(v) => setRet({ ...r, activity_days: v })} /></Field>
            <Field label="Connexions (jours)"><NumberInput integer min={30} max={3650} value={r.connections_days} onChange={(v) => setRet({ ...r, connections_days: v })} /></Field>
            <Field label="Erreurs (jours)"><NumberInput integer min={30} max={3650} value={r.errors_days} onChange={(v) => setRet({ ...r, errors_days: v })} /></Field>
          </div>
          <p className="text-xs text-muted mt-2">Les entrées plus anciennes sont supprimées lors de la purge (une entrée de journal la consigne). Aucun mot de passe, jeton ou secret n'est jamais enregistré dans les journaux.</p>
          <div className="flex gap-2 mt-3">
            <AsyncButton onClick={async () => { try { await api.call("PUT", "/api/history/retention", r); toast("Durées de conservation enregistrées."); d.reload(); } catch (e) { toastError(e); } }}>Enregistrer</AsyncButton>
            <AsyncButton className="btn-secondary" onClick={async () => { try { const x = await api.call("POST", "/api/history/purge"); toast(`Purge : ${x.activity} activité(s), ${x.connections} connexion(s), ${x.errors} erreur(s).`); integ.reload(); } catch (e) { toastError(e); } }}>Purger maintenant</AsyncButton>
          </div></>)}
      </Card>
    </div>
  );
}

export default function HistoryPage() {
  const { perms } = useApp();
  const [tab, setTab] = useState("activite");
  return (
    <div>
      <PageHeader title="Historique et activité" icon={<HistoryIcon size={22} />} subtitle="Qui a fait quoi, quand, sur quel projet — avec les valeurs avant et après. Diagnostic des erreurs pour les administrateurs." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "activite", label: "Activité" }, ...(perms.admin ? [{ id: "connexions", label: "Connexions" },
        { id: "diagnostic", label: "Erreurs et diagnostic" }, { id: "integrite", label: "Intégrité et conservation" }] : [])]} />
      {tab === "activite" && <Activity />}
      {tab === "connexions" && perms.admin && <Connections />}
      {tab === "diagnostic" && perms.admin && <Diagnostic />}
      {tab === "integrite" && perms.admin && <Integrity />}
    </div>
  );
}
