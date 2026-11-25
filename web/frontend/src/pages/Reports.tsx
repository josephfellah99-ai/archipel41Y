import { FileText, Download } from "lucide-react";
import { useState } from "react";
import { api, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateTimeFr } from "../lib/format";
import { Card, Empty, Field, Notice, PageHeader, Select } from "../components/ui";

const KINDS = [
  { code: "devis", label: "Rapport d'analyse des devis", needs: "comparison", desc: "Synthèse des offres, tableau comparatif coloré, contrôle CCTP, conclusion argumentée." },
  { code: "urbanisme", label: "Rapport urbanistique et de faisabilité", needs: "analysis", desc: "Zonage, servitudes, risques, extraits du règlement, indicateurs, sources et incertitudes." },
  { code: "chantier", label: "Rapport de chantier", needs: "project", desc: "Planning, avancement attendu/réel, retards, lots et entreprises, incidents." },
  { code: "compte_rendu", label: "Compte rendu de réunion", needs: "event", desc: "Objet, participants, ordre du jour, compte rendu, documents associés." },
  { code: "financier", label: "Rapport financier", needs: "project", desc: "Budgets, marchés, TS, facturation, paiements, écarts par lot, alertes." },
  { code: "synthese", label: "Synthèse de projet", needs: "project", desc: "Fiche projet, phases, devis, finances et chantier en un seul document." },
];
const FORMATS = [{ value: "pdf", label: "PDF" }, { value: "xlsx", label: "Excel (XLSX)" }, { value: "docx", label: "Word (DOCX)" }, { value: "csv", label: "CSV" }];

export default function Reports() {
  const { projectId, projects, perms, toast, toastError } = useApp();
  const [kind, setKind] = useState("synthese");
  const [fmt, setFmt] = useState("pdf");
  const [pid, setPid] = useState(projectId || "");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const k = KINDS.find((x) => x.code === kind)!;
  const cmps = useApi<any[]>(k.needs === "comparison" ? `/api/comparisons${pid ? `?project_id=${pid}` : ""}` : null, [kind]);
  const analyses = useApi<any[]>(k.needs === "analysis" ? "/api/urbanisme/analyses" : null, [kind]);
  const events = useApi<any[]>(k.needs === "event" ? `/api/events${pid ? `?project_id=${pid}` : ""}` : null, [kind]);
  const list = useApi<any[]>(`/api/reports${pid ? `?project_id=${pid}` : ""}`);
  const options = k.needs === "comparison" ? (cmps.data || []).map((c) => ({ value: c.id, label: c.title }))
    : k.needs === "analysis" ? (analyses.data || []).map((a) => ({ value: a.id, label: a.label || a.query }))
    : k.needs === "event" ? (events.data || []).map((e) => ({ value: e.id, label: `${new Date(e.start).toLocaleDateString("fr-FR")} – ${e.title}` })) : [];
  const ready = k.needs === "project" ? !!pid : !!target;
  const gen = async () => {
    setBusy(true);
    try {
      const body: any = { kind, fmt };
      if (k.needs === "project") body.project_id = pid;
      if (k.needs === "comparison") body.comparison_id = target;
      if (k.needs === "analysis") body.analysis_id = target;
      if (k.needs === "event") body.event_id = target;
      const r = await api.call("POST", "/api/reports", body);
      toast("Rapport généré et classé dans les documents.");
      await download(r.download_url);
      list.reload();
    } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  return (
    <div>
      <PageHeader title="Rapports" icon={<FileText size={22} />} subtitle="Génération de rapports professionnels en PDF, XLSX, DOCX et CSV, aux couleurs de l'agence." />
      <div className="grid lg:grid-cols-[1fr_380px] gap-6">
        <div className="grid sm:grid-cols-2 gap-3">{KINDS.map((x) => (
          <button key={x.code} onClick={() => { setKind(x.code); setTarget(""); }} className={`card p-4 text-left transition ${kind === x.code ? "ring-2 ring-sage" : "hover:border-sage"}`}>
            <div className="font-medium text-sm">{x.label}</div><div className="text-xs text-muted mt-1">{x.desc}</div></button>))}</div>
        <Card title="Paramètres du rapport">
          <div className="space-y-3">
            <Field label="Projet"><Select value={pid} onChange={(v) => { setPid(v); setTarget(""); }} placeholder="— Tous —" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} /></Field>
            {k.needs !== "project" && <Field label={k.needs === "comparison" ? "Comparatif" : k.needs === "analysis" ? "Analyse urbanistique" : "Rendez-vous"}>
              <Select value={target} onChange={setTarget} placeholder="— Choisir —" options={options} /></Field>}
            {k.needs !== "project" && !options.length && <Notice>{k.needs === "comparison" ? "Aucun comparatif : comparez d'abord des devis." : k.needs === "analysis" ? "Aucune analyse : lancez une recherche dans Urbanisme." : "Aucun rendez-vous pour ce projet."}</Notice>}
            <Field label="Format"><Select value={fmt} onChange={setFmt} options={FORMATS} /></Field>
            <button className="btn-primary w-full" disabled={!ready || busy || !perms.write} onClick={gen}><Download size={15} /> {busy ? "Génération…" : "Générer et télécharger"}</button>
          </div>
        </Card>
      </div>
      <div className="mt-6"><Card title="Rapports générés" pad={false}>
        {!list.data?.length ? <Empty title="Aucun rapport généré" /> : <table className="table"><thead><tr><th>Titre</th><th>Format</th><th>Date</th><th /></tr></thead>
          <tbody>{list.data.map((r) => <tr key={r.id}><td>{r.title}</td><td className="uppercase text-xs">{r.fmt}</td><td className="text-muted">{dateTimeFr(r.created_at)}</td>
            <td><button className="btn-ghost p-1" onClick={() => download(r.download_url).catch(toastError)} aria-label="Télécharger"><Download size={15} /></button></td></tr>)}</tbody></table>}
      </Card></div>
    </div>
  );
}
