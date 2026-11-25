import {
  FileSpreadsheet, Upload, Scale, CheckCircle2, AlertTriangle, Trash2, Plus, Save, RefreshCw, Sparkles, Download, FileText, Building2, Eye, Filter,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, blobUrl, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { CMP_STATUS, dateFr, eur, LINE_STATUS, num, parseNum, QUOTE_STATUS } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Markdown, Modal, Notice, PageHeader, Select, Spinner, Tabs } from "../components/ui";
import { PdfPages } from "./Documents";

export function NeedProject({ what }: { what: string }) {
  const { projects, setProjectId } = useApp();
  return (
    <div className="card p-8 max-w-xl mx-auto text-center">
      <div className="font-medium">Sélectionnez un projet</div>
      <p className="text-sm text-muted mt-1 mb-4">{what} se rattache à un projet. Choisissez-le ci-dessous ou dans le sélecteur en haut de l'écran.</p>
      <Select value="" onChange={(v) => setProjectId(v || null)} placeholder="— Choisir un projet —" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} />
    </div>
  );
}

function Dropzone({ onFiles, accept, label }: { onFiles: (f: File[]) => void; accept?: string; label: string }) {
  const [over, setOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(Array.from(e.dataTransfer.files)); }}
      onClick={() => ref.current?.click()} role="button" tabIndex={0}
      className={`rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition ${over ? "border-sage bg-sage/10" : "border-line hover:border-sage"}`}>
      <Upload className="mx-auto text-muted" size={22} />
      <div className="text-sm font-medium mt-2">{label}</div>
      <div className="text-xs text-muted mt-1">Glissez-déposez ou cliquez · PDF (natifs ou scannés), JPG, PNG, XLS, XLSX, CSV, DOC, DOCX, ZIP</div>
      <input ref={ref} type="file" multiple hidden accept={accept} onChange={(e) => { onFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
    </div>
  );
}

function Totals({ q }: { q: any }) {
  const c = q.computed || {};
  const rows = [["Total HT", c.total_ht, q.declared_ht], ["TVA", c.total_tva, q.declared_tva], ["Total TTC", c.total_ttc, q.declared_ttc]];
  return (
    <table className="table">
      <thead><tr><th></th><th className="text-right">Recalculé (moteur)</th><th className="text-right">Déclaré (devis)</th><th className="text-right">Écart</th></tr></thead>
      <tbody>
        {rows.map(([l, a, b]: any) => {
          const gap = a !== undefined && b !== null && b !== undefined ? Math.round((b - a) * 100) / 100 : null;
          return <tr key={l}><td className="font-medium">{l}</td><td className="text-right tabular-nums">{eur(a)}</td><td className="text-right tabular-nums">{eur(b)}</td>
            <td className={`text-right tabular-nums ${gap && Math.abs(gap) > 1 ? "text-danger font-medium" : "text-muted"}`}>{gap === null ? "—" : eur(gap)}</td></tr>;
        })}
        {(c.by_rate || []).map((r: any) => <tr key={r.rate}><td className="text-muted">dont TVA {String(r.rate).replace(".", ",")} %</td><td className="text-right tabular-nums text-muted">base {eur(r.base)} → {eur(r.tva)}</td><td /><td /></tr>)}
        {c.options_ht > 0 && <tr><td className="text-muted">Options (non comprises)</td><td className="text-right tabular-nums">{eur(c.options_ht)}</td><td /><td /></tr>}
        {c.variants_ht > 0 && <tr><td className="text-muted">Variantes (non comprises)</td><td className="text-right tabular-nums">{eur(c.variants_ht)}</td><td /><td /></tr>}
        {c.to_check_ht > 0 && <tr><td className="text-muted">Lignes à vérifier (non comprises)</td><td className="text-right tabular-nums">{eur(c.to_check_ht)}</td><td /><td /></tr>}
      </tbody>
    </table>
  );
}

function Specs({ projectId, lotId, lots }: { projectId: string; lotId: string; lots: any[] }) {
  const { perms, toast, toastError } = useApp();
  const dp = useApi<any[]>(`/api/dpgf-items?project_id=${projectId}${lotId ? `&lot_id=${lotId}` : ""}`);
  const cc = useApi<any[]>(`/api/cctp?project_id=${projectId}${lotId ? `&lot_id=${lotId}` : ""}`);
  const [busy, setBusy] = useState(false);
  const upload = async (kind: "dpgf" | "cctp", files: File[]) => {
    if (!files[0]) return;
    const fd = new FormData();
    fd.append("file", files[0]);
    fd.append("project_id", projectId);
    if (lotId) fd.append("lot_id", lotId);
    setBusy(true);
    try {
      const r = await api.upload(`/api/${kind}/import`, fd);
      toast(`${kind.toUpperCase()} importé : ${r.count} ${kind === "dpgf" ? "ligne(s)" : "article(s)"} reconnu(s).`);
      kind === "dpgf" ? dp.reload() : cc.reload();
    } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  const lotName = lots.find((l) => l.id === lotId);
  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card title={`DPGF ${lotName ? `– Lot ${lotName.code}` : "(tous lots)"}`} actions={<span className="text-xs text-muted">{dp.data?.length || 0} ligne(s)</span>}>
        {perms.write && <div className="mb-3"><Dropzone label={busy ? "Import en cours…" : "Importer la DPGF (Excel, CSV ou PDF)"} onFiles={(f) => upload("dpgf", f)} /></div>}
        {!dp.data?.length ? <Empty title="Aucune DPGF">La DPGF sert de référence au comparateur (quantités, unités, prix estimés).</Empty> : (
          <div className="overflow-x-auto max-h-96 scrollbar-thin"><table className="table">
            <thead><tr><th>N°</th><th>Désignation</th><th>U</th><th className="text-right">Qté</th><th className="text-right">PU estimé</th><th>CCTP</th></tr></thead>
            <tbody>{dp.data.map((d) => <tr key={d.id}><td>{d.code}</td><td>{d.designation}</td><td>{d.unit}</td><td className="text-right tabular-nums">{num(d.quantity)}</td>
              <td className="text-right tabular-nums">{eur(d.estimated_unit_price)}</td><td className="text-muted">{d.cctp_ref}</td></tr>)}</tbody>
          </table></div>)}
      </Card>
      <Card title={`CCTP ${lotName ? `– Lot ${lotName.code}` : "(tous lots)"}`} actions={<span className="text-xs text-muted">{cc.data?.length || 0} article(s)</span>}>
        {perms.write && <div className="mb-3"><Dropzone label={busy ? "Import en cours…" : "Importer le CCTP (PDF ou Word)"} onFiles={(f) => upload("cctp", f)} /></div>}
        {!cc.data?.length ? <Empty title="Aucun CCTP analysé">Les articles et exigences techniques (classes de béton, DTU, épaisseurs…) sont repérés pour contrôler les offres.</Empty> : (
          <ul className="divide-y divide-line max-h-96 overflow-y-auto scrollbar-thin">{cc.data.map((r) => (
            <li key={r.id} className="py-2"><div className="text-sm font-medium">Art. {r.article} – {r.title}</div>
              <div className="flex flex-wrap gap-1 mt-1">{(r.keywords || []).map((k: string) => <span key={k} className="chip bg-sunken text-muted">{k}</span>)}</div></li>))}</ul>)}
      </Card>
    </div>
  );
}

export function QuotesPage() {
  const { projectId, perms, toast, toastError } = useApp();
  const [lotId, setLotId] = useState("");
  const [tab, setTab] = useState("devis");
  const lots = useApi<any[]>(projectId ? `/api/lots?project_id=${projectId}` : null);
  const quotes = useApi<any[]>(projectId ? `/api/quotes?project_id=${projectId}${lotId ? `&lot_id=${lotId}` : ""}` : null);
  const cmps = useApi<any[]>(projectId ? `/api/comparisons?project_id=${projectId}` : null);
  const ai = useApi<any>("/api/assistant/status");
  const [importLot, setImportLot] = useState("");
  const [method, setMethod] = useState("regles");
  const [busy, setBusy] = useState<string | null>(null);
  const [report, setReport] = useState<any[] | null>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [useAi, setUseAi] = useState(false);
  const nav = useNavigate();
  useEffect(() => { setImportLot(lotId); }, [lotId]);
  if (!projectId) return <><PageHeader title="Devis et comparateur intelligent" icon={<FileSpreadsheet size={22} />} /><NeedProject what="L'analyse des devis" /></>;
  const lotMap = Object.fromEntries((lots.data || []).map((l) => [l.id, l]));
  const doImport = async (files: File[]) => {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("project_id", projectId);
    if (importLot) fd.append("lot_id", importLot);
    fd.append("method", method);
    setBusy(`Analyse de ${files.length} fichier(s) : lecture, OCR si nécessaire, reconnaissance des tableaux…`);
    try {
      const r = await api.upload<any[]>("/api/quotes/import", fd);
      setReport(r);
      toast(`${r.length} devis importé(s) – vérifiez et corrigez les données extraites avant validation.`);
      quotes.reload();
    } catch (e) { toastError(e); } finally { setBusy(null); }
  };
  const compareNow = async () => {
    setBusy("Comparaison des offres…");
    try {
      const r = await api.call("POST", "/api/comparisons", { project_id: projectId, lot_id: lotId || null, quote_ids: [...sel], use_ai: useAi });
      nav(`/comparatifs/${r.id}`);
    } catch (e) { toastError(e); } finally { setBusy(null); }
  };
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  return (
    <div>
      <PageHeader title="Devis et comparateur intelligent" icon={<FileSpreadsheet size={22} />}
        subtitle="Importez les offres, corrigez les données extraites, comparez-les à la DPGF et au CCTP."
        actions={<Select className="w-64" value={lotId} onChange={setLotId} placeholder="Tous les lots" options={(lots.data || []).map((l) => ({ value: l.id, label: `Lot ${l.code} – ${l.name}` }))} />} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "devis", label: `Devis (${quotes.data?.length || 0})` }, { id: "ref", label: "DPGF et CCTP" }, { id: "cmp", label: `Comparatifs (${cmps.data?.length || 0})` }]} />
      {busy && <div className="mb-4"><Notice><span className="flex items-center gap-2"><RefreshCw size={14} className="animate-spin" /> {busy}</span></Notice></div>}
      {tab === "devis" && (
        <div className="space-y-6">
          {perms.write && (
            <Card title="Importer des devis">
              <div className="grid sm:grid-cols-3 gap-3 mb-3">
                <Field label="Lot concerné"><Select value={importLot} onChange={setImportLot} placeholder="— Non précisé —" options={(lots.data || []).map((l) => ({ value: l.id, label: `Lot ${l.code} – ${l.name}` }))} /></Field>
                <Field label="Méthode d'extraction" hint={method === "ia" ? "Le texte du devis est transmis au fournisseur d'IA configuré." : "Moteur de règles local : aucune donnée ne quitte l'agence."}>
                  <Select value={method} onChange={setMethod} options={[{ value: "regles", label: "Moteur de règles (local)" }, ...(ai.data?.available ? [{ value: "ia", label: "Assistant IA (" + ai.data.provider + ")" }] : [])]} /></Field>
              </div>
              <Dropzone label="Déposer un ou plusieurs devis" onFiles={doImport} />
              {report && <div className="mt-4 space-y-1.5">{report.map((r) => (
                <div key={r.quote.id} className="text-sm flex flex-wrap items-center gap-2">
                  <CheckCircle2 size={15} className="text-ok" /><span className="font-medium">{r.extraction.filename}</span>
                  <span className="text-muted">· {r.extraction.method} · {r.quote.lines.length} ligne(s) · {eur(r.quote.computed.total_ht)} HT</span>
                  {r.extraction.ocr_used && <span className="chip bg-warn/15 text-warn">OCR</span>}
                  {r.quote.anomalies.length > 0 && <span className="chip bg-danger/15 text-danger">{r.quote.anomalies.length} anomalie(s)</span>}
                  <Link className="text-sage text-xs" to={`/devis/${r.quote.id}`}>Vérifier →</Link>
                </div>))}</div>}
            </Card>
          )}
          <Card title="Devis du projet" actions={perms.write && sel.size >= 2 && (
            <div className="flex items-center gap-3">
              <label className="text-xs flex items-center gap-1.5" title={ai.data?.available ? "" : "Aucun fournisseur d'IA configuré : conclusion par le moteur de règles"}>
                <input type="checkbox" checked={useAi} disabled={!ai.data?.available} onChange={(e) => setUseAi(e.target.checked)} /> Conclusion rédigée par l'IA</label>
              <button className="btn-primary" onClick={compareNow}><Scale size={15} /> Comparer {sel.size} offres</button>
            </div>)} pad={false}>
            {quotes.loading && !quotes.data ? <Spinner /> : !quotes.data?.length ? <Empty title="Aucun devis importé">Déposez vos devis ci-dessus pour lancer l'extraction automatique.</Empty> : (
              <div className="overflow-x-auto"><table className="table">
                <thead><tr><th className="w-8"></th><th>Entreprise</th><th>Référence</th><th>Date</th><th>Lot</th><th className="text-right">Total HT recalculé</th><th>Contrôle</th><th>Fiabilité</th><th>Statut</th></tr></thead>
                <tbody>{quotes.data.map((q) => {
                  const high = (q.anomalies || []).filter((a: any) => a.severity === "haute").length;
                  return (
                    <tr key={q.id} className="hover:bg-sunken/50">
                      <td><input type="checkbox" checked={sel.has(q.id)} onChange={() => toggle(q.id)} aria-label="Sélectionner pour comparaison" /></td>
                      <td><Link className="font-medium hover:text-sage" to={`/devis/${q.id}`}>{q.company_name || <span className="text-warn">Entreprise non identifiée</span>}</Link></td>
                      <td className="text-muted">{q.reference || "—"}</td><td className="text-muted">{dateFr(q.quote_date)}</td>
                      <td>{q.lot_id ? `Lot ${lotMap[q.lot_id]?.code || ""}` : "—"}</td>
                      <td className="text-right tabular-nums font-medium">{eur(q.computed?.total_ht)}</td>
                      <td>{high ? <span className="chip bg-danger/15 text-danger"><AlertTriangle size={11} /> {high} anomalie(s)</span> : <span className="chip bg-ok/15 text-ok">Cohérent</span>}</td>
                      <td className="text-xs text-muted">{q.extraction?.confidence ? `${Math.round(q.extraction.confidence * 100)} %` : "—"}{(q.extraction?.method || "").includes("ocr") ? " · OCR" : ""}</td>
                      <td><span className={`chip ${q.status === "valide" || q.status === "retenu" ? "bg-ok/15 text-ok" : q.status === "rejete" ? "bg-danger/15 text-danger" : "bg-warn/15 text-warn"}`}>{QUOTE_STATUS[q.status]}</span></td>
                    </tr>);
                })}</tbody>
              </table></div>)}
          </Card>
        </div>
      )}
      {tab === "ref" && <Specs projectId={projectId} lotId={lotId} lots={lots.data || []} />}
      {tab === "cmp" && (
        <Card title="Comparatifs enregistrés" pad={false}>
          {!cmps.data?.length ? <Empty title="Aucun comparatif">Sélectionnez au moins deux devis dans l'onglet « Devis » puis cliquez sur « Comparer ».</Empty> : (
            <table className="table"><thead><tr><th>Titre</th><th>Entreprises</th><th>Date</th><th>Conclusion</th></tr></thead>
              <tbody>{cmps.data.map((c) => <tr key={c.id} className="hover:bg-sunken/50 cursor-pointer" onClick={() => nav(`/comparatifs/${c.id}`)}>
                <td className="font-medium">{c.title}</td><td className="text-muted">{c.companies.join(", ")}</td><td>{dateFr(c.created_at)}</td>
                <td>{c.conclusion_source === "moteur_regles" ? "Moteur de règles" : "IA + moteur de règles"}</td></tr>)}</tbody></table>)}
        </Card>
      )}
    </div>
  );
}

function ListEditor({ label, items, onChange, disabled }: { label: string; items: string[]; onChange: (v: string[]) => void; disabled?: boolean }) {
  const [v, setV] = useState("");
  return (
    <div>
      <div className="label">{label}</div>
      <ul className="space-y-1">{items.map((it, i) => (
        <li key={i} className="flex items-start gap-2 text-sm bg-sunken rounded-md px-2.5 py-1.5"><span className="flex-1">{it}</span>
          {!disabled && <button className="text-muted hover:text-danger" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label="Retirer"><Trash2 size={13} /></button>}</li>))}
        {!items.length && <li className="text-xs text-muted">Aucun élément détecté.</li>}</ul>
      {!disabled && <div className="flex gap-2 mt-1.5"><input className="input py-1" value={v} onChange={(e) => setV(e.target.value)} placeholder="Ajouter…"
        onKeyDown={(e) => { if (e.key === "Enter" && v.trim()) { onChange([...items, v.trim()]); setV(""); } }} />
        <button className="btn-secondary py-1" onClick={() => { if (v.trim()) { onChange([...items, v.trim()]); setV(""); } }}><Plus size={14} /></button></div>}
    </div>
  );
}

export function QuoteReview() {
  const { id } = useParams();
  const { perms, toast, toastError } = useApp();
  const { data: q, loading, error, reload, setData } = useApi<any>(`/api/quotes/${id}`);
  const companies = useApi<any[]>("/api/companies");
  const ai = useApi<any>("/api/assistant/status");
  const [lines, setLines] = useState<any[]>([]);
  const [head, setHead] = useState<any>(null);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [showDoc, setShowDoc] = useState(true);
  const [busy, setBusy] = useState(false);
  const dpgf = useApi<any[]>(q ? `/api/dpgf-items?project_id=${q.project_id}${q.lot_id ? `&lot_id=${q.lot_id}` : ""}` : null);
  useEffect(() => {
    if (!q) return;
    setLines(q.lines.map((l: any) => ({ ...l })));
    setHead({ company_id: q.company_id || "", reference: q.reference || "", quote_date: q.quote_date || "", delay_text: q.delay_text || "", delay_days: q.delay_days ?? "",
      validity_days: q.validity_days ?? "", payment_terms: q.payment_terms || "", conditions: q.conditions || [], exclusions: q.exclusions || [], reserves: q.reserves || [],
      variants: q.variants || [], declared_ht: q.declared_ht ?? "", declared_tva: q.declared_tva ?? "", declared_ttc: q.declared_ttc ?? "", notes: q.notes || "", status: q.status });
    setDirty(false);
  }, [q]);
  const [docExt, setDocExt] = useState("");
  const [docText, setDocText] = useState("");
  useEffect(() => {
    if (!q?.document_id) return;
    api.get(`/api/documents/${q.document_id}`).then((d: any) => setDocExt(d.extension || "")).catch(() => {});
    api.get(`/api/documents/${q.document_id}/text`).then((d: any) => setDocText(d.text || "")).catch(() => {});
  }, [q?.document_id]);
  useEffect(() => {
    let url: string | null = null;
    if (q?.document_id) blobUrl(`/api/documents/${q.document_id}/download?inline=true`).then((u) => { url = u; setPreview(u); }).catch(() => setPreview(null));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [q?.document_id]);
  const canEdit = perms.write;
  const upd = (i: number, k: string, v: any) => { setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l))); setDirty(true); };
  const liveTotal = useMemo(() => lines.reduce((s, l) => {
    if (l.status !== "inclus") return s;
    const qn = parseNum(String(l.quantity ?? "")), pu = parseNum(String(l.unit_price ?? "")), t = parseNum(String(l.total_ht ?? ""));
    return s + (qn !== null && pu !== null ? Math.round(qn * pu * 100) / 100 : t ?? 0);
  }, 0), [lines]);
  const saveAll = async () => {
    setBusy(true);
    try {
      const h = { ...head, company_id: head.company_id || null, quote_date: head.quote_date || null };
      for (const k of ["delay_days", "validity_days", "declared_ht", "declared_tva", "declared_ttc"]) h[k] = h[k] === "" ? null : parseNum(String(h[k]));
      let r = await api.call("PUT", `/api/quotes/${id}`, { ...h, version: q.version });
      r = await api.call("PUT", `/api/quotes/${id}/lines`, { lines });
      setData(r);
      toast("Corrections enregistrées – totaux recalculés par le moteur déterministe.");
    } catch (e: any) {
      if (e.status === 409) { toast("Conflit : le devis a été modifié par ailleurs, il a été rechargé.", "error"); reload(); } else toastError(e);
    } finally { setBusy(false); }
  };
  const action = async (path: string, msg: string) => {
    setBusy(true);
    try { setData(await api.call("POST", path)); toast(msg); } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  if (loading && !q) return <Spinner />;
  if (error || !q || !head) return <ErrorBox error={error} />;
  const anomalies = q.anomalies || [];
  return (
    <div>
      <PageHeader title={q.company_name || "Devis – entreprise non identifiée"} icon={<FileSpreadsheet size={22} />}
        subtitle={<>Devis {q.reference || "sans référence"} · {dateFr(q.quote_date)} · extraction « {q.extraction?.method} » · fiabilité {Math.round((q.extraction?.confidence || 0) * 100)} %</>}
        actions={<>
          <Link className="btn-secondary" to="/devis">← Devis du projet</Link>
          {q.document_id && <button className="btn-secondary" onClick={() => setShowDoc(!showDoc)}><Eye size={15} /> {showDoc ? "Masquer" : "Afficher"} le document</button>}
          {canEdit && <button className="btn-secondary" disabled={busy} onClick={() => action(`/api/quotes/${id}/reextract?method=regles`, "Extraction relancée (moteur de règles).")}><RefreshCw size={15} /> Ré-extraire</button>}
          {canEdit && ai.data?.available && <button className="btn-secondary" disabled={busy} onClick={() => action(`/api/quotes/${id}/reextract?method=ia`, "Extraction relancée par l'IA – vérifiez chaque ligne.")}><Sparkles size={15} /> Extraire avec l'IA</button>}
          {canEdit && <button className="btn-primary" disabled={busy || !dirty} onClick={saveAll}><Save size={15} /> Enregistrer les corrections</button>}
          {perms.validate && <button className="btn-primary" disabled={busy || dirty} title={dirty ? "Enregistrez d'abord vos corrections" : ""} onClick={() => action(`/api/quotes/${id}/validate`, "Devis validé.")}><CheckCircle2 size={15} /> Valider</button>}
        </>} />
      {(q.extraction?.warnings || []).length > 0 && <div className="mb-4"><Notice tone="warn"><ul className="list-disc pl-4">{q.extraction.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul></Notice></div>}
      <div className={`grid gap-6 ${showDoc && preview ? "xl:grid-cols-[1fr_minmax(380px,40%)]" : ""}`}>
        <div className="space-y-6 min-w-0">
          <div className={`grid gap-6 ${showDoc && preview ? "2xl:grid-cols-2" : "lg:grid-cols-2"}`}>
            <Card title="Totaux et contrôle des calculs"><Totals q={q} />
              {dirty && <div className="text-xs text-info mt-2">Aperçu du total HT des lignes incluses après vos corrections : <b>{eur(liveTotal)}</b> (enregistrez pour recalculer TVA et contrôles).</div>}</Card>
            <Card title={`Anomalies détectées (${anomalies.length})`}>
              {!anomalies.length ? <div className="text-sm text-ok flex items-center gap-2"><CheckCircle2 size={16} /> Aucune anomalie : calculs, totaux et taux de TVA cohérents.</div> : (
                <ul className="space-y-2">{anomalies.map((a: any, i: number) => (
                  <li key={i} className="text-sm flex gap-2"><span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${a.severity === "haute" ? "bg-danger" : a.severity === "moyenne" ? "bg-warn" : "bg-info"}`} />
                    <span>{a.message}{a.designation && <span className="text-muted"> — {a.designation}</span>}</span></li>))}</ul>)}
            </Card>
          </div>
          <Card title="Informations générales">
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <Field label="Entreprise" className="sm:col-span-2" hint={!head.company_id && q.company_name_raw ? <>Détectée : « {q.company_name_raw} » — {canEdit && <button className="text-sage underline" onClick={() => action(`/api/quotes/${id}/create-company`, "Fiche entreprise créée.")}>créer la fiche</button>}</> : undefined}>
                <Select disabled={!canEdit} value={head.company_id} onChange={(v) => { setHead({ ...head, company_id: v }); setDirty(true); }} placeholder="— Non rattachée —" options={(companies.data || []).map((c) => ({ value: c.id, label: c.name }))} /></Field>
              <Field label="Référence"><input className="input" disabled={!canEdit} value={head.reference} onChange={(e) => { setHead({ ...head, reference: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Date du devis"><input className="input" type="date" disabled={!canEdit} value={head.quote_date} onChange={(e) => { setHead({ ...head, quote_date: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Délai annoncé" className="sm:col-span-2"><input className="input" disabled={!canEdit} value={head.delay_text} onChange={(e) => { setHead({ ...head, delay_text: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Délai (jours calendaires)"><input className="input" disabled={!canEdit} value={head.delay_days} onChange={(e) => { setHead({ ...head, delay_days: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Validité (jours)"><input className="input" disabled={!canEdit} value={head.validity_days} onChange={(e) => { setHead({ ...head, validity_days: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Total HT déclaré"><input className="input" disabled={!canEdit} value={head.declared_ht} onChange={(e) => { setHead({ ...head, declared_ht: e.target.value }); setDirty(true); }} /></Field>
              <Field label="TVA déclarée"><input className="input" disabled={!canEdit} value={head.declared_tva} onChange={(e) => { setHead({ ...head, declared_tva: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Total TTC déclaré"><input className="input" disabled={!canEdit} value={head.declared_ttc} onChange={(e) => { setHead({ ...head, declared_ttc: e.target.value }); setDirty(true); }} /></Field>
              <Field label="Statut"><Select disabled={!perms.validate} value={head.status} onChange={(v) => { setHead({ ...head, status: v }); setDirty(true); }} options={Object.entries(QUOTE_STATUS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
              <Field label="Conditions de paiement" className="sm:col-span-2 lg:col-span-4"><input className="input" disabled={!canEdit} value={head.payment_terms} onChange={(e) => { setHead({ ...head, payment_terms: e.target.value }); setDirty(true); }} /></Field>
            </div>
            <div className="grid md:grid-cols-2 gap-4 mt-4">
              <ListEditor label="Exclusions (expressément non comprises)" items={head.exclusions} disabled={!canEdit} onChange={(v) => { setHead({ ...head, exclusions: v }); setDirty(true); }} />
              <ListEditor label="Réserves" items={head.reserves} disabled={!canEdit} onChange={(v) => { setHead({ ...head, reserves: v }); setDirty(true); }} />
              <ListEditor label="Conditions particulières" items={head.conditions} disabled={!canEdit} onChange={(v) => { setHead({ ...head, conditions: v }); setDirty(true); }} />
              <ListEditor label="Variantes proposées" items={head.variants} disabled={!canEdit} onChange={(v) => { setHead({ ...head, variants: v }); setDirty(true); }} />
            </div>
          </Card>
          <Card title={`Lignes extraites (${lines.length})`} pad={false} actions={canEdit && <button className="btn-secondary" onClick={() => { setLines([...lines, { designation: "", status: "inclus", quantity: "", unit: "", unit_price: "", total_ht: "", vat_rate: q.computed?.by_rate?.[0]?.rate ?? 20 }]); setDirty(true); }}><Plus size={15} /> Ligne</button>}>
            <div className="overflow-x-auto scrollbar-thin"><table className="table text-xs">
              <thead><tr><th>N°</th><th className="min-w-[260px]">Désignation</th><th>Qté</th><th>U</th><th>PU HT</th><th>Montant HT</th><th>TVA %</th><th>Statut</th><th>DPGF</th><th>Fiab.</th><th></th></tr></thead>
              <tbody>{lines.map((l, i) => {
                const qn = parseNum(String(l.quantity ?? "")), pu = parseNum(String(l.unit_price ?? "")), t = parseNum(String(l.total_ht ?? ""));
                const calc = qn !== null && pu !== null ? Math.round(qn * pu * 100) / 100 : null;
                const mismatch = calc !== null && t !== null && Math.abs(calc - t) > 0.02;
                return (
                  <tr key={l.id || `n${i}`} className={l.confidence !== undefined && l.confidence < 0.7 && !l.corrected ? "bg-warn/5" : ""} title={l.raw || ""}>
                    <td><input className="input py-1 w-14" disabled={!canEdit} value={l.code || ""} onChange={(e) => upd(i, "code", e.target.value)} /></td>
                    <td><textarea rows={1} className="input py-1 min-h-[30px]" disabled={!canEdit} value={l.designation} onChange={(e) => upd(i, "designation", e.target.value)} />
                      {l.section && <div className="text-[10px] text-muted mt-0.5">{l.section}</div>}</td>
                    <td><input className="input py-1 w-16 text-right" disabled={!canEdit} value={l.quantity ?? ""} onChange={(e) => upd(i, "quantity", e.target.value)} /></td>
                    <td><input className="input py-1 w-12" disabled={!canEdit} value={l.unit || ""} onChange={(e) => upd(i, "unit", e.target.value)} /></td>
                    <td><input className="input py-1 w-20 text-right" disabled={!canEdit} value={l.unit_price ?? ""} onChange={(e) => upd(i, "unit_price", e.target.value)} /></td>
                    <td><input className={`input py-1 w-24 text-right ${mismatch ? "border-danger text-danger" : ""}`} disabled={!canEdit} value={l.total_ht ?? ""} onChange={(e) => upd(i, "total_ht", e.target.value)} />
                      {mismatch && <div className="text-[10px] text-danger">calcul : {num(calc)}</div>}</td>
                    <td><input className="input py-1 w-14 text-right" disabled={!canEdit} value={l.vat_rate ?? ""} onChange={(e) => upd(i, "vat_rate", e.target.value)} /></td>
                    <td><Select className="py-1 w-28" disabled={!canEdit} value={l.status} onChange={(v) => upd(i, "status", v)} options={Object.entries(LINE_STATUS).map(([v, lb]) => ({ value: v, label: lb }))} /></td>
                    <td><Select className="py-1 w-36" disabled={!canEdit} value={l.dpgf_item_id || ""} onChange={(v) => upd(i, "dpgf_item_id", v || null)} placeholder="Auto" options={(dpgf.data || []).map((d) => ({ value: d.id, label: `${d.code || ""} ${d.designation}`.slice(0, 50) }))} /></td>
                    <td className="text-muted whitespace-nowrap">{l.corrected ? <span className="text-ok">corrigée</span> : l.confidence !== undefined && l.confidence !== null ? `${Math.round(l.confidence * 100)} %` : ""}</td>
                    <td>{canEdit && <button className="text-muted hover:text-danger" onClick={() => { setLines(lines.filter((_, j) => j !== i)); setDirty(true); }} aria-label="Supprimer la ligne"><Trash2 size={14} /></button>}</td>
                  </tr>);
              })}</tbody>
            </table></div>
            <div className="px-5 py-3 text-xs text-muted border-t border-line">Survolez une ligne pour voir le texte source. Les lignes surlignées ont une fiabilité d'extraction inférieure à 70 %. Statut « Exclu » : uniquement pour une prestation expressément exclue par l'entreprise.</div>
          </Card>
        </div>
        {showDoc && preview && (
          <div className="card overflow-hidden xl:sticky xl:top-4 h-[80vh]">
            {docExt.toLowerCase() === "pdf" ? <div className="h-full overflow-y-auto scrollbar-thin p-3"><PdfPages docId={q.document_id} /></div>
              : ["png", "jpg", "jpeg", "webp", "gif"].includes(docExt.toLowerCase())
              ? <div className="h-full overflow-auto p-3"><img src={preview} alt="Document source" className="w-full" /></div>
              : <div className="p-4 overflow-auto h-full"><div className="text-xs text-muted mb-2">Texte extrait du document source</div><pre className="text-xs whitespace-pre-wrap">{docText}</pre></div>}
          </div>
        )}
      </div>
    </div>
  );
}

export function ComparisonView() {
  const { id } = useParams();
  const { toast, toastError, perms } = useApp();
  const { data: c, loading, error } = useApi<any>(`/api/comparisons/${id}`);
  const [filter, setFilter] = useState("tous");
  const [showPU, setShowPU] = useState(false);
  const [tab, setTab] = useState("tableau");
  const nav = useNavigate();
  if (loading && !c) return <Spinner />;
  if (error || !c) return <ErrorBox error={error} />;
  const r = c.result;
  const S = r.summaries;
  const rank = Object.fromEntries(r.ranking.map((x: any) => [x.quote_id, x]));
  const rows = r.rows.filter((row: any) => {
    const st = S.map((s: any) => row.cells[s.quote_id].status);
    if (filter === "ecarts") return S.some((s: any) => row.cells[s.quote_id].flag) || new Set(st).size > 1;
    if (filter === "manquants") return st.some((x: string) => ["non_renseigne", "non_inclus"].includes(x));
    if (filter === "verifier") return st.some((x: string) => ["a_verifier", "non_comparable"].includes(x));
    return true;
  });
  const exp = async (fmt: string) => { try { await download(`/api/comparisons/${id}/export?fmt=${fmt}`); } catch (e) { toastError(e); } };
  const report = async () => {
    try { const rep = await api.call("POST", "/api/reports", { kind: "devis", fmt: "pdf", comparison_id: id }); toast("Rapport PDF généré et classé dans les documents du projet."); await download(rep.download_url); } catch (e) { toastError(e); }
  };
  return (
    <div>
      <PageHeader title={c.title} icon={<Scale size={22} />} subtitle={`${S.length} offres · ${r.has_reference ? "référence : DPGF du projet" : "référence : offre la plus détaillée (pas de DPGF)"} · ${dateFr(c.created_at)}`}
        actions={<>
          <button className="btn-secondary" onClick={() => nav("/devis")}>← Devis</button>
          <button className="btn-secondary" onClick={() => exp("xlsx")}><Download size={15} /> Excel</button>
          <button className="btn-secondary" onClick={() => exp("csv")}>CSV</button>
          <button className="btn-secondary" onClick={() => exp("docx")}>Word</button>
          {perms.write && <button className="btn-primary" onClick={report}><FileText size={15} /> Rapport PDF</button>}
        </>} />
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
        {r.ranking.map((x: any) => {
          const s = S.find((y: any) => y.quote_id === x.quote_id);
          return (
            <div key={x.quote_id} className={`card p-4 ${x.rank === 1 ? "ring-2 ring-sage" : ""}`}>
              <div className="flex items-center gap-2"><span className="chip bg-forest text-white dark:text-bg">#{x.rank}</span><Building2 size={14} className="text-muted" /><span className="text-sm font-medium truncate">{s.company}</span></div>
              <div className="text-2xl font-semibold mt-2 tabular-nums">{eur(s.total_ht, 0)} <span className="text-xs font-normal text-muted">HT</span></div>
              <div className="text-xs text-muted">Périmètre comparable : {eur(s.adjusted_ht, 0)} · délai {s.delay_days ? `${s.delay_days} j` : "n.c."}</div>
              <div className="flex flex-wrap gap-1 mt-2">
                <span className="chip bg-ok/15 text-ok">{s.counts.inclus} inclus</span>
                {s.counts.non_renseigne > 0 && <span className="chip bg-warn/15 text-warn">{s.counts.non_renseigne} non renseigné(s)</span>}
                {s.counts.non_inclus > 0 && <span className="chip bg-danger/15 text-danger">{s.counts.non_inclus} exclu(s)</span>}
                {s.anomalies > 0 && <span className="chip bg-danger/15 text-danger">{s.anomalies} anomalie(s)</span>}
              </div>
              <div className="text-xs mt-2 text-muted">Score {x.score}/100 — prix {x.details.prix} · complétude {x.details.completude} · risques {x.details.risques} · délai {x.details.delai}</div>
            </div>);
        })}
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "tableau", label: "Tableau comparatif" }, { id: "conclusion", label: "Conclusion argumentée" }, { id: "cctp", label: `Contrôle CCTP (${r.cctp.length})` }, { id: "offres", label: "Conditions des offres" }]} />
      {tab === "tableau" && (
        <Card pad={false} title={<span className="flex items-center gap-2"><Filter size={14} /> {rows.length} prestation(s)</span>}
          actions={<div className="flex items-center gap-3">
            <label className="text-xs flex items-center gap-1.5"><input type="checkbox" checked={showPU} onChange={(e) => setShowPU(e.target.checked)} /> Prix unitaires</label>
            <Select className="py-1 w-56" value={filter} onChange={setFilter} options={[{ value: "tous", label: "Toutes les prestations" }, { value: "ecarts", label: "Écarts et divergences" }, { value: "manquants", label: "Non renseignés / exclus" }, { value: "verifier", label: "À vérifier / non comparables" }]} />
          </div>}>
          <div className="overflow-x-auto scrollbar-thin"><table className="table text-xs">
            <thead><tr><th>N°</th><th className="min-w-[240px]">Prestation</th><th>U</th><th className="text-right">Qté réf.</th>
              {S.map((s: any) => <th key={s.quote_id} className="text-right min-w-[150px]">{s.company}</th>)}<th className="text-right">Médiane</th></tr></thead>
            <tbody>{rows.map((row: any) => (
              <tr key={row.key} className={row.extra ? "bg-sunken/40" : ""}>
                <td className="text-muted">{row.code}</td>
                <td>{row.designation}{row.extra && <div className="text-[10px] text-muted">Hors référence – proposé par {row.origin}</div>}</td>
                <td>{row.unit}</td><td className="text-right tabular-nums">{num(row.quantity)}</td>
                {S.map((s: any) => {
                  const cell = row.cells[s.quote_id];
                  const st = CMP_STATUS[cell.status];
                  return (
                    <td key={s.quote_id} className="text-right" title={[cell.designation ? `Libellé de l'offre : ${cell.designation}` : "", cell.note || ""].filter(Boolean).join("\n")}>
                      <div className={`tabular-nums ${row.is_min === s.quote_id ? "font-semibold text-ok" : ""}`}>{cell.amount !== null && cell.amount !== undefined ? eur(cell.amount) : ""}</div>
                      {showPU && cell.unit_price !== null && cell.unit_price !== undefined && <div className="text-[10px] text-muted">{num(cell.quantity)} × {eur(cell.unit_price)}</div>}
                      <div className="flex justify-end gap-1 mt-0.5 flex-wrap">
                        {cell.status !== "inclus" && <span className={`chip ${st.cls}`}>{st.label}</span>}
                        {cell.deviation !== null && cell.deviation !== undefined && Math.abs(cell.deviation) >= 0.05 &&
                          <span className={`chip ${cell.flag ? "bg-danger/15 text-danger" : "bg-sunken text-muted"}`}>{cell.deviation > 0 ? "+" : ""}{Math.round(cell.deviation * 100)} %</span>}
                      </div>
                    </td>);
                })}
                <td className="text-right tabular-nums text-muted">{eur(row.median)}</td>
              </tr>))}
              <tr className="font-semibold bg-sunken/60"><td /><td>Total HT (lignes incluses, recalculé)</td><td /><td />
                {S.map((s: any) => <td key={s.quote_id} className="text-right tabular-nums">{eur(s.total_ht)}</td>)}<td /></tr>
              <tr className="bg-sunken/60"><td /><td>Montant à périmètre comparable (estimation)</td><td /><td />
                {S.map((s: any) => <td key={s.quote_id} className="text-right tabular-nums">{eur(s.adjusted_ht)}</td>)}<td /></tr>
            </tbody>
          </table></div>
          <div className="px-5 py-3 border-t border-line flex flex-wrap gap-2 text-xs">{Object.entries(CMP_STATUS).map(([k, v]) => <span key={k} className={`chip ${v.cls}`}>{v.label}</span>)}
            <span className="text-muted">· Survolez une cellule pour le libellé exact de l'offre. « Non renseigné » ≠ « Non inclus » : une absence n'est jamais assimilée à une exclusion.</span></div>
        </Card>
      )}
      {tab === "conclusion" && <Card><Markdown text={c.conclusion || ""} /><div className="text-xs text-muted mt-3">Source : {c.conclusion_source === "moteur_regles" ? "moteur de règles d'Archipel41 (calculs déterministes)" : "assistant IA à partir des faits calculés, suivi de la conclusion du moteur de règles"}.</div></Card>}
      {tab === "cctp" && (
        <Card pad={false}>{!r.cctp.length ? <Empty title="Aucun CCTP importé">Importez le CCTP dans l'onglet « DPGF et CCTP » pour contrôler la mention des exigences techniques.</Empty> : (
          <div className="overflow-x-auto"><table className="table text-xs"><thead><tr><th>Article</th><th>Exigences repérées</th>{S.map((s: any) => <th key={s.quote_id}>{s.company}</th>)}</tr></thead>
            <tbody>{r.cctp.map((x: any) => <tr key={x.article}><td className="font-medium">{x.article} {x.title}</td><td className="text-muted">{[...x.specs, ...x.references].join(", ") || "—"}</td>
              {S.map((s: any) => { const v = x.quotes[s.quote_id]; return <td key={s.quote_id}><span className={`chip ${v.status === "mentionne" ? "bg-ok/15 text-ok" : v.status === "absent" ? "bg-danger/15 text-danger" : "bg-warn/15 text-warn"}`}>{v.status === "mentionne" ? "Mentionné" : v.status === "absent" ? "Ouvrage absent" : "À vérifier"}</span>
                {v.missing.length > 0 && <div className="text-[10px] text-muted mt-0.5">Non cité : {v.missing.join(", ")}</div>}</td>; })}</tr>)}</tbody></table></div>)}
        </Card>
      )}
      {tab === "offres" && (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{S.map((s: any) => (
          <Card key={s.quote_id} title={s.company}>
            <div className="text-sm space-y-2">
              <div><span className="text-muted">Délai :</span> {s.delay_text || "non renseigné"}</div>
              <div><span className="text-muted">Validité :</span> {s.validity_days ? `${s.validity_days} jours` : "non renseignée"}</div>
              <div><div className="text-muted">Exclusions :</div>{s.exclusions.length ? <ul className="list-disc pl-5">{s.exclusions.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul> : <div className="text-xs text-muted">Aucune</div>}</div>
              <div><div className="text-muted">Réserves :</div>{s.reserves.length ? <ul className="list-disc pl-5">{s.reserves.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul> : <div className="text-xs text-muted">Aucune</div>}</div>
              <div><div className="text-muted">Écarts de prix inhabituels :</div>{s.unusual.length ? <ul className="list-disc pl-5">{s.unusual.map((u: any, i: number) => <li key={i}>{u.designation} ({u.deviation > 0 ? "+" : ""}{Math.round(u.deviation * 100)} %)</li>)}</ul> : <div className="text-xs text-muted">Aucun</div>}</div>
              <Link className="text-sage text-xs" to={`/devis/${s.quote_id}`}>Voir et corriger le devis →</Link>
            </div>
          </Card>))}</div>
      )}
    </div>
  );
}
