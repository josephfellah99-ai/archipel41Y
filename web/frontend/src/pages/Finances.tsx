import { Wallet, Plus, Trash2, FileText } from "lucide-react";
import { useState } from "react";
import { api, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr, eur, FIN_STATUS, FINANCE_KINDS } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Select, Spinner, Stat, Tabs } from "../components/ui";

function LotBars({ lots }: { lots: any[] }) {
  const max = Math.max(1, ...lots.map((l) => Math.max(l.budget || 0, l.engage || 0)));
  return (
    <div className="space-y-3">
      {lots.map((l) => (
        <div key={l.lot_id}>
          <div className="flex justify-between text-xs mb-1"><span className="font-medium">Lot {l.code} – {l.name}</span>
            <span className={l.ecart > 0 ? "text-danger" : "text-muted"}>{eur(l.engage, 0)} / {eur(l.budget, 0)}{l.ecart_pct !== null ? ` (${l.ecart_pct > 0 ? "+" : ""}${l.ecart_pct} %)` : ""}</span></div>
          <div className="relative h-3 rounded-full bg-sunken overflow-hidden" title={`Budget ${eur(l.budget)} · engagé ${eur(l.engage)} · facturé ${eur(l.facture)}`}>
            <div className="absolute inset-y-0 left-0 bg-sand dark:bg-line" style={{ width: `${(l.budget / max) * 100}%` }} />
            <div className={`absolute inset-y-0 left-0 ${l.ecart > 0 ? "bg-danger/70" : "bg-sage"}`} style={{ width: `${(l.engage / max) * 100}%`, height: "50%" }} />
            <div className="absolute bottom-0 left-0 bg-forest" style={{ width: `${(l.facture / max) * 100}%`, height: "50%" }} />
          </div>
        </div>))}
      <div className="flex gap-4 text-[11px] text-muted"><span className="flex items-center gap-1"><span className="h-2 w-4 rounded bg-sand dark:bg-line" /> budget</span><span className="flex items-center gap-1"><span className="h-2 w-4 rounded bg-sage" /> engagé</span><span className="flex items-center gap-1"><span className="h-2 w-4 rounded bg-forest" /> facturé</span></div>
    </div>
  );
}

function EntryModal({ entry, projectId, lots, companies, onClose, onSaved }: any) {
  const { perms, toastError } = useApp();
  const [f, setF] = useState<any>(entry);
  const save = async () => {
    try {
      const body = { ...f, project_id: projectId, amount_ht: Number(String(f.amount_ht).replace(",", ".")), vat_rate: Number(f.vat_rate), lot_id: f.lot_id || null, company_id: f.company_id || null,
        due_date: f.due_date || null, amount_ttc: null, situation_number: f.situation_number ? Number(f.situation_number) : null, progress_percent: f.progress_percent ? Number(f.progress_percent) : null };
      if (f.id) await api.put(`/api/finance-entries/${f.id}`, body, f.label); else await api.post("/api/finance-entries", body, f.label);
      onSaved(); onClose();
    } catch (e) { toastError(e); }
  };
  return (
    <Modal open onClose={onClose} title={f.id ? f.label : "Nouvelle écriture"} footer={<>
      {f.id && perms.delete && <button className="btn-ghost text-danger mr-auto" onClick={async () => { await api.del(`/api/finance-entries/${f.id}`); onSaved(); onClose(); }}><Trash2 size={15} /> Supprimer</button>}
      <button className="btn-secondary" onClick={onClose}>Annuler</button>{perms.write && <button className="btn-primary" onClick={save} disabled={!f.label || f.amount_ht === ""}>Enregistrer</button>}</>}>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Nature"><Select value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={Object.entries(FINANCE_KINDS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Statut"><Select value={f.status} onChange={(v) => setF({ ...f, status: v })} options={Object.entries(FIN_STATUS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Libellé *" className="sm:col-span-2"><input className="input" value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} /></Field>
        <Field label="Lot"><Select value={f.lot_id || ""} onChange={(v) => setF({ ...f, lot_id: v })} placeholder="—" options={lots.map((l: any) => ({ value: l.id, label: `${l.code} ${l.name}` }))} /></Field>
        <Field label="Entreprise"><Select value={f.company_id || ""} onChange={(v) => setF({ ...f, company_id: v })} placeholder="—" options={companies.map((c: any) => ({ value: c.id, label: c.name }))} /></Field>
        <Field label="Montant HT (€) *"><input className="input" inputMode="decimal" value={f.amount_ht} onChange={(e) => setF({ ...f, amount_ht: e.target.value })} /></Field>
        <Field label="TVA (%)" hint="Le TTC est calculé par le moteur (arrondi au centime)."><Select value={String(f.vat_rate)} onChange={(v) => setF({ ...f, vat_rate: v })} options={["20", "10", "5.5", "2.1", "0"].map((v) => ({ value: v, label: `${v.replace(".", ",")} %` }))} /></Field>
        <Field label="Date"><input className="input" type="date" value={f.entry_date} onChange={(e) => setF({ ...f, entry_date: e.target.value })} /></Field>
        <Field label="Échéance"><input className="input" type="date" value={f.due_date || ""} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
        <Field label="Référence"><input className="input" value={f.reference || ""} onChange={(e) => setF({ ...f, reference: e.target.value })} /></Field>
        {f.kind === "situation" && <><Field label="N° de situation"><input className="input" value={f.situation_number || ""} onChange={(e) => setF({ ...f, situation_number: e.target.value })} /></Field>
          <Field label="Avancement cumulé (%)"><input className="input" value={f.progress_percent || ""} onChange={(e) => setF({ ...f, progress_percent: e.target.value })} /></Field></>}
        <Field label="Notes" className="sm:col-span-2"><textarea className="input" value={f.notes || ""} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
    </Modal>
  );
}

function ProjectFinances({ projectId }: { projectId: string }) {
  const { perms, toast, toastError } = useApp();
  const s = useApi<any>(`/api/projects/${projectId}/finances`);
  const entries = useApi<any[]>(`/api/finance-entries?project_id=${projectId}`);
  const blines = useApi<any[]>(`/api/budget-lines?project_id=${projectId}`);
  const lots = useApi<any[]>(`/api/lots?project_id=${projectId}`);
  const companies = useApi<any[]>("/api/companies");
  const [kind, setKind] = useState("");
  const [edit, setEdit] = useState<any>(null);
  const [tab, setTab] = useState("synthese");
  const reload = () => { s.reload(); entries.reload(); blines.reload(); };
  if (s.loading && !s.data) return <Spinner />;
  if (!s.data) return <ErrorBox error={s.error} />;
  const d = s.data;
  const company = Object.fromEntries((companies.data || []).map((c) => [c.id, c.name]));
  const rows = (entries.data || []).filter((e) => !kind || e.kind === kind);
  const saveBudget = async (b: any) => {
    try { await api.put(`/api/budget-lines/${b.id}`, { ...b, initial_amount: Number(b.initial_amount), current_amount: Number(b.current_amount) }, b.label); toast("Budget mis à jour."); reload(); } catch (e) { toastError(e); }
  };
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat label="Budget initial" value={eur(d.budget_initial, 0)} />
        <Stat label="Budget actualisé" value={eur(d.budget_actualise, 0)} />
        <Stat label="Engagé (marchés + TS)" value={eur(d.engage, 0)} hint={d.ecart_pct !== null ? `${d.ecart_pct > 0 ? "+" : ""}${d.ecart_pct} % vs budget` : undefined} />
        <Stat label="Facturé" value={eur(d.facture, 0)} hint={`dont situations ${eur(d.situations, 0)}`} />
        <Stat label="Payé" value={eur(d.paye, 0)} hint={`reste à payer ${eur(d.reste_a_payer, 0)}`} />
        <Stat label="Échéances dépassées" value={d.en_retard} tone="danger" />
      </div>
      {d.alerts.length > 0 && <Notice tone="warn"><ul className="list-disc pl-4">{d.alerts.map((a: any, i: number) => <li key={i}>{a.message}</li>)}</ul></Notice>}
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "synthese", label: "Synthèse par lot" }, { id: "ecritures", label: `Écritures (${entries.data?.length || 0})` }, { id: "budget", label: "Budget" }]} />
      {tab === "synthese" && <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Budget, engagements et facturation par lot">{d.by_lot.length ? <LotBars lots={d.by_lot} /> : <Empty title="Aucun lot" />}</Card>
        <Card title="Détail par lot (HT)" pad={false}><div className="overflow-x-auto"><table className="table text-xs">
          <thead><tr><th>Lot</th><th className="text-right">Budget</th><th className="text-right">Marché</th><th className="text-right">TS</th><th className="text-right">Facturé</th><th className="text-right">Écart</th></tr></thead>
          <tbody>{d.by_lot.map((l: any) => <tr key={l.lot_id}><td>{l.code} {l.name}<div className="text-muted">{l.company || "non attribué"}</div></td><td className="text-right tabular-nums">{eur(l.budget, 0)}</td>
            <td className="text-right tabular-nums">{eur(l.marche, 0)}</td><td className="text-right tabular-nums">{eur(l.travaux_supp, 0)}</td><td className="text-right tabular-nums">{eur(l.facture, 0)}</td>
            <td className={`text-right tabular-nums ${l.ecart > 0 ? "text-danger" : ""}`}>{eur(l.ecart, 0)}</td></tr>)}</tbody></table></div></Card>
      </div>}
      {tab === "ecritures" && (
        <Card pad={false} title={<Select className="py-1 w-56" value={kind} onChange={setKind} placeholder="Toutes les natures" options={Object.entries(FINANCE_KINDS).map(([v, l]) => ({ value: v, label: l }))} />}
          actions={perms.write && <button className="btn-primary" onClick={() => setEdit({ kind: kind || "facture", label: "", amount_ht: "", vat_rate: 20, entry_date: new Date().toISOString().slice(0, 10), status: "prevu" })}><Plus size={15} /> Écriture</button>}>
          {!rows.length ? <Empty title="Aucune écriture">Enregistrez marchés, avenants/TS, factures, acomptes, situations, paiements et dépenses.</Empty> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Date</th><th>Nature</th><th>Libellé</th><th>Entreprise</th><th className="text-right">HT</th><th className="text-right">TTC</th><th>Échéance</th><th>Statut</th></tr></thead>
              <tbody>{rows.map((e) => (
                <tr key={e.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => setEdit({ ...e })}>
                  <td>{dateFr(e.entry_date)}</td><td><span className="chip bg-sunken">{FINANCE_KINDS[e.kind]}</span></td><td>{e.label}{e.situation_number ? ` (n°${e.situation_number})` : ""}</td>
                  <td className="text-muted">{company[e.company_id] || "—"}</td><td className="text-right tabular-nums">{eur(e.amount_ht)}</td><td className="text-right tabular-nums">{eur(e.amount_ttc)}</td>
                  <td className={e.due_date && e.status !== "paye" && e.due_date < new Date().toISOString().slice(0, 10) ? "text-danger" : "text-muted"}>{dateFr(e.due_date)}</td>
                  <td><span className={`chip ${e.status === "paye" ? "bg-ok/15 text-ok" : e.status === "annule" ? "bg-sunken text-muted" : "bg-info/15 text-info"}`}>{FIN_STATUS[e.status]}</span></td></tr>))}</tbody></table></div>)}
        </Card>)}
      {tab === "budget" && (
        <Card title="Lignes budgétaires (HT)" pad={false} actions={perms.write && <button className="btn-secondary" onClick={async () => { await api.post("/api/budget-lines", { project_id: projectId, label: "Nouvelle ligne", initial_amount: 0, current_amount: 0 }); blines.reload(); }}><Plus size={15} /> Ligne</button>}>
          {!blines.data?.length ? <Empty title="Aucune ligne budgétaire">Sans ligne détaillée, le budget actualisé = budget initial du projet + travaux supplémentaires.</Empty> : (
            <table className="table"><thead><tr><th>Libellé</th><th className="text-right">Initial</th><th className="text-right">Actualisé</th><th className="text-right">Écart</th><th /></tr></thead>
              <tbody>{blines.data.map((b, i) => (
                <tr key={b.id}><td><input className="input py-1" disabled={!perms.write} value={b.label} onChange={(e) => blines.setData(blines.data!.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} /></td>
                  <td><input className="input py-1 text-right w-32 ml-auto" disabled={!perms.write} value={b.initial_amount} onChange={(e) => blines.setData(blines.data!.map((x, j) => (j === i ? { ...x, initial_amount: e.target.value } : x)))} /></td>
                  <td><input className="input py-1 text-right w-32 ml-auto" disabled={!perms.write} value={b.current_amount} onChange={(e) => blines.setData(blines.data!.map((x, j) => (j === i ? { ...x, current_amount: e.target.value } : x)))} /></td>
                  <td className="text-right tabular-nums">{eur(Number(b.current_amount) - Number(b.initial_amount), 0)}</td>
                  <td>{perms.write && <button className="btn-secondary py-1" onClick={() => saveBudget(b)}>OK</button>}</td></tr>))}</tbody></table>)}
        </Card>)}
      {edit && <EntryModal entry={edit} projectId={projectId} lots={lots.data || []} companies={companies.data || []} onClose={() => setEdit(null)} onSaved={reload} />}
    </div>
  );
}

export default function Finances() {
  const { projectId, setProjectId, perms, toastError } = useApp();
  const ov = useApi<any[]>("/api/finances/overview");
  return (
    <div>
      <PageHeader title="Finances" icon={<Wallet size={22} />} subtitle="Suivi budgétaire et financier des opérations (montants HT, TTC calculé par le moteur)."
        actions={projectId && perms.write && <button className="btn-secondary" onClick={async () => { try { const r = await api.call("POST", "/api/reports", { kind: "financier", fmt: "xlsx", project_id: projectId }); await download(r.download_url); } catch (e) { toastError(e); } }}><FileText size={15} /> Rapport financier (Excel)</button>} />
      {!projectId && (
        <Card title="Vue d'ensemble des projets" pad={false}>
          {!ov.data?.length ? <Empty title="Aucun projet" /> : <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>Projet</th><th className="text-right">Budget actualisé</th><th className="text-right">Engagé</th><th className="text-right">Facturé</th><th className="text-right">Payé</th><th className="text-right">Écart</th><th>Alertes</th></tr></thead>
            <tbody>{ov.data.map((p) => <tr key={p.project_id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => setProjectId(p.project_id)}>
              <td className="font-medium">{p.code} – {p.name}</td><td className="text-right tabular-nums">{eur(p.budget_actualise, 0)}</td><td className="text-right tabular-nums">{eur(p.engage, 0)}</td>
              <td className="text-right tabular-nums">{eur(p.facture, 0)}</td><td className="text-right tabular-nums">{eur(p.paye, 0)}</td>
              <td className={`text-right tabular-nums ${p.ecart_pct > 0 ? "text-danger" : ""}`}>{p.ecart_pct === null ? "—" : `${p.ecart_pct} %`}</td><td>{p.alerts || ""}</td></tr>)}</tbody></table></div>}
        </Card>)}
      {projectId && <ProjectFinances projectId={projectId} />}
    </div>
  );
}
