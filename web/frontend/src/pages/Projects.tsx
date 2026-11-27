import { FolderKanban, Plus, Trash2, Save, AlertTriangle, Lock, ExternalLink } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr, eur, LOT_STATUS, STATUS_PROJECT, toNum } from "../lib/format";
import { AsyncButton, Card, Confirm, Empty, ErrorBox, Field, Modal, NumberInput, PageHeader, Progress, Select, Spinner, Tabs } from "../components/ui";
import { DocumentsTable } from "./Documents";

const emptyProject = { code: "", name: "", client_id: "", status: "etude", address: "", postal_code: "", city: "", program: "", description: "",
  budget_initial: "", surface_m2: "", start_date: "", end_date: "", confidential: false, fee_rate: "" };

function clean(o: any) {
  const out: any = {};
  for (const [k, v] of Object.entries(o)) out[k] = v === "" ? null : v;
  const labels: Record<string, string> = { budget_initial: "Budget travaux", surface_m2: "Surface", fee_rate: "Taux d'honoraires", latitude: "Latitude", longitude: "Longitude", progress: "Avancement" };
  for (const k of Object.keys(labels)) if (k in out) out[k] = toNum(out[k], labels[k]);
  if ("progress" in out && out.progress === null) out.progress = 0;
  return out;
}

export function ProjectForm({ value, onChange, clients }: { value: any; onChange: (v: any) => void; clients: any[] }) {
  const set = (k: string) => (e: any) => onChange({ ...value, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      <Field label="Code projet *"><input className="input" value={value.code} onChange={set("code")} placeholder="24-07" required /></Field>
      <Field label="Statut"><Select value={value.status} onChange={(v) => onChange({ ...value, status: v })} options={Object.entries(STATUS_PROJECT).map(([v, l]) => ({ value: v, label: l }))} /></Field>
      <Field label="Nom du projet *" className="sm:col-span-2"><input className="input" value={value.name} onChange={set("name")} required /></Field>
      <Field label="Maître d'ouvrage (client)" className="sm:col-span-2">
        <Select value={value.client_id} onChange={(v) => onChange({ ...value, client_id: v })} placeholder="— Aucun —" options={clients.map((c) => ({ value: c.id, label: c.name }))} /></Field>
      <Field label="Adresse du chantier" className="sm:col-span-2"><input className="input" value={value.address || ""} onChange={set("address")} /></Field>
      <Field label="Code postal"><input className="input" value={value.postal_code || ""} onChange={set("postal_code")} /></Field>
      <Field label="Commune"><input className="input" value={value.city || ""} onChange={set("city")} /></Field>
      <Field label="Programme"><input className="input" value={value.program || ""} onChange={set("program")} /></Field>
      <Field label="Surface (m²)"><NumberInput min={0} suffix="m²" value={value.surface_m2} onChange={(v) => onChange({ ...value, surface_m2: v })} /></Field>
      <Field label="Budget travaux initial (€ HT)"><NumberInput min={0} suffix="€" value={value.budget_initial} onChange={(v) => onChange({ ...value, budget_initial: v })} /></Field>
      <Field label="Taux d'honoraires (%)"><NumberInput min={0} max={100} suffix="%" value={value.fee_rate} onChange={(v) => onChange({ ...value, fee_rate: v })} /></Field>
      <Field label="Début"><input className="input" type="date" value={value.start_date || ""} onChange={set("start_date")} /></Field>
      <Field label="Fin prévisionnelle"><input className="input" type="date" value={value.end_date || ""} onChange={set("end_date")} /></Field>
      <Field label="Description" className="sm:col-span-2"><textarea className="input min-h-[80px]" value={value.description || ""} onChange={set("description")} /></Field>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={!!value.confidential} onChange={set("confidential")} />
        Projet confidentiel (visible uniquement par l'équipe du projet, les chefs de projet et les administrateurs ; non transmis à une IA externe sans autorisation)</label>
    </div>
  );
}

export function ProjectsList() {
  const { perms, toastError, toast, reloadProjects } = useApp();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useApi<any[]>(`/api/projects?${new URLSearchParams({ ...(status ? { status } : {}), ...(q ? { q } : {}) })}`);
  const clients = useApi<any[]>("/api/clients");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(emptyProject);
  const nav = useNavigate();
  const create = async () => {
    try {
      const p = await api.post("/api/projects", clean(form), `Création du projet ${form.name}`);
      toast(p.__queued ? "Projet enregistré hors ligne : il sera synchronisé au retour du réseau." : "Projet créé.");
      setOpen(false);
      setForm(emptyProject);
      await reloadProjects();
      if (!p.__queued) nav(`/projets/${p.id}`);
      else reload();
    } catch (e) { toastError(e); }
  };
  const clientName = useMemo(() => Object.fromEntries((clients.data || []).map((c) => [c.id, c.name])), [clients.data]);
  return (
    <div>
      <PageHeader title="Projets et chantiers" icon={<FolderKanban size={22} />} subtitle="Toutes les opérations de l'agence, de l'esquisse à la réception."
        actions={perms.write && <button className="btn-primary" onClick={() => setOpen(true)}><Plus size={16} /> Nouveau projet</button>} />
      <div className="flex flex-wrap gap-2 mb-4">
        <input className="input w-64" placeholder="Filtrer par nom, code, commune…" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select className="w-48" value={status} onChange={setStatus} placeholder="Tous les statuts" options={Object.entries(STATUS_PROJECT).map(([v, l]) => ({ value: v, label: l }))} />
      </div>
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : !data?.length ? <Empty title="Aucun projet">Créez votre premier projet avec le bouton « Nouveau projet ».</Empty> : (
        <div className="card overflow-x-auto"><table className="table">
          <thead><tr><th>Code</th><th>Projet</th><th>Maître d'ouvrage</th><th>Commune</th><th>Statut</th><th>Phase</th><th className="w-40">Avancement</th><th className="text-right">Budget HT</th></tr></thead>
          <tbody>{data.map((p) => (
            <tr key={p.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => nav(`/projets/${p.id}`)}>
              <td className="font-medium whitespace-nowrap"><span className="inline-block h-2.5 w-2.5 rounded-full mr-2 align-middle" style={{ background: p.color || "#718578" }} />{p.code}</td>
              <td>{p.name} {p.confidential && <Lock size={12} className="inline text-muted" />}</td><td className="text-muted">{clientName[p.client_id] || "—"}</td>
              <td className="text-muted">{p.city || "—"}</td><td><span className="chip bg-sunken">{STATUS_PROJECT[p.status]}</span></td><td>{p.current_phase || "—"}</td>
              <td><div className="flex items-center gap-2"><Progress value={p.progress} /><span className="text-xs text-muted w-9">{p.progress} %</span></div></td>
              <td className="text-right tabular-nums">{eur(p.budget_initial, 0)}</td></tr>))}</tbody>
        </table></div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Nouveau projet" wide
        footer={<><button className="btn-secondary" onClick={() => setOpen(false)}>Annuler</button><AsyncButton onClick={create} disabled={!form.code?.trim() || !form.name?.trim()}>Créer le projet</AsyncButton></>}>
        <ProjectForm value={form} onChange={setForm} clients={clients.data || []} />
        <p className="text-xs text-muted mt-3">Les phases ESQ, APS, APD, PC, PRO, DCE, ACT, EXE/VISA, DET et AOR sont créées automatiquement ; vous pourrez les adapter à la mission.</p>
      </Modal>
    </div>
  );
}

function Phases({ project, onSave, canEdit }: { project: any; onSave: (patch: any) => Promise<void>; canEdit: boolean }) {
  const [phases, setPhases] = useState<any[]>(project.phases || []);
  const [current, setCurrent] = useState(project.current_phase || "");
  useEffect(() => { setPhases(project.phases || []); setCurrent(project.current_phase || ""); }, [project]);
  const upd = (i: number, k: string, v: any) => setPhases(phases.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  return (
    <Card title="Phases de la mission" actions={canEdit && <AsyncButton onClick={async () => {
      let ph;
      try { ph = phases.map((p) => ({ ...p, progress: toNum(p.progress, `Avancement ${p.code}`) ?? 0 })); } catch (e: any) { alert(e.message); return; }
      await onSave({ phases: ph, current_phase: current || null });
    }}><Save size={15} /> Enregistrer</AsyncButton>}>
      <div className="overflow-x-auto"><table className="table">
        <thead><tr><th>Active</th><th>Phase</th><th>Intitulé</th><th>Début</th><th>Fin</th><th>Statut</th><th>Avancement</th><th>En cours</th></tr></thead>
        <tbody>{phases.map((p, i) => (
          <tr key={p.code} className={p.enabled ? "" : "opacity-50"}>
            <td><input type="checkbox" checked={p.enabled} disabled={!canEdit} onChange={(e) => upd(i, "enabled", e.target.checked)} aria-label={`Activer ${p.code}`} /></td>
            <td className="font-medium">{p.code}</td><td className="text-muted min-w-[220px]">{p.label}</td>
            <td><input type="date" className="input py-1" disabled={!canEdit} value={p.start || ""} onChange={(e) => upd(i, "start", e.target.value || null)} /></td>
            <td><input type="date" className="input py-1" disabled={!canEdit} value={p.end || ""} onChange={(e) => upd(i, "end", e.target.value || null)} /></td>
            <td><Select className="py-1" disabled={!canEdit} value={p.status} onChange={(v) => upd(i, "status", v)} options={[{ value: "a_venir", label: "À venir" }, { value: "en_cours", label: "En cours" }, { value: "terminee", label: "Terminée" }]} /></td>
            <td className="w-24"><NumberInput integer min={0} max={100} className="py-1" disabled={!canEdit} value={p.progress} onChange={(v) => upd(i, "progress", v)} aria-label={`Avancement ${p.code}`} /></td>
            <td><input type="radio" name="current" disabled={!canEdit || !p.enabled} checked={current === p.code} onChange={() => setCurrent(p.code)} aria-label={`Phase en cours ${p.code}`} /></td>
          </tr>))}</tbody>
      </table></div>
    </Card>
  );
}

function Lots({ projectId, companies }: { projectId: string; companies: any[] }) {
  const { perms, toastError, toast } = useApp();
  const { data, reload } = useApi<any[]>(`/api/lots?project_id=${projectId}`);
  const [edit, setEdit] = useState<any>(null);
  const save = async () => {
    try {
      const body = { ...edit, project_id: projectId, budget: toNum(edit.budget, "Budget"), contract_amount: toNum(edit.contract_amount, "Montant du marché"), company_id: edit.company_id || null, progress: toNum(edit.progress, "Avancement") ?? 0 };
      if (edit.id) await api.put(`/api/lots/${edit.id}`, body, `Lot ${edit.code}`);
      else await api.post("/api/lots", body, `Lot ${edit.code}`);
      setEdit(null); toast("Lot enregistré."); reload();
    } catch (e) { toastError(e); }
  };
  const company = Object.fromEntries(companies.map((c) => [c.id, c.name]));
  return (
    <Card title="Lots et entreprises" actions={perms.write && <button className="btn-secondary" onClick={() => setEdit({ code: "", name: "", budget: "", status: "a_consulter", company_id: "", progress: 0, contract_amount: "" })}><Plus size={15} /> Ajouter un lot</button>}>
      {!data?.length ? <Empty title="Aucun lot">Créez les lots de travaux (Gros œuvre, Charpente, Menuiseries…).</Empty> : (
        <div className="overflow-x-auto"><table className="table">
          <thead><tr><th>Lot</th><th>Désignation</th><th>Entreprise</th><th>Statut</th><th className="text-right">Budget HT</th><th className="text-right">Marché HT</th><th>Avancement</th></tr></thead>
          <tbody>{data.map((l) => (
            <tr key={l.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => perms.write && setEdit({ ...l, budget: l.budget ?? "", contract_amount: l.contract_amount ?? "", company_id: l.company_id || "" })}>
              <td className="font-medium">{l.code}</td><td>{l.name}</td><td className="text-muted">{l.company_id ? <Link className="hover:text-sage" onClick={(e) => e.stopPropagation()} to={`/annuaire/entreprises/${l.company_id}`}>{company[l.company_id]}</Link> : "Non attribué"}</td>
              <td><span className="chip bg-sunken">{LOT_STATUS[l.status]}</span></td><td className="text-right tabular-nums">{eur(l.budget, 0)}</td><td className="text-right tabular-nums">{eur(l.contract_amount, 0)}</td>
              <td className="w-32"><Progress value={l.progress} /></td></tr>))}</tbody>
        </table></div>
      )}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? `Lot ${edit.code}` : "Nouveau lot"}
        footer={<>{edit?.id && perms.delete && <button className="btn-ghost text-danger mr-auto" onClick={async () => { try { await api.del(`/api/lots/${edit.id}`); setEdit(null); reload(); } catch (e) { toastError(e); } }}><Trash2 size={15} /> Supprimer</button>}
          <button className="btn-secondary" onClick={() => setEdit(null)}>Annuler</button><AsyncButton onClick={save} disabled={!edit?.code?.trim() || !edit?.name?.trim()}>Enregistrer</AsyncButton></>}>
        {edit && <div className="grid sm:grid-cols-2 gap-3">
          <Field label="N° de lot *"><input className="input" value={edit.code} onChange={(e) => setEdit({ ...edit, code: e.target.value })} /></Field>
          <Field label="Statut"><Select value={edit.status} onChange={(v) => setEdit({ ...edit, status: v })} options={Object.entries(LOT_STATUS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
          <Field label="Désignation *" className="sm:col-span-2"><input className="input" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
          <Field label="Entreprise attributaire" className="sm:col-span-2"><Select value={edit.company_id} onChange={(v) => setEdit({ ...edit, company_id: v })} placeholder="— Non attribué —" options={companies.map((c) => ({ value: c.id, label: c.name }))} /></Field>
          <Field label="Budget (€ HT)"><NumberInput min={0} suffix="€" value={edit.budget} onChange={(v) => setEdit({ ...edit, budget: v })} /></Field>
          <Field label="Montant du marché (€ HT)"><NumberInput min={0} suffix="€" value={edit.contract_amount} onChange={(v) => setEdit({ ...edit, contract_amount: v })} /></Field>
          <Field label="Avancement (%)"><NumberInput integer min={0} max={100} suffix="%" value={edit.progress} onChange={(v) => setEdit({ ...edit, progress: v })} /></Field>
        </div>}
      </Modal>
    </Card>
  );
}

function Incidents({ projectId, incidents, reload }: { projectId: string; incidents: any[]; reload: () => void }) {
  const { perms, toastError } = useApp();
  const [edit, setEdit] = useState<any>(null);
  const save = async () => {
    try {
      if (edit.id) await api.put(`/api/incidents/${edit.id}`, edit, "Incident");
      else await api.post("/api/incidents", { ...edit, project_id: projectId }, "Incident");
      setEdit(null); reload();
    } catch (e) { toastError(e); }
  };
  const sev: Record<string, string> = { faible: "bg-info/15 text-info", moyenne: "bg-warn/15 text-warn", haute: "bg-danger/15 text-danger", critique: "bg-danger text-white" };
  return (
    <Card title="Incidents et observations de chantier" actions={perms.write && <button className="btn-secondary" onClick={() => setEdit({ date: new Date().toISOString().slice(0, 10), title: "", severity: "moyenne", status: "ouvert", description: "" })}><Plus size={15} /> Signaler</button>}>
      {!incidents.length ? <Empty title="Aucun incident enregistré" icon={<AlertTriangle size={18} />} /> : (
        <ul className="divide-y divide-line">{incidents.map((i) => (
          <li key={i.id} className="py-3 flex gap-3 cursor-pointer" onClick={() => perms.write && setEdit(i)}>
            <span className={`chip h-fit ${sev[i.severity]}`}>{i.severity}</span>
            <div className="flex-1 min-w-0"><div className="text-sm font-medium">{i.title}</div><div className="text-xs text-muted">{dateFr(i.date)} · {i.status.replace("_", " ")}</div>
              {i.description && <div className="text-sm text-ink/80 mt-1">{i.description}</div>}{i.resolution && <div className="text-xs text-ok mt-1">Résolution : {i.resolution}</div>}</div>
          </li>))}</ul>
      )}
      <Modal open={!!edit} onClose={() => setEdit(null)} title="Incident" footer={<><button className="btn-secondary" onClick={() => setEdit(null)}>Annuler</button><AsyncButton onClick={save} disabled={!edit?.title?.trim() || !edit?.date}>Enregistrer</AsyncButton></>}>
        {edit && <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Date"><input className="input" type="date" value={edit.date} onChange={(e) => setEdit({ ...edit, date: e.target.value })} /></Field>
          <Field label="Gravité"><Select value={edit.severity} onChange={(v) => setEdit({ ...edit, severity: v })} options={["faible", "moyenne", "haute", "critique"].map((v) => ({ value: v, label: v }))} /></Field>
          <Field label="Intitulé *" className="sm:col-span-2"><input className="input" value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></Field>
          <Field label="Description" className="sm:col-span-2"><textarea className="input min-h-[80px]" value={edit.description || ""} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></Field>
          <Field label="Statut"><Select value={edit.status} onChange={(v) => setEdit({ ...edit, status: v })} options={[{ value: "ouvert", label: "Ouvert" }, { value: "en_cours", label: "En cours" }, { value: "clos", label: "Clos" }]} /></Field>
          <Field label="Résolution"><input className="input" value={edit.resolution || ""} onChange={(e) => setEdit({ ...edit, resolution: e.target.value })} /></Field>
        </div>}
      </Modal>
    </Card>
  );
}

function Team({ project, users, onSave, canEdit }: { project: any; users: any[]; onSave: (p: any) => Promise<void>; canEdit: boolean }) {
  const [team, setTeam] = useState<any[]>(project.team || []);
  useEffect(() => { setTeam(project.team || []); }, [project]);
  const free = users.filter((u) => !team.some((m) => m.user_id === u.id));
  const name = Object.fromEntries(users.map((u) => [u.id, u]));
  return (
    <Card title="Équipe affectée" actions={canEdit && <AsyncButton onClick={() => onSave({ team })}><Save size={15} /> Enregistrer</AsyncButton>}>
      <ul className="divide-y divide-line">{team.map((m, i) => (
        <li key={m.user_id} className="py-2 flex items-center gap-3">
          <div className="h-8 w-8 rounded-full text-white text-xs flex items-center justify-center" style={{ background: name[m.user_id]?.color || "#718578" }}>{name[m.user_id]?.full_name?.split(" ").map((s: string) => s[0]).join("")}</div>
          <div className="flex-1"><div className="text-sm">{name[m.user_id]?.full_name || "Utilisateur"}</div><div className="text-xs text-muted">{name[m.user_id]?.role_label}</div></div>
          <input className="input w-56" placeholder="Rôle sur le projet" disabled={!canEdit} value={m.role || ""} onChange={(e) => setTeam(team.map((x, j) => (j === i ? { ...x, role: e.target.value } : x)))} />
          {canEdit && <button className="btn-ghost p-1.5 text-danger" onClick={() => setTeam(team.filter((_, j) => j !== i))} aria-label="Retirer"><Trash2 size={15} /></button>}
        </li>))}</ul>
      {canEdit && free.length > 0 && <div className="mt-3 max-w-xs"><Select value="" onChange={(v) => v && setTeam([...team, { user_id: v, role: "" }])} placeholder="+ Ajouter un collaborateur" options={free.map((u) => ({ value: u.id, label: u.full_name }))} /></div>}
    </Card>
  );
}

function Terrain({ project, onSave, canEdit }: { project: any; onSave: (p: any) => Promise<void>; canEdit: boolean }) {
  const [t, setT] = useState<any>(project.terrain || {});
  const [coords, setCoords] = useState({ latitude: project.latitude ?? "", longitude: project.longitude ?? "" });
  useEffect(() => { setT(project.terrain || {}); setCoords({ latitude: project.latitude ?? "", longitude: project.longitude ?? "" }); }, [project]);
  const fields = [["parcelle", "Référence(s) cadastrale(s)"], ["surface_cadastrale_m2", "Surface cadastrale (m²)"], ["zone_plu", "Zone du PLU"], ["topographie", "Topographie"],
    ["nature_sol", "Nature du sol / géotechnique"], ["reseaux", "Réseaux disponibles"], ["acces", "Accès et servitudes de passage"], ["notes", "Observations"]];
  return (
    <Card title="Informations du terrain" actions={<>
      <Link to="/urbanisme" className="btn-secondary"><ExternalLink size={14} /> Analyser la parcelle</Link>
      {canEdit && <AsyncButton onClick={() => onSave({ terrain: t, latitude: coords.latitude, longitude: coords.longitude })}><Save size={15} /> Enregistrer</AsyncButton>}</>}>
      <div className="grid sm:grid-cols-2 gap-3">
        {fields.map(([k, l]) => <Field key={k} label={l}><input className="input" disabled={!canEdit} value={t[k] ?? ""} onChange={(e) => setT({ ...t, [k]: e.target.value })} /></Field>)}
        <Field label="Latitude (WGS84)" hint="Ex. 47,2184 — renseignée automatiquement par l'analyse urbanistique ou la météo."><NumberInput min={-90} max={90} disabled={!canEdit} value={coords.latitude} onChange={(v) => setCoords({ ...coords, latitude: v })} /></Field>
        <Field label="Longitude (WGS84)" hint="Ex. -1,5536"><NumberInput min={-180} max={180} disabled={!canEdit} value={coords.longitude} onChange={(v) => setCoords({ ...coords, longitude: v })} /></Field>
      </div>
    </Card>
  );
}

export function ProjectDetail() {
  const { id } = useParams();
  const { perms, toast, toastError, reloadProjects, setProjectId } = useApp();
  const { data, loading, error, reload } = useApi<any>(`/api/projects/${id}/overview`);
  const clients = useApi<any[]>("/api/clients");
  const companies = useApi<any[]>("/api/companies");
  const users = useApi<any[]>("/api/users");
  const [tab, setTab] = useState("synthese");
  const [form, setForm] = useState<any>(null);
  const [del, setDel] = useState(false);
  const nav = useNavigate();
  useEffect(() => { if (data) setForm({ ...emptyProject, ...data.project }); }, [data]);
  useEffect(() => { if (id) setProjectId(id); }, [id, setProjectId]);
  const save = async (patch: any) => {
    try {
      const r = await api.put(`/api/projects/${id}`, { ...clean(patch), version: data.project.version }, `Projet ${data.project.code}`);
      toast(r.__queued ? "Modification enregistrée hors ligne." : "Projet enregistré.");
      reload(); reloadProjects();
    } catch (e: any) {
      // En cas d'échec, la saisie est conservée : seul un conflit de version recharge la fiche.
      if (e.status === 409) { toast("Conflit : ce projet a été modifié par un autre utilisateur. La version actuelle a été rechargée.", "error"); reload(); }
      else toastError(e);
    }
  };
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorBox error={error} />;
  const p = data.project;
  return (
    <div>
      <PageHeader title={p.name} subtitle={<span>{p.code} · {STATUS_PROJECT[p.status]} · phase {p.current_phase || "—"} {p.confidential && <span className="chip bg-sunken ml-1"><Lock size={11} /> confidentiel</span>}</span>}
        actions={<>
          <Link className="btn-secondary" to="/devis">Devis ({data.counts.quotes})</Link>
          <Link className="btn-secondary" to="/planning">Planning ({data.counts.tasks})</Link>
          {perms.delete && <button className="btn-ghost text-danger" onClick={() => setDel(true)}><Trash2 size={15} /></button>}
        </>} />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div className="card p-4"><div className="text-xs text-muted">Avancement</div><div className="text-xl font-semibold">{p.progress} %</div><Progress value={p.progress} /></div>
        <div className="card p-4"><div className="text-xs text-muted">Budget initial</div><div className="text-xl font-semibold">{eur(p.budget_initial, 0)}</div></div>
        <div className="card p-4"><div className="text-xs text-muted">Maître d'ouvrage</div><div className="text-sm font-medium mt-1">{data.client ? <Link className="hover:text-sage" to={`/annuaire/clients/${data.client.id}`}>{data.client.name}</Link> : "—"}</div></div>
        <div className="card p-4"><div className="text-xs text-muted">Échéance</div><div className="text-sm font-medium mt-1">{dateFr(p.start_date)} → {dateFr(p.end_date)}</div></div>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "synthese", label: "Fiche projet" }, { id: "phases", label: "Phases" }, { id: "lots", label: `Lots (${data.lots.length})` },
        { id: "terrain", label: "Terrain" }, { id: "equipe", label: `Équipe (${data.team.length})` }, { id: "incidents", label: `Incidents (${data.incidents.length})` },
        { id: "documents", label: `Documents (${data.counts.documents})` }]} />
      {tab === "synthese" && form && (
        <Card title="Fiche projet" actions={perms.write && <AsyncButton onClick={() => save(form)} disabled={!form.code?.trim() || !form.name?.trim()}><Save size={15} /> Enregistrer</AsyncButton>}>
          <ProjectForm value={form} onChange={setForm} clients={clients.data || []} />
          <div className="grid sm:grid-cols-2 gap-3 mt-3"><Field label="Avancement global (%)"><NumberInput integer min={0} max={100} suffix="%" value={form.progress} onChange={(v) => setForm({ ...form, progress: v })} /></Field></div>
          {data.companies.length > 0 && <div className="mt-4 text-sm"><span className="text-muted">Entreprises suivies : </span>{data.companies.join(" · ")}</div>}
        </Card>
      )}
      {tab === "phases" && <Phases project={p} onSave={save} canEdit={perms.write} />}
      {tab === "lots" && <Lots projectId={p.id} companies={companies.data || []} />}
      {tab === "terrain" && <Terrain project={p} onSave={save} canEdit={perms.write} />}
      {tab === "equipe" && <Team project={p} users={users.data || []} onSave={save} canEdit={perms.write} />}
      {tab === "incidents" && <Incidents projectId={p.id} incidents={data.incidents} reload={reload} />}
      {tab === "documents" && <DocumentsTable projectId={p.id} />}
      <Confirm open={del} onClose={() => setDel(false)} title="Supprimer le projet" confirmLabel="Supprimer"
        message={<>Le projet <b>{p.name}</b> sera supprimé (suppression logique, conservée dans l'historique et les sauvegardes).</>}
        onConfirm={async () => { try { await api.del(`/api/projects/${p.id}?version=${p.version}`); await reloadProjects(); setProjectId(null); nav("/projets"); } catch (e) { toastError(e); } }} />
    </div>
  );
}
