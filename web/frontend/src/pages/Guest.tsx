import { Download, Eye, FileText, LogOut, MapPin, Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { blobUrl, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { bytes, dateFr, DOC_CATEGORIES, STATUS_PROJECT } from "../lib/format";
import { Card, Empty, ErrorBox, Modal, Progress, Spinner, Tabs } from "../components/ui";
import { Comments } from "../components/Comments";
import logo from "../logo.svg";

function Viewer({ doc, onClose }: { doc: any; onClose: () => void }) {
  const pages = useApi<any>(`/api/guest/documents/${doc.id}/pages`);
  const [imgs, setImgs] = useState<string[]>([]);
  const [single, setSingle] = useState<string | null>(null);
  const isImg = ["png", "jpg", "jpeg", "webp", "gif"].includes((doc.extension || "").toLowerCase());
  useEffect(() => {
    let urls: string[] = [];
    if (isImg) blobUrl(`/api/guest/documents/${doc.id}/file`).then((u) => { urls = [u]; setSingle(u); }).catch(() => {});
    else if (pages.data?.pages) {
      Promise.all(Array.from({ length: Math.min(pages.data.pages, 30) }, (_, i) => blobUrl(`/api/guest/documents/${doc.id}/page/${i + 1}`)))
        .then((u) => { urls = u; setImgs(u); }).catch(() => {});
    }
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [doc.id, pages.data, isImg]);
  return (
    <Modal open onClose={onClose} title={doc.name} wide dismissable>
      {isImg ? (single ? <img src={single} alt={doc.name} className="w-full" /> : <Spinner />)
        : pages.loading ? <Spinner /> : !pages.data?.pages ? <Empty title="Aperçu indisponible">Ce format ne peut pas être affiché ici.</Empty>
        : <div className="space-y-3">{imgs.map((u, i) => <img key={i} src={u} alt={`Page ${i + 1}`} className="w-full border border-line" />)}{!imgs.length && <Spinner />}</div>}
    </Modal>
  );
}

function GuestProject({ id }: { id: string }) {
  const { guest, toastError } = useApp();
  const p = useApi<any>(guest?.modules.includes("fiche") ? `/api/guest/projects/${id}` : null);
  const docs = useApi<any[]>(guest?.modules.includes("documents") ? `/api/guest/projects/${id}/documents` : null);
  const plan = useApi<any[]>(guest?.modules.includes("planning") ? `/api/guest/projects/${id}/planning` : null);
  const [tab, setTab] = useState(guest?.modules.includes("fiche") ? "fiche" : "documents");
  const [view, setView] = useState<any>(null);
  const tabs = [
    ...(guest?.modules.includes("fiche") ? [{ id: "fiche", label: "Projet" }] : []),
    ...(guest?.modules.includes("documents") ? [{ id: "documents", label: `Documents${docs.data ? ` (${docs.data.length})` : ""}` }] : []),
    ...(guest?.modules.includes("planning") ? [{ id: "planning", label: "Planning" }] : []),
    ...(guest?.can_comment ? [{ id: "echanges", label: "Échanges avec l'agence" }] : []),
  ];
  return (
    <div>
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      {tab === "fiche" && (p.loading && !p.data ? <Spinner /> : p.data ? (
        <div className="grid lg:grid-cols-[1fr_320px] gap-6">
          <Card title={`${p.data.code} – ${p.data.name}`}>
            <div className="text-sm text-muted flex items-center gap-1.5"><MapPin size={14} />{[p.data.address, p.data.postal_code, p.data.city].filter(Boolean).join(" ") || "Adresse non communiquée"}</div>
            {p.data.description && <p className="text-sm mt-3 whitespace-pre-wrap">{p.data.description}</p>}
            <div className="grid sm:grid-cols-3 gap-3 mt-4 text-sm">
              <div><div className="text-xs text-muted">Statut</div>{STATUS_PROJECT[p.data.status]}</div>
              <div><div className="text-xs text-muted">Phase en cours</div>{p.data.current_phase || "—"}</div>
              <div><div className="text-xs text-muted">Surface</div>{p.data.surface_m2 ? `${p.data.surface_m2} m²` : "—"}</div>
            </div>
            <div className="mt-4"><div className="text-xs text-muted mb-1">Avancement global : {p.data.progress} %</div><Progress value={p.data.progress} /></div>
          </Card>
          <Card title="Phases de la mission">
            <ul className="space-y-2">{p.data.phases.map((ph: any) => (
              <li key={ph.code} className="text-sm"><div className="flex justify-between"><span><b>{ph.code}</b> {ph.label}</span><span className="text-xs text-muted">{ph.progress ?? 0} %</span></div>
                <Progress value={ph.progress ?? 0} /></li>))}</ul>
          </Card>
        </div>) : <ErrorBox error={p.error} />)}
      {tab === "documents" && (
        <Card pad={false}>{docs.loading && !docs.data ? <Spinner /> : !docs.data?.length ? <Empty title="Aucun document partagé pour le moment" /> : (
          <ul className="divide-y divide-line">{docs.data.map((d) => (
            <li key={d.id} className="px-5 py-3 flex items-center gap-3">
              <FileText size={18} className="text-sage shrink-0" />
              <div className="min-w-0 flex-1"><div className="text-sm font-medium truncate">{d.name}</div>
                <div className="text-xs text-muted">{DOC_CATEGORIES[d.category] || d.category} · {bytes(d.size)} · mis à jour le {dateFr(d.updated_at)}</div></div>
              <button className="btn-secondary py-1" onClick={() => setView(d)}><Eye size={14} /> Consulter</button>
              {guest?.can_download && <button className="btn-secondary py-1" onClick={async () => { try { await download(`/api/guest/documents/${d.id}/file?download=true`, d.name); } catch (e) { toastError(e); } }}><Download size={14} /></button>}
            </li>))}</ul>)}</Card>)}
      {tab === "planning" && (
        <Card pad={false}>{!plan.data?.length ? <Empty title="Aucune tâche planifiée" /> : (
          <table className="table"><thead><tr><th>Tâche</th><th>Début</th><th>Durée</th><th className="w-40">Avancement</th></tr></thead>
            <tbody>{plan.data.map((t) => <tr key={t.id}><td>{t.name}</td><td>{dateFr(t.start_date)}</td><td>{t.milestone ? "jalon" : `${t.duration_days} j`}</td>
              <td><div className="flex items-center gap-2"><Progress value={t.progress} /><span className="text-xs text-muted">{t.progress} %</span></div></td></tr>)}</tbody></table>)}</Card>)}
      {tab === "echanges" && <Card title="Échanges avec l'agence"><Comments entity="projects" entityId={id} guest canWrite={guest?.can_comment} /></Card>}
      {view && <Viewer doc={view} onClose={() => setView(null)} />}
    </div>
  );
}

export default function GuestApp() {
  const { guest, agency, user, logout } = useApp();
  const [pid, setPid] = useState<string | null>(guest?.projects[0]?.id || null);
  if (!guest) return null;
  return (
    <div className="min-h-full bg-bg">
      <header className="border-b border-line bg-surface">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-3">
          <img src={logo} alt="" className="h-8 w-8" />
          <div className="leading-tight min-w-0"><div className="text-sm font-semibold tracking-[0.18em] text-forest">ARCHIPEL41</div>
            <div className="text-[11px] text-muted truncate">{agency?.name} · espace invité</div></div>
          <div className="flex-1" />
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted"><Clock size={13} /> accès valable jusqu'au {new Date(guest.expires_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}</div>
          <span className="text-sm hidden md:inline">{user?.full_name}</span>
          <button className="btn-secondary h-8" onClick={logout}><LogOut size={14} /> Quitter</button>
        </div>
      </header>
      <div className="bg-sunken/70 text-xs text-center py-1.5 px-3 text-muted">Accès invité : consultation limitée aux éléments partagés par l'agence (« {guest.invitation} »). Vos consultations sont enregistrées.</div>
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {guest.projects.length > 1 && (
          <div className="flex flex-wrap gap-2 mb-5">{guest.projects.map((p) => (
            <button key={p.id} onClick={() => setPid(p.id)} className={pid === p.id ? "btn-primary" : "btn-secondary"}>{p.code} – {p.name}</button>))}</div>)}
        {pid ? <GuestProject key={pid} id={pid} /> : <Empty title="Aucun projet partagé">Le projet partagé n'est plus disponible.</Empty>}
      </main>
    </div>
  );
}
