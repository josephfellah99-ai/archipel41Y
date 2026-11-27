import { Users, Plus, Mail, Phone, KeyRound, Copy, Ban, ShieldCheck, UserX, Activity, Link2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr, dateTimeFr, ROLE_LABELS } from "../lib/format";
import { AsyncButton, Card, Confirm, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Select, Spinner, Tabs } from "../components/ui";

const LEVEL_SHORT: Record<string, string> = { none: "Aucun", read: "Lecture", write: "Modification", full: "Complet" };
const ROLE_HELP: Record<string, string> = {
  admin: "Gestion complète : comptes, autorisations, invitations, paramètres, historiques.",
  manager: "Gère projets, documents et opérations ; valide devis, documents et plannings.",
  member: "Consulte et modifie selon les droits accordés.",
  viewer: "Consulte sans modifier.",
};
const ACTION_LABELS: Record<string, string> = { create: "a créé", update: "a modifié", delete: "a supprimé", commentaire: "a commenté", invitation_creee: "a créé une invitation" };
const ENTITY_LABELS: Record<string, string> = {
  projects: "le projet", documents: "le document", tasks: "la tâche", events: "le rendez-vous", quotes: "le devis", lots: "le lot",
  finance_entries: "l'écriture", clients: "le client", companies: "l'entreprise", comparisons: "le comparatif", users: "le compte",
  incidents: "l'incident", invitations: "l'invitation", geo_layers: "la couche", budget_lines: "la ligne budgétaire",
};

function initials(n: string) { return n.split(" ").map((s) => s[0]).slice(0, 2).join(""); }

function Avatar({ name, color, size = 9 }: { name: string; color?: string; size?: number }) {
  const px = size * 4;
  return <div className="rounded-full shrink-0 flex items-center justify-center text-xs font-semibold text-white" style={{ background: color || "#718578", width: px, height: px }}>{initials(name)}</div>;
}

export function ActivityFeed({ items }: { items: any[] }) {
  if (!items.length) return <Empty title="Aucune activité récente" icon={<Activity size={18} />} />;
  return (
    <ul className="divide-y divide-line">{items.map((a, i) => (
      <li key={i} className="py-2.5 text-sm flex gap-3">
        <span className="text-xs text-muted w-28 shrink-0 tabular-nums">{dateTimeFr(a.at)}</span>
        <span><b className="font-medium">{a.user}</b> {ACTION_LABELS[a.action] || a.action} {ENTITY_LABELS[a.entity] || ""} <span className="text-muted">{(a.summary || "").split(" : ")[0]}</span></span>
      </li>))}</ul>
  );
}

/** Éditeur des autorisations fines : rôle, niveau par module, accès par projet. */
function PermissionsEditor({ value, onChange, role }: { value: any; onChange: (v: any) => void; role: string }) {
  const cat = useApi<any>("/api/permissions/catalog");
  const roles = useApi<any[]>("/api/roles");
  const { projects } = useApp();
  const def = roles.data?.find((r) => r.code === role)?.default_level || "read";
  const v = { modules: {}, projects: {}, assigned_only: false, ...(value || {}) };
  if (role === "admin") return <Notice tone="info">Un administrateur dispose toujours d'un accès complet à tous les modules et projets.</Notice>;
  if (!cat.data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div>
        <div className="label">Accès par module <span className="text-muted font-normal">(par défaut pour ce rôle : {LEVEL_SHORT[def]})</span></div>
        <div className="border border-line rounded-lg divide-y divide-line">
          {cat.data.modules.map((m: any) => {
            const cur = v.modules[m.code] || "";
            return (
              <div key={m.code} className="flex items-center gap-3 px-3 py-1.5">
                <span className="text-sm flex-1">{m.label}</span>
                <select className="input py-1 w-44" aria-label={`Accès ${m.label}`} value={cur} onChange={(e) => {
                  const mods = { ...v.modules };
                  if (e.target.value) mods[m.code] = e.target.value; else delete mods[m.code];
                  onChange({ ...v, modules: mods });
                }}>
                  <option value="">Par défaut ({LEVEL_SHORT[def]})</option>
                  {cat.data.levels.map((l: any) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </div>);
          })}
        </div>
      </div>
      <div>
        <div className="label">Accès aux projets</div>
        <label className="flex items-center gap-2 text-sm mb-2"><input type="checkbox" checked={!!v.assigned_only} onChange={(e) => onChange({ ...v, assigned_only: e.target.checked })} />
          Uniquement les projets auxquels la personne est affectée (équipe du projet)</label>
        <div className="border border-line rounded-lg divide-y divide-line max-h-56 overflow-y-auto scrollbar-thin">
          {projects.map((p) => (
            <div key={p.id} className="flex items-center gap-3 px-3 py-1.5">
              <span className="text-sm flex-1 truncate">{p.code} – {p.name}</span>
              <select className="input py-1 w-44" aria-label={`Accès projet ${p.code}`} value={v.projects[p.id] || ""} onChange={(e) => {
                const pr = { ...v.projects };
                if (e.target.value) pr[p.id] = e.target.value; else delete pr[p.id];
                onChange({ ...v, projects: pr });
              }}>
                <option value="">Selon le rôle</option>
                {cat.data.project_levels.map((l: any) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>))}
          {!projects.length && <div className="px-3 py-2 text-sm text-muted">Aucun projet.</div>}
        </div>
      </div>
    </div>
  );
}

function UserModal({ edit, onClose, onSaved }: { edit: any; onClose: () => void; onSaved: () => void }) {
  const { toast, toastError, user } = useApp();
  const [f, setF] = useState<any>(edit);
  const [tab, setTab] = useState("profil");
  const save = async () => {
    try {
      const perms = f.role === "admin" ? {} : (f.permissions || {});
      if (f.id) {
        await api.call("PUT", `/api/users/${f.id}`, { full_name: f.full_name, role: f.role, active: f.active, job_title: f.job_title || null,
          phone: f.phone || null, color: f.color || null, permissions: perms, ...(f.password ? { password: f.password } : {}) });
      } else {
        await api.call("POST", "/api/users", { email: f.email, full_name: f.full_name, role: f.role, password: f.password,
          job_title: f.job_title || null, phone: f.phone || null, color: f.color || null, permissions: perms });
      }
      toast("Compte enregistré.");
      onSaved();
      onClose();
    } catch (e) { toastError(e); }
  };
  return (
    <Modal open onClose={onClose} title={f.id ? f.full_name : "Nouveau collaborateur"} wide
      footer={<><button className="btn-secondary" onClick={onClose}>Annuler</button>
        <AsyncButton onClick={save} disabled={!f.full_name?.trim() || !f.email?.trim() || (!f.id && !f.password)}>Enregistrer</AsyncButton></>}>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "profil", label: "Profil et rôle" }, { id: "droits", label: "Autorisations" }]} />
      {tab === "profil" ? (
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Nom complet" required><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="E-mail (identifiant)" required><input className="input" type="email" disabled={!!f.id} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Rôle" hint={ROLE_HELP[f.role]}><Select value={f.role} onChange={(v) => setF({ ...f, role: v })} options={Object.entries(ROLE_LABELS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
          <Field label="Fonction"><input className="input" value={f.job_title || ""} onChange={(e) => setF({ ...f, job_title: e.target.value })} placeholder="Architecte, conducteur de travaux…" /></Field>
          <Field label="Téléphone"><input className="input" value={f.phone || ""} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          <Field label="Couleur (agenda, planning)"><input className="input h-10 p-1" type="color" value={f.color || "#718578"} onChange={(e) => setF({ ...f, color: e.target.value })} /></Field>
          <Field label={f.id ? "Nouveau mot de passe (facultatif)" : "Mot de passe initial"} required={!f.id} hint="10 caractères minimum, 3 types de caractères. À changer par la personne à sa première connexion.">
            <input className="input" type="password" autoComplete="new-password" value={f.password || ""} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          {f.id && f.id !== user?.id && <label className="text-sm flex items-center gap-2 self-end pb-2"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Compte actif (décochez pour désactiver sans supprimer)</label>}
        </div>
      ) : <PermissionsEditor value={f.permissions} role={f.role} onChange={(p) => setF({ ...f, permissions: p })} />}
    </Modal>
  );
}

function Members() {
  const { perms, toast, toastError, user } = useApp();
  const team = useApi<any[]>("/api/team");
  const users = useApi<any[]>(perms.admin ? "/api/users" : null);
  const [edit, setEdit] = useState<any>(null);
  const [del, setDel] = useState<any>(null);
  const [sel, setSel] = useState<string | null>(null);
  const full = useMemo(() => Object.fromEntries((users.data || []).map((u) => [u.id, u])), [users.data]);
  const reload = () => { team.reload(); users.reload(); };
  if (team.loading && !team.data) return <Spinner />;
  return (
    <div className="grid xl:grid-cols-[1fr_380px] gap-6">
      <Card title={`${team.data?.length || 0} collaborateur(s)`} pad={false} actions={perms.admin && <button className="btn-primary" onClick={() => setEdit({ email: "", full_name: "", role: "member", password: "", active: true, color: "#718578", permissions: {} })}><Plus size={15} /> Collaborateur</button>}>
        <ul className="divide-y divide-line">{(team.data || []).map((u) => (
          <li key={u.id} className={`px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-sunken/50 ${sel === u.id ? "bg-sunken/60" : ""}`} onClick={() => setSel(u.id)}>
            <Avatar name={u.full_name} color={u.color} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium truncate">{u.full_name}{u.id === user?.id && <span className="text-xs text-muted font-normal"> (vous)</span>}
                {!u.active && <span className="chip bg-sunken text-muted ml-2">désactivé</span>}</div>
              <div className="text-xs text-muted truncate">{[u.job_title, u.role_label].filter(Boolean).join(" · ")}</div>
            </div>
            <div className="hidden md:block text-xs text-muted text-right w-44 truncate">{u.projects.length ? u.projects.map((p: any) => p.code).join(", ") : "aucun projet"}</div>
            <div className="text-xs w-20 text-right">{u.open_tasks ? <span className="chip bg-info/15 text-info">{u.open_tasks} tâche(s)</span> : ""}</div>
            {perms.admin && full[u.id] && <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
              <button className="btn-ghost p-1.5" title="Modifier le compte et les autorisations" onClick={() => setEdit({ ...full[u.id], password: "" })}><ShieldCheck size={15} /></button>
              {u.id !== user?.id && <button className="btn-ghost p-1.5 text-danger" title="Supprimer le compte" onClick={() => setDel(u)}><UserX size={15} /></button>}
            </div>}
          </li>))}</ul>
      </Card>
      <MemberPanel id={sel || user?.id || null} />
      {edit && <UserModal edit={edit} onClose={() => setEdit(null)} onSaved={reload} />}
      <Confirm open={!!del} onClose={() => setDel(null)} title="Supprimer le compte" confirmLabel="Supprimer"
        message={<>Le compte de <b>{del?.full_name}</b> sera supprimé : la personne ne pourra plus se connecter. Son historique (journaux, documents, commentaires) est conservé. Pour une suspension temporaire, préférez « désactiver ».</>}
        onConfirm={async () => { try { const r = await api.call("DELETE", `/api/users/${del.id}`); toast(r.message); reload(); } catch (e) { toastError(e); } }} />
    </div>
  );
}

function MemberPanel({ id }: { id: string | null }) {
  const m = useApi<any>(id ? `/api/team/${id}` : null);
  if (!id) return null;
  if (m.loading && !m.data) return <Card><Spinner /></Card>;
  if (!m.data) return <Card><ErrorBox error={m.error} /></Card>;
  const u = m.data;
  return (
    <Card>
      <div className="flex items-center gap-3"><Avatar name={u.full_name} color={u.color} size={12} />
        <div><div className="font-semibold">{u.full_name}</div><div className="text-xs text-muted">{[u.job_title, u.role_label].filter(Boolean).join(" · ")}</div></div></div>
      <div className="mt-3 space-y-1 text-sm">
        <div className="flex items-center gap-2"><Mail size={14} className="text-muted" /><a className="hover:text-sage" href={`mailto:${u.email}`}>{u.email}</a></div>
        {u.phone && <div className="flex items-center gap-2"><Phone size={14} className="text-muted" /><a className="hover:text-sage" href={`tel:${u.phone}`}>{u.phone}</a></div>}
      </div>
      <div className="label mt-4">Projets attribués</div>
      {u.projects.length ? <ul className="text-sm space-y-1">{u.projects.map((p: any) => <li key={p.id}><Link className="hover:text-sage" to={`/projets/${p.id}`}>{p.label}</Link></li>)}</ul> : <div className="text-sm text-muted">Aucun.</div>}
      <div className="label mt-4">Tâches et responsabilités</div>
      {u.tasks.length ? <ul className="text-sm space-y-1">{u.tasks.slice(0, 10).map((t: any) => <li key={t.id} className="flex justify-between gap-2"><span className="truncate">{t.name} <span className="text-muted">· {t.project}</span></span><span className="text-xs text-muted shrink-0">{t.progress} %</span></li>)}</ul> : <div className="text-sm text-muted">Aucune tâche.</div>}
      <div className="label mt-4">Activité récente</div>
      <ActivityFeed items={u.activity.slice(0, 8).map((a: any) => ({ ...a, user: u.full_name }))} />
    </Card>
  );
}

function Invitations() {
  const { toast, toastError, projects } = useApp();
  const list = useApi<any[]>("/api/invitations");
  const [f, setF] = useState<any>(null);
  const [created, setCreated] = useState<any>(null);
  const [rev, setRev] = useState<any>(null);
  const create = async () => {
    try {
      const r = await api.call("POST", "/api/invitations", { ...f, valid_days: Number(f.valid_days), max_uses: Number(f.max_uses), session_hours: Number(f.session_hours),
        guest_email: f.guest_email || null, guest_name: f.guest_name || null, project_ids: f.kind === "projet" ? f.project_ids : [] });
      setCreated(r); setF(null); list.reload();
    } catch (e) { toastError(e); }
  };
  const ST: Record<string, string> = { active: "bg-ok/15 text-ok", expiree: "bg-sunken text-muted", revoquee: "bg-danger/15 text-danger", epuisee: "bg-warn/15 text-warn" };
  const SL: Record<string, string> = { active: "Active", expiree: "Expirée", revoquee: "Révoquée", epuisee: "Utilisations épuisées" };
  const link = (code: string) => `${window.location.origin}${window.location.pathname}?invitation=${code}`;
  return (
    <div className="space-y-4">
      <Notice tone="info">Une invitation donne à une personne extérieure un accès <b>limité et temporaire</b> : soit à l'espace de <b>démonstration</b> (données fictives),
        soit à un ou plusieurs <b>projets</b> (fiche, documents validés, planning, terrain — selon votre choix). Le code n'est affiché qu'une fois ; il peut être révoqué à tout moment.</Notice>
      <Card title="Invitations" pad={false} actions={<button className="btn-primary" onClick={() => setF({ kind: "projet", label: "", guest_name: "", guest_email: "", valid_days: 7, max_uses: 3, session_hours: 8,
        project_ids: [], modules: ["fiche", "documents"], doc_categories: [], can_download: false, can_comment: false })}><Plus size={15} /> Créer une invitation</button>}>
        {!list.data?.length ? <Empty title="Aucune invitation" icon={<KeyRound size={18} />} /> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>Invitation</th><th>Type</th><th>Accès</th><th>Code</th><th>Expire le</th><th>Utilisations</th><th>État</th><th /></tr></thead>
            <tbody>{list.data.map((i) => (
              <tr key={i.id}>
                <td><div className="font-medium">{i.label}</div><div className="text-xs text-muted">{i.guest_name || "—"} · créée par {i.created_by_name}</div></td>
                <td>{i.kind === "demo" ? "Démonstration" : "Projet"}</td>
                <td className="text-xs">{i.kind === "demo" ? "Données fictives" : <>{i.projects.map((p: any) => p.label).join(", ")}<div className="text-muted">{i.modules.join(", ")}{i.can_download ? " · téléchargement" : ""}{i.can_comment ? " · commentaires" : ""}</div></>}</td>
                <td className="font-mono text-xs">{i.code_masque}</td>
                <td>{dateFr(i.expires_at)}</td><td className="tabular-nums">{i.uses} / {i.max_uses}</td>
                <td><span className={`chip ${ST[i.status]}`}>{SL[i.status]}</span></td>
                <td>{i.status === "active" && <button className="btn-ghost text-danger py-1" onClick={() => setRev(i)}><Ban size={14} /> Révoquer</button>}</td>
              </tr>))}</tbody></table></div>)}
      </Card>
      {f && (
        <Modal open onClose={() => setF(null)} title="Créer une invitation" wide footer={<><button className="btn-secondary" onClick={() => setF(null)}>Annuler</button>
          <AsyncButton onClick={create} disabled={!f.label.trim() || (f.kind === "projet" && !f.project_ids.length)}>Générer le code</AsyncButton></>}>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field group label="Type d'invitation" className="sm:col-span-2"><div className="grid sm:grid-cols-2 gap-2">
              {[["projet", "Invitation à un projet", "Consultation limitée d'un ou plusieurs projets réels."], ["demo", "Invitation de démonstration", "Découverte de l'application sur des données fictives."]].map(([k, l, h]) => (
                <button key={k} type="button" onClick={() => setF({ ...f, kind: k })} className={`text-left rounded-lg border p-3 ${f.kind === k ? "border-forest bg-forest/5" : "border-line"}`}>
                  <div className="text-sm font-medium">{l}</div><div className="text-xs text-muted">{h}</div></button>))}</div></Field>
            <Field label="Intitulé" required><input className="input" value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder="Présentation du projet à M. Martin" /></Field>
            <Field label="Nom de l'invité"><input className="input" value={f.guest_name} onChange={(e) => setF({ ...f, guest_name: e.target.value })} /></Field>
            <Field label="E-mail de l'invité (facultatif)"><input className="input" type="email" value={f.guest_email} onChange={(e) => setF({ ...f, guest_email: e.target.value })} /></Field>
            <Field label="Validité du code"><Select value={String(f.valid_days)} onChange={(v) => setF({ ...f, valid_days: v })} options={[["1", "1 jour"], ["3", "3 jours"], ["7", "7 jours"], ["14", "14 jours"], ["30", "30 jours"], ["90", "90 jours"]].map(([v, l]) => ({ value: v, label: l }))} /></Field>
            <Field label="Nombre d'utilisations"><Select value={String(f.max_uses)} onChange={(v) => setF({ ...f, max_uses: v })} options={["1", "3", "5", "10", "25"].map((v) => ({ value: v, label: v }))} /></Field>
            <Field label="Durée d'une session"><Select value={String(f.session_hours)} onChange={(v) => setF({ ...f, session_hours: v })} options={[["2", "2 heures"], ["8", "8 heures"], ["24", "24 heures"], ["72", "3 jours"]].map(([v, l]) => ({ value: v, label: l }))} /></Field>
            {f.kind === "projet" && <>
              <Field group label="Projets partagés" required className="sm:col-span-2">
                <div className="border border-line rounded-lg max-h-40 overflow-y-auto scrollbar-thin divide-y divide-line">{projects.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 px-3 py-1.5 text-sm"><input type="checkbox" checked={f.project_ids.includes(p.id)}
                    onChange={(e) => setF({ ...f, project_ids: e.target.checked ? [...f.project_ids, p.id] : f.project_ids.filter((x: string) => x !== p.id) })} />{p.code} – {p.name}</label>))}</div></Field>
              <Field group label="Parties visibles" className="sm:col-span-2"><div className="flex flex-wrap gap-3">
                {[["fiche", "Fiche du projet"], ["documents", "Documents"], ["planning", "Planning"], ["terrain", "Terrain et carte"]].map(([k, l]) => (
                  <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.modules.includes(k)}
                    onChange={(e) => setF({ ...f, modules: e.target.checked ? [...f.modules, k] : f.modules.filter((x: string) => x !== k) })} />{l}</label>))}</div></Field>
              <Field label="Documents partagés" className="sm:col-span-2" hint="Par défaut : uniquement les documents « validés » des catégories plans, rapports, comptes rendus, photos et urbanisme. Les documents confidentiels et archivés ne sont jamais partagés.">
                <Select value={f.doc_categories.length ? "plans" : ""} onChange={(v) => setF({ ...f, doc_categories: v === "plans" ? ["plan"] : [] })}
                  options={[{ value: "", label: "Documents validés (par défaut)" }, { value: "plans", label: "Plans uniquement (y compris de travail)" }]} /></Field>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.can_download} onChange={(e) => setF({ ...f, can_download: e.target.checked })} /> Autoriser le téléchargement des fichiers</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.can_comment} onChange={(e) => setF({ ...f, can_comment: e.target.checked })} /> Autoriser les commentaires</label>
            </>}
          </div>
        </Modal>)}
      {created && (
        <Modal open onClose={() => setCreated(null)} title="Invitation créée" footer={<button className="btn-primary" onClick={() => setCreated(null)}>J'ai noté le code</button>}>
          <Notice tone="warn">Ce code ne sera <b>plus jamais affiché</b>. Transmettez-le à l'invité par un canal sûr (de vive voix, SMS…).</Notice>
          <div className="text-center my-5"><div className="font-mono text-3xl tracking-[0.2em] text-forest select-all" aria-label="Code d'invitation">{created.code}</div>
            <div className="text-xs text-muted mt-2">Valable jusqu'au {dateFr(created.expires_at)} · {created.max_uses} utilisation(s)</div></div>
          <div className="flex flex-wrap gap-2 justify-center">
            <button className="btn-secondary" onClick={() => { navigator.clipboard?.writeText(created.code); toast("Code copié."); }}><Copy size={14} /> Copier le code</button>
            <button className="btn-secondary" onClick={() => { navigator.clipboard?.writeText(link(created.code)); toast("Lien d'accès copié."); }}><Link2 size={14} /> Copier le lien d'accès</button>
          </div>
        </Modal>)}
      <Confirm open={!!rev} onClose={() => setRev(null)} title="Révoquer l'invitation" confirmLabel="Révoquer"
        message={<>L'invitation « {rev?.label} » sera désactivée immédiatement et les sessions invitées ouvertes seront fermées.</>}
        onConfirm={async () => { try { await api.call("POST", `/api/invitations/${rev.id}/revoke`); toast("Invitation révoquée."); list.reload(); } catch (e) { toastError(e); } }} />
    </div>
  );
}

export default function TeamPage() {
  const { perms } = useApp();
  const [tab, setTab] = useState("equipe");
  const act = useApi<any[]>(tab === "activite" ? "/api/team/activity/recent?days=30" : null);
  return (
    <div>
      <PageHeader title="Équipe" icon={<Users size={22} />} subtitle="Collaborateurs, rôles et autorisations, projets attribués, invitations et activité de l'agence." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "equipe", label: "Collaborateurs" }, ...(perms.admin ? [{ id: "invitations", label: "Gestion des accès invités" }] : []),
        { id: "activite", label: "Activité récente" }]} />
      {tab === "equipe" && <Members />}
      {tab === "invitations" && perms.admin && <Invitations />}
      {tab === "activite" && <Card>{act.loading && !act.data ? <Spinner /> : <ActivityFeed items={act.data || []} />}</Card>}
    </div>
  );
}
