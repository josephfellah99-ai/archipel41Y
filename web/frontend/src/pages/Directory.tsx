import { Users, Plus, Building2, User, Save, Trash2, Star } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApi, useApp, useEditable } from "../lib/app";
import { dateFr, eur, QUOTE_STATUS, STATUS_PROJECT } from "../lib/format";
import { StaleNotice } from "./Projects";
import { AsyncButton, Card, Confirm, Empty, ErrorBox, Field, Modal, PageHeader, Select, Spinner, Tabs } from "../components/ui";

const KINDS: Record<string, string> = { particulier: "Particulier", entreprise: "Entreprise", collectivite: "Collectivité", promoteur: "Promoteur / SCI" };

function Contacts({ value, onChange, disabled }: { value: any[]; onChange: (v: any[]) => void; disabled?: boolean }) {
  return (
    <div>
      <div className="label">Contacts</div>
      <div className="space-y-2">{value.map((c, i) => (
        <div key={i} className="grid grid-cols-2 sm:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2">
          {["name", "role", "email", "phone"].map((k) => <input key={k} className="input py-1.5" disabled={disabled} placeholder={{ name: "Nom", role: "Fonction", email: "E-mail", phone: "Téléphone" }[k]}
            value={c[k] || ""} onChange={(e) => onChange(value.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))} />)}
          {!disabled && <button className="btn-ghost text-danger p-1.5" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label="Retirer"><Trash2 size={14} /></button>}
        </div>))}</div>
      {!disabled && <button className="btn-ghost text-sage text-xs mt-1 px-0" onClick={() => onChange([...value, { name: "" }])}><Plus size={13} /> Ajouter un contact</button>}
    </div>
  );
}

/** Liste saisie en texte libre : la frappe (virgules, espaces) n'est jamais modifiée pendant la saisie. */
function ListInput({ value, onChange, disabled, placeholder }: { value: string[]; onChange: (v: string[]) => void; disabled?: boolean; placeholder?: string }) {
  const [txt, setTxt] = useState((value || []).join(", "));
  const last = useRef(value);
  useEffect(() => { if (value !== last.current) { last.current = value; const cur = txt.split(",").map((x) => x.trim()).filter(Boolean); if (cur.join("|") !== (value || []).join("|")) setTxt((value || []).join(", ")); } }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  return <input className="input" disabled={disabled} placeholder={placeholder} value={txt}
    onChange={(e) => { setTxt(e.target.value); const arr = e.target.value.split(",").map((x) => x.trim()).filter(Boolean); last.current = arr; onChange(arr); }} />;
}

function EntityForm({ kind, value, onChange, disabled }: { kind: "client" | "company"; value: any; onChange: (v: any) => void; disabled?: boolean }) {
  const set = (k: string) => (e: any) => onChange({ ...value, [k]: e.target.value });
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      <Field label="Nom / raison sociale *" className="sm:col-span-2"><input className="input" disabled={disabled} value={value.name || ""} onChange={set("name")} /></Field>
      {kind === "client" ? <Field label="Type"><Select disabled={disabled} value={value.kind} onChange={(v) => onChange({ ...value, kind: v })} options={Object.entries(KINDS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        : <Field label="Spécialités (séparées par des virgules)"><ListInput disabled={disabled} placeholder="Gros œuvre, Maçonnerie" value={value.specialties || []} onChange={(v) => onChange({ ...value, specialties: v })} /></Field>}
      <Field label="SIRET"><input className="input" disabled={disabled} value={value.siret || ""} onChange={set("siret")} /></Field>
      <Field label="E-mail"><input className="input" type="email" disabled={disabled} value={value.email || ""} onChange={set("email")} /></Field>
      <Field label="Téléphone"><input className="input" disabled={disabled} value={value.phone || ""} onChange={set("phone")} /></Field>
      <Field label="Adresse" className="sm:col-span-2"><input className="input" disabled={disabled} value={value.address || ""} onChange={set("address")} /></Field>
      <Field label="Code postal"><input className="input" disabled={disabled} value={value.postal_code || ""} onChange={set("postal_code")} /></Field>
      <Field label="Ville"><input className="input" disabled={disabled} value={value.city || ""} onChange={set("city")} /></Field>
      {kind === "company" && <><Field label="Assurance décennale"><input className="input" disabled={disabled} value={value.insurance || ""} onChange={set("insurance")} /></Field>
        <Field label="Évaluation (1 à 5)"><Select disabled={disabled} value={value.rating ? String(value.rating) : ""} onChange={(v) => onChange({ ...value, rating: v ? Number(v) : null })} placeholder="—" options={[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: "★".repeat(n) }))} /></Field></>}
      <div className="sm:col-span-2"><Contacts value={value.contacts || []} onChange={(v) => onChange({ ...value, contacts: v })} disabled={disabled} /></div>
      <Field label="Observations" className="sm:col-span-2"><textarea className="input min-h-[80px]" disabled={disabled} value={value.notes || ""} onChange={set("notes")} /></Field>
    </div>
  );
}

const clean = (v: any) => { const o: any = {}; for (const [k, x] of Object.entries(v)) o[k] = x === "" ? null : x; return o; };

export function Directory() {
  const { perms, toast, toastError } = useApp();
  const [tab, setTab] = useState("clients");
  const [q, setQ] = useState("");
  const path = tab === "clients" ? "clients" : "companies";
  const { data, loading, reload } = useApi<any[]>(`/api/${path}${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  const [create, setCreate] = useState<any>(null);
  const nav = useNavigate();
  const save = async () => {
    try { const r = await api.post(`/api/${path}`, clean(create), create.name); toast("Fiche créée."); setCreate(null); r.__queued ? reload() : nav(`/annuaire/${tab === "clients" ? "clients" : "entreprises"}/${r.id}`); } catch (e) { toastError(e); }
  };
  return (
    <div>
      <PageHeader title="Clients et entreprises" icon={<Users size={22} />} subtitle="Maîtres d'ouvrage, entreprises, contacts, devis, marchés et historique."
        actions={perms.write && <button className="btn-primary" onClick={() => setCreate(tab === "clients" ? { kind: "particulier", contacts: [] } : { specialties: [], contacts: [] })}><Plus size={16} /> {tab === "clients" ? "Nouveau client" : "Nouvelle entreprise"}</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "clients", label: "Clients" }, { id: "entreprises", label: "Entreprises" }]} />
      <input className="input w-72 mb-4" placeholder="Rechercher…" value={q} onChange={(e) => setQ(e.target.value)} />
      {loading && !data ? <Spinner /> : !data?.length ? <Empty title="Aucune fiche" /> : (
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">{data.map((c) => (
          <Link key={c.id} to={`/annuaire/${tab === "clients" ? "clients" : "entreprises"}/${c.id}`} className="card p-4 hover:border-sage transition">
            <div className="flex items-center gap-2">{tab === "clients" ? <User size={16} className="text-sage" /> : <Building2 size={16} className="text-sage" />}<span className="font-medium truncate">{c.name}</span>
              {c.rating && <span className="ml-auto text-xs text-warn flex items-center">{c.rating}<Star size={11} fill="currentColor" /></span>}</div>
            <div className="text-xs text-muted mt-1">{tab === "clients" ? KINDS[c.kind] : (c.specialties || []).join(" · ") || "Spécialités non renseignées"}</div>
            <div className="text-xs text-muted mt-1">{[c.city, c.phone, c.email].filter(Boolean).join(" · ") || "—"}</div>
          </Link>))}</div>)}
      <Modal open={!!create} onClose={() => setCreate(null)} title={tab === "clients" ? "Nouveau client" : "Nouvelle entreprise"} wide
        footer={<><button className="btn-secondary" onClick={() => setCreate(null)}>Annuler</button><AsyncButton disabled={!create?.name?.trim()} onClick={save}>Créer</AsyncButton></>}>
        {create && <EntityForm kind={tab === "clients" ? "client" : "company"} value={create} onChange={setCreate} />}
      </Modal>
    </div>
  );
}

function Detail({ kind }: { kind: "client" | "company" }) {
  const { id } = useParams();
  const { perms, toast, toastError } = useApp();
  const path = kind === "client" ? "clients" : "companies";
  const { data, loading, error, reload } = useApi<any>(`/api/${path}/${id}`);
  const rel = useApi<any>(`/api/${path}/${id}/related`);
  const fe = useEditable<any>(data);
  const f = fe.value;
  const setF = fe.setValue;
  const [tab, setTab] = useState("fiche");
  const [del, setDel] = useState(false);
  const [note, setNote] = useState("");
  const nav = useNavigate();
  if (loading && !data) return <Spinner />;
  if (error || !f) return <ErrorBox error={error} />;
  const save = async (patch?: any) => {
    try { await api.put(`/api/${path}/${id}`, clean({ ...f, ...(patch || {}) }), f.name); fe.markSaved(); toast("Fiche enregistrée."); reload(); return true; }
    catch (e: any) { if (e.status === 409) { toast("Conflit : fiche modifiée par ailleurs, rechargée.", "error"); reload(); } else toastError(e); return false; }
  };
  const r = rel.data || {};
  return (
    <div>
      <PageHeader title={f.name} icon={kind === "client" ? <User size={22} /> : <Building2 size={22} />} subtitle={kind === "client" ? KINDS[f.kind] : (f.specialties || []).join(" · ")}
        actions={<><Link className="btn-secondary" to="/annuaire">← Annuaire</Link>{perms.delete && <button className="btn-ghost text-danger" onClick={() => setDel(true)}><Trash2 size={15} /></button>}</>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "fiche", label: "Fiche" }, { id: "projets", label: `Projets (${r.projects?.length || 0})` },
        ...(kind === "company" ? [{ id: "devis", label: `Devis (${r.quotes?.length || 0})` }, { id: "marches", label: `Marchés (${(r.lots?.length || 0) + (r.markets?.length || 0)})` }] : []),
        { id: "documents", label: `Documents (${r.documents?.length || 0})` }, { id: "historique", label: "Historique" }]} />
      {tab === "fiche" && <Card actions={perms.write && <AsyncButton onClick={() => save()} disabled={!f.name?.trim()}><Save size={15} /> Enregistrer</AsyncButton>}><StaleNotice stale={fe.stale} onDiscard={fe.discard} /><EntityForm kind={kind} value={f} onChange={setF} disabled={!perms.write} /></Card>}
      {tab === "projets" && <Card pad={false}>{!r.projects?.length ? <Empty title="Aucun projet associé" /> : <table className="table"><tbody>{r.projects.map((p: any) => <tr key={p.id}><td><Link className="hover:text-sage font-medium" to={`/projets/${p.id}`}>{p.code} – {p.name}</Link></td><td>{STATUS_PROJECT[p.status]}</td><td className="text-right">{eur(p.budget_initial, 0)}</td></tr>)}</tbody></table>}</Card>}
      {tab === "devis" && <Card pad={false}>{!r.quotes?.length ? <Empty title="Aucun devis" /> : <table className="table"><thead><tr><th>Référence</th><th>Projet</th><th>Date</th><th className="text-right">Total HT</th><th>Statut</th></tr></thead>
        <tbody>{r.quotes.map((q: any) => <tr key={q.id}><td><Link className="hover:text-sage" to={`/devis/${q.id}`}>{q.reference || "—"}</Link></td><td>{q.project}</td><td>{dateFr(q.quote_date)}</td><td className="text-right tabular-nums">{eur(q.computed?.total_ht)}</td><td>{QUOTE_STATUS[q.status]}</td></tr>)}</tbody></table>}</Card>}
      {tab === "marches" && <Card pad={false}>{!r.lots?.length && !r.markets?.length ? <Empty title="Aucun marché" /> : <table className="table"><thead><tr><th>Objet</th><th>Projet</th><th className="text-right">Montant HT</th></tr></thead>
        <tbody>{r.lots.map((l: any) => <tr key={l.id}><td>Lot {l.code} – {l.name} (attributaire)</td><td>{l.project}</td><td className="text-right tabular-nums">{eur(l.contract_amount)}</td></tr>)}
          {r.markets.map((m: any) => <tr key={m.id}><td>{m.label}</td><td /><td className="text-right tabular-nums">{eur(m.amount_ht)}</td></tr>)}</tbody></table>}</Card>}
      {tab === "documents" && <Card pad={false}>{!r.documents?.length ? <Empty title="Aucun document lié" /> : <ul className="divide-y divide-line">{r.documents.map((d: any) => <li key={d.id} className="px-5 py-2 text-sm"><Link className="hover:text-sage" to={`/documents?doc=${d.id}`}>{d.name}</Link></li>)}</ul>}</Card>}
      {tab === "historique" && (
        <Card title="Historique des échanges">
          {perms.write && <div className="flex gap-2 mb-3"><input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ajouter une note (appel, courrier, réunion…)" />
            <AsyncButton disabled={!note.trim()} onClick={async () => { const ok = await save({ history: [{ date: new Date().toISOString(), text: note.trim() }, ...(f.history || [])] }); if (ok) setNote(""); }}>Ajouter</AsyncButton></div>}
          <ul className="space-y-2">{(f.history || []).map((h: any, i: number) => <li key={i} className="text-sm"><span className="text-muted text-xs">{dateFr(h.date)}</span> — {h.text}</li>)}</ul>
          {!f.history?.length && <div className="text-sm text-muted">Aucune note.</div>}
        </Card>)}
      <Confirm open={del} onClose={() => setDel(false)} title="Supprimer la fiche" message={`Supprimer « ${f.name} » ?`} onConfirm={async () => { try { await api.del(`/api/${path}/${id}`); nav("/annuaire"); } catch (e) { toastError(e); } }} />
    </div>
  );
}

export const ClientDetail = () => <Detail kind="client" />;
export const CompanyDetail = () => <Detail kind="company" />;
