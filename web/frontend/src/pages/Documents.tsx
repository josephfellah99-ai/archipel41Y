import { Files, Upload, Download, Eye, History, Search, Lock, Trash2, RefreshCw, Archive } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, blobUrl, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { bytes, dateFr, dateTimeFr, DOC_CATEGORIES } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Select, Spinner, Tabs, useDebounced, AsyncButton } from "../components/ui";

const PREVIEWABLE = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "txt", "md", "csv"]);
const TEXT_STATUS: Record<string, string> = { ok: "Texte extrait", ocr: "Texte extrait par OCR", vide: "Aucun texte", non_supporte: "Format non analysé", erreur: "Erreur d'extraction", en_attente: "En attente" };

function PageImage({ docId, n, version }: { docId: string; n: number; version?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let u: string | null = null;
    blobUrl(`/api/documents/${docId}/page/${n}?scale=1.6${version ? `&version=${version}` : ""}`).then((x) => { u = x; setUrl(x); }).catch(() => {});
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [docId, n, version]);
  return url ? <img src={url} alt={`Page ${n}`} className="w-full rounded-md border border-line bg-white shadow-sm" loading="lazy" />
    : <div className="aspect-[1/1.41] w-full rounded-md bg-sunken animate-pulse" />;
}

/** Aperçu PDF rendu par le serveur, page par page (indépendant de la visionneuse du navigateur). */
export function PdfPages({ docId, version, className = "" }: { docId: string; version?: number; className?: string }) {
  const [count, setCount] = useState<number | null>(null);
  const [shown, setShown] = useState(4);
  useEffect(() => { api.get(`/api/documents/${docId}/pages${version ? `?version=${version}` : ""}`).then((r: any) => setCount(r.pages)).catch(() => setCount(0)); }, [docId, version]);
  if (count === null) return <Spinner />;
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: Math.min(count, shown) }, (_, i) => <div key={i}><div className="text-[10px] text-muted mb-1">Page {i + 1} / {count}</div><PageImage docId={docId} n={i + 1} version={version} /></div>)}
      {count > shown && <button className="btn-secondary w-full" onClick={() => setShown(shown + 6)}>Afficher les pages suivantes ({count - shown})</button>}
    </div>
  );
}

export function DocPreview({ doc, version }: { doc: any; version?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ext = (doc.extension || "").toLowerCase();
  useEffect(() => {
    let u: string | null = null;
    setUrl(null); setText(null); setErr(null);
    const v = version ? `&version=${version}` : "";
    if (ext === "pdf") return;
    if (PREVIEWABLE.has(ext) && !["txt", "md", "csv"].includes(ext)) {
      blobUrl(`/api/documents/${doc.id}/download?inline=true${v}`).then((x) => { u = x; setUrl(x); }).catch((e) => setErr(e.message));
    } else {
      api.get(`/api/documents/${doc.id}/text${version ? `?version=${version}` : ""}`).then((r: any) => setText(r.text || "")).catch((e) => setErr(e.message));
    }
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [doc.id, version, ext]);
  if (ext === "pdf") return <div className="max-h-[70vh] overflow-y-auto scrollbar-thin pr-1"><PdfPages docId={doc.id} version={version} /></div>;
  if (err) return <ErrorBox error={err} />;
  if (url) return ext === "pdf" ? <iframe title={doc.name} src={url} className="w-full h-[70vh] rounded-lg border border-line bg-white" />
    : <img src={url} alt={doc.name} className="max-h-[70vh] mx-auto rounded-lg" />;
  if (text !== null) return (
    <div>
      {["dwg", "dxf", "ifc", "pln", "pla", "rvt", "skp"].includes(ext) &&
        <Notice>Fichier de CAO/BIM ({ext.toUpperCase()}) : conservé, versionné et téléchargeable. Ouvrez-le avec votre logiciel métier (ArchiCAD, AutoCAD, Revit, visionneuse IFC…).</Notice>}
      <pre className="whitespace-pre-wrap text-xs bg-sunken rounded-lg p-4 max-h-[65vh] overflow-auto scrollbar-thin mt-2">{text || "Aucun texte extrait pour ce document."}</pre>
    </div>
  );
  return <Spinner />;
}

function DocModal({ doc, onClose, onChanged }: { doc: any; onClose: () => void; onChanged: () => void }) {
  const { perms, toast, toastError, projects } = useApp();
  const full = useApi<any>(`/api/documents/${doc.id}`);
  const hist = useApi<any[]>(`/api/documents/${doc.id}/history`);
  const [tab, setTab] = useState("apercu");
  const [ver, setVer] = useState<number | undefined>();
  const [meta, setMeta] = useState<any>({ name: doc.name, category: doc.category, tags: (doc.tags || []).join(", "), project_id: doc.project_id || "", confidential: doc.confidential, description: doc.description || "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const saveMeta = async () => {
    try {
      await api.call("PUT", `/api/documents/${doc.id}`, { ...meta, project_id: meta.project_id || null, tags: meta.tags.split(",").map((t: string) => t.trim()).filter(Boolean), version: full.data?.version });
      toast("Document mis à jour."); onChanged(); full.reload();
    } catch (e) { toastError(e); }
  };
  const newVersion = async (f: File) => {
    const fd = new FormData(); fd.append("file", f);
    try { await api.upload(`/api/documents/${doc.id}/versions`, fd); toast("Nouvelle version ajoutée."); full.reload(); hist.reload(); onChanged(); } catch (e) { toastError(e); }
  };
  return (
    <Modal open onClose={onClose} title={doc.name} wide footer={<>
      {perms.delete && <button className="btn-ghost text-danger mr-auto" onClick={async () => { await api.del(`/api/documents/${doc.id}`); onChanged(); onClose(); }}><Trash2 size={15} /> Supprimer</button>}
      <button className="btn-secondary" onClick={() => download(`/api/documents/${doc.id}/download${ver ? `?version=${ver}` : ""}`).catch(toastError)}><Download size={15} /> Télécharger</button>
      {perms.write && <><input ref={fileRef} type="file" hidden onChange={(e) => e.target.files?.[0] && newVersion(e.target.files[0])} />
        <button className="btn-primary" onClick={() => fileRef.current?.click()}><Upload size={15} /> Nouvelle version</button></>}</>}>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "apercu", label: "Aperçu" }, { id: "infos", label: "Classement" }, { id: "versions", label: `Versions (${full.data?.versions?.length || doc.current_version})` }, { id: "historique", label: "Historique" }]} />
      {tab === "apercu" && <DocPreview doc={doc} version={ver} />}
      {tab === "infos" && (
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Nom" className="sm:col-span-2"><input className="input" disabled={!perms.write} value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} /></Field>
          <Field label="Catégorie"><Select disabled={!perms.write} value={meta.category} onChange={(v) => setMeta({ ...meta, category: v })} options={Object.entries(DOC_CATEGORIES).map(([v, l]) => ({ value: v, label: l }))} /></Field>
          <Field label="Projet"><Select disabled={!perms.write} value={meta.project_id} onChange={(v) => setMeta({ ...meta, project_id: v })} placeholder="— Documents de l'agence —" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} /></Field>
          <Field label="Mots-clés (séparés par des virgules)" className="sm:col-span-2"><input className="input" disabled={!perms.write} value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} /></Field>
          <Field label="Description" className="sm:col-span-2"><textarea className="input" disabled={!perms.write} value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} /></Field>
          <label className="text-sm flex items-center gap-2 sm:col-span-2"><input type="checkbox" disabled={!perms.write} checked={meta.confidential} onChange={(e) => setMeta({ ...meta, confidential: e.target.checked })} /> Document confidentiel (jamais transmis à un fournisseur d'IA externe sans autorisation de l'administrateur)</label>
          <div className="text-xs text-muted sm:col-span-2">Analyse du contenu : {TEXT_STATUS[doc.text_status] || doc.text_status} {doc.page_count ? `· ${doc.page_count} page(s)` : ""}
            {perms.write && <button className="text-sage ml-2" onClick={async () => { try { await api.call("POST", `/api/documents/${doc.id}/reindex`); toast("Document réindexé."); } catch (e) { toastError(e); } }}><RefreshCw size={11} className="inline" /> Réindexer</button>}</div>
          {perms.write && <div className="sm:col-span-2"><AsyncButton onClick={saveMeta}>Enregistrer le classement</AsyncButton></div>}
        </div>
      )}
      {tab === "versions" && (full.data ? (
        <table className="table"><thead><tr><th>Version</th><th>Fichier</th><th>Taille</th><th>Date</th><th>Commentaire</th><th /></tr></thead>
          <tbody>{full.data.versions.map((v: any) => (
            <tr key={v.id}><td>v{v.number}{v.number === full.data.current_version && <span className="chip bg-ok/15 text-ok ml-1">actuelle</span>}</td><td>{v.filename}</td><td>{bytes(v.size)}</td><td>{dateTimeFr(v.created_at)}</td><td className="text-muted">{v.comment || ""}</td>
              <td className="whitespace-nowrap">{v.has_file ? <><button className="btn-ghost p-1" onClick={() => { setVer(v.number); setTab("apercu"); }} title="Aperçu"><Eye size={14} /></button>
                <button className="btn-ghost p-1" onClick={() => download(`/api/documents/${doc.id}/download?version=${v.number}`).catch(toastError)} title="Télécharger"><Download size={14} /></button></> : <span className="text-xs text-warn">non synchronisé</span>}</td></tr>))}</tbody></table>) : <Spinner />)}
      {tab === "historique" && <ul className="space-y-2">{(hist.data || []).map((h, i) => <li key={i} className="text-sm"><span className="font-medium">{h.user}</span> · {h.op} · <span className="text-muted">{dateTimeFr(h.at)}</span>
        {h.changes && <span className="text-xs text-muted"> — {Object.keys(h.changes).join(", ")}</span>}</li>)}</ul>}
    </Modal>
  );
}

export function DocumentsTable({ projectId }: { projectId?: string | null }) {
  const { perms, toast, toastError } = useApp();
  const [params] = useSearchParams();
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [conf, setConf] = useState(false);
  const [open, setOpen] = useState<any>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const qs = new URLSearchParams({ ...(projectId ? { project_id: projectId } : {}), ...(cat ? { category: cat } : {}), ...(dq ? { q: dq } : {}) });
  const { data, loading, error, reload } = useApi<any[]>(`/api/documents?${qs}`);
  useEffect(() => { const d = params.get("doc"); if (d && data) { const x = data.find((y) => y.id === d); if (x) setOpen(x); } }, [params, data]);
  const upload = async (files: File[]) => {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (projectId) fd.append("project_id", projectId);
    if (cat) fd.append("category", cat);
    fd.append("confidential", String(conf));
    setBusy(true);
    try {
      const r = await api.upload("/api/documents/upload", fd);
      const warn = r.extraction.filter((x: any) => x.warnings.length);
      toast(`${r.documents.length} document(s) importé(s)${warn.length ? ` – ${warn.length} avec avertissement(s)` : ""}.`);
      reload();
    } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  return (
    <Card pad={false} title={`${data?.length ?? 0} document(s)`} actions={<div className="flex flex-wrap gap-2 items-center">
      {sel.size > 0 && <button className="btn-secondary" onClick={() => download("/api/documents/export", "documents_archipel41.zip", { ids: [...sel] }).catch(toastError)}><Archive size={15} /> Exporter ({sel.size})</button>}
      {perms.write && <><label className="text-xs flex items-center gap-1.5"><input type="checkbox" checked={conf} onChange={(e) => setConf(e.target.checked)} /> Confidentiel</label>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => { upload(Array.from(e.target.files || [])); e.target.value = ""; }} />
        <button className="btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}><Upload size={15} /> {busy ? "Import…" : "Importer"}</button></>}
    </div>}>
      <div className="px-5 pb-3 flex flex-wrap gap-2">
        <div className="relative"><Search size={14} className="absolute left-3 top-2.5 text-muted" /><input className="input pl-8 w-72" placeholder="Nom, description ou contenu…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select className="w-48" value={cat} onChange={setCat} placeholder="Toutes catégories" options={Object.entries(DOC_CATEGORIES).map(([v, l]) => ({ value: v, label: l }))} />
      </div>
      <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); perms.write && upload(Array.from(e.dataTransfer.files)); }}>
        <ErrorBox error={error} />
        {loading && !data ? <Spinner /> : !data?.length ? <Empty title="Aucun document" icon={<Files size={18} />}>Glissez-déposez des fichiers ici : PDF, Word, Excel, images, DWG, DXF, IFC, PLN, PLA…</Empty> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th className="w-8" /><th>Nom</th><th>Catégorie</th><th>Version</th><th>Taille</th><th>Modifié</th><th>Contenu</th><th /></tr></thead>
            <tbody>{data.map((d) => (
              <tr key={d.id} className="hover:bg-sunken/50">
                <td><input type="checkbox" checked={sel.has(d.id)} onChange={() => setSel((s) => { const n = new Set(s); n.has(d.id) ? n.delete(d.id) : n.add(d.id); return n; })} aria-label="Sélectionner" /></td>
                <td className="cursor-pointer" onClick={() => setOpen(d)}><span className="chip bg-sunken text-muted uppercase mr-2">{d.extension}</span><span className="font-medium hover:text-sage">{d.name}</span>{d.confidential && <Lock size={12} className="inline ml-1 text-muted" />}
                  {(d.tags || []).length > 0 && <div className="flex gap-1 mt-1">{d.tags.map((t: string) => <span key={t} className="chip bg-sage/10 text-sage">{t}</span>)}</div>}</td>
                <td>{DOC_CATEGORIES[d.category] || d.category}</td><td>v{d.current_version}</td><td className="text-muted">{bytes(d.size)}</td><td className="text-muted">{dateFr(d.updated_at)}</td>
                <td className="text-xs text-muted">{TEXT_STATUS[d.text_status] || d.text_status}</td>
                <td className="whitespace-nowrap"><button className="btn-ghost p-1" onClick={() => setOpen(d)} title="Ouvrir"><Eye size={15} /></button>
                  <button className="btn-ghost p-1" onClick={() => download(`/api/documents/${d.id}/download`).catch(toastError)} title="Télécharger"><Download size={15} /></button></td>
              </tr>))}</tbody>
          </table></div>)}
      </div>
      {open && <DocModal doc={open} onClose={() => setOpen(null)} onChanged={reload} />}
    </Card>
  );
}

function SemanticSearch() {
  const { projectId } = useApp();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    try { setRes(await api.get(`/api/documents/search?q=${encodeURIComponent(q)}${projectId ? `&project_id=${projectId}` : ""}`)); } finally { setBusy(false); }
  };
  return (
    <Card title="Recherche dans le contenu des documents">
      <form onSubmit={run} className="flex gap-2 mb-3"><input className="input" placeholder="ex. classe d'exposition du béton, hauteur maximale en zone UB…" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn-primary" disabled={busy}><Search size={15} /> Rechercher</button></form>
      <p className="text-xs text-muted mb-3">Recherche hybride (sémantique + mots-clés) dans le texte extrait de tous les documents accessibles, y compris les documents scannés passés à l'OCR.</p>
      {busy ? <Spinner /> : res && (res.length === 0 ? <Empty title="Aucun passage pertinent" /> : (
        <ul className="space-y-3">{res.map((r, i) => (
          <li key={i} className="rounded-lg border border-line p-3"><div className="text-sm font-medium">{r.document} {r.page && <span className="text-muted font-normal">· page {r.page}</span>}<span className="text-xs text-muted float-right">pertinence {Math.round(r.score * 100)} %</span></div>
            <div className="text-sm text-ink/80 mt-1 whitespace-pre-wrap line-clamp-5">{r.text}</div></li>))}</ul>))}
    </Card>
  );
}

export default function Documents() {
  const { projectId, projects } = useApp();
  const [scope, setScope] = useState<"projet" | "tous">(projectId ? "projet" : "tous");
  useEffect(() => { setScope(projectId ? "projet" : "tous"); }, [projectId]);
  const p = projects.find((x) => x.id === projectId);
  return (
    <div>
      <PageHeader title="Documents" icon={<Files size={22} />} subtitle="Bibliothèque documentaire : classement, versions, prévisualisation, recherche et exports."
        actions={projectId && <Select className="w-64" value={scope} onChange={(v) => setScope(v as any)} options={[{ value: "projet", label: `Projet ${p?.code || ""}` }, { value: "tous", label: "Toute l'agence" }]} />} />
      <div className="space-y-6">
        <DocumentsTable projectId={scope === "projet" ? projectId : null} />
        <SemanticSearch />
      </div>
    </div>
  );
}
