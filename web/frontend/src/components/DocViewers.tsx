import { CheckCircle2, Circle, Layers, Minus, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app";
import { dateTimeFr, num } from "../lib/format";
import { Empty, ErrorBox, Notice, Spinner, Tabs } from "./ui";

/* ------------------------------------------------------------------------------------------ visionneuses */

function SheetView({ v }: { v: any }) {
  const [i, setI] = useState("0");
  const s = v.sheets[Number(i)] || v.sheets[0];
  if (!s) return <Empty title="Classeur vide" />;
  return (
    <div>
      {v.sheets.length > 1 && <Tabs value={i} onChange={setI} tabs={v.sheets.map((x: any, k: number) => ({ id: String(k), label: x.name }))} />}
      <div className="overflow-auto max-h-[62vh] scrollbar-thin border border-line rounded-lg">
        <table className="text-xs border-collapse min-w-full" aria-label={`Feuille ${s.name}`}>
          <tbody>{s.rows.map((r: string[], k: number) => (
            <tr key={k} className={k === 0 ? "bg-sunken font-semibold sticky top-0" : "odd:bg-sunken/30"}>
              <td className="px-2 py-1 text-muted text-right border-r border-line select-none">{k + 1}</td>
              {r.map((c, j) => <td key={j} className={`px-2 py-1 border-r border-line/60 whitespace-pre-wrap ${/^-?[\d \s]+(,\d+)?\s?(€|%)?$/.test(c) ? "text-right tabular-nums" : ""}`}>{c}</td>)}
            </tr>))}</tbody>
        </table>
      </div>
      <div className="text-[11px] text-muted mt-1">{num(s.n_rows, 0)} ligne(s){s.truncated ? " — aperçu limité aux 300 premières lignes et 40 colonnes : téléchargez le fichier pour le voir en entier" : ""}
        {v.more_sheets > 0 && ` · ${v.more_sheets} autre(s) feuille(s) non affichée(s)`}</div>
    </div>
  );
}

function SvgView({ v }: { v: any }) {
  const [z, setZ] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);
  const src = useMemo(() => URL.createObjectURL(new Blob([v.svg], { type: "image/svg+xml" })), [v.svg]);
  useEffect(() => () => URL.revokeObjectURL(src), [src]);
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <button className="btn-secondary py-1 px-2" onClick={() => setZ(Math.min(z * 1.5, 40))} aria-label="Zoom avant"><Plus size={14} /></button>
        <button className="btn-secondary py-1 px-2" onClick={() => setZ(Math.max(z / 1.5, 0.2))} aria-label="Zoom arrière"><Minus size={14} /></button>
        <button className="btn-secondary py-1 px-2" onClick={() => { setZ(1); setPan({ x: 0, y: 0 }); }} aria-label="Vue d'ensemble"><RotateCcw size={14} /></button>
        <span className="text-xs text-muted ml-2">{num(v.entities, 0)} entité(s){v.units ? ` · unités : ${v.units}` : ""} · faites glisser pour vous déplacer</span>
      </div>
      <div className="relative h-[58vh] overflow-hidden rounded-lg border border-line bg-white cursor-grab active:cursor-grabbing"
        onWheel={(e) => { e.preventDefault(); setZ((x) => Math.min(40, Math.max(0.2, x * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))); }}
        onMouseDown={(e) => { drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; }}
        onMouseMove={(e) => { if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); }}
        onMouseUp={() => { drag.current = null; }} onMouseLeave={() => { drag.current = null; }}>
        <img src={src} alt="Plan DXF" draggable={false} className="absolute inset-0 w-full h-full object-contain select-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${z})`, transformOrigin: "center" }} />
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2 text-xs"><Layers size={13} className="text-muted" />{v.layers.map((l: any) => <span key={l.name} className="chip bg-sunken">{l.name} · {l.count}</span>)}</div>
      {Object.keys(v.unsupported || {}).length > 0 && <div className="text-[11px] text-muted mt-1">Non dessinés : {Object.entries(v.unsupported).map(([k, n]) => `${k} (${n})`).join(", ")}</div>}
      <Notice>{v.notice}</Notice>
    </div>
  );
}

function IfcView({ v }: { v: any }) {
  const s = v.summary;
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-3 text-sm">
        <div className="rounded-lg border border-line p-3"><div className="text-[11px] uppercase tracking-wider text-muted">Projet</div><div className="font-medium">{s.project || "—"}</div></div>
        <div className="rounded-lg border border-line p-3"><div className="text-[11px] uppercase tracking-wider text-muted">Schéma</div><div className="font-medium">{s.schema}</div></div>
        <div className="rounded-lg border border-line p-3"><div className="text-[11px] uppercase tracking-wider text-muted">Logiciel d'origine</div><div className="font-medium">{s.authoring || "—"}</div></div>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div><h4 className="text-sm font-semibold mb-1">Structure spatiale</h4>
          <ul className="text-sm space-y-0.5">
            {s.sites.map((x: string, i: number) => <li key={"s" + i}>Site : {x || "(sans nom)"}</li>)}
            {s.buildings.map((x: string, i: number) => <li key={"b" + i}>Bâtiment : {x || "(sans nom)"}</li>)}
            {s.storeys.map((x: any, i: number) => <li key={"n" + i} className="pl-4">Niveau {x.name}{x.elevation !== null ? ` — altitude ${num(x.elevation, 2)} m` : ""}</li>)}
          </ul></div>
        <div><h4 className="text-sm font-semibold mb-1">Objets par type</h4>
          {!s.elements.length ? <div className="text-sm text-muted">Aucun objet de construction reconnu.</div> :
            <table className="table text-sm"><tbody>{s.elements.map((e: any) => <tr key={e.label}><td>{e.label}</td><td className="text-right tabular-nums">{num(e.count, 0)}</td></tr>)}</tbody></table>}
        </div>
      </div>
      {s.spaces.length > 0 && <div><h4 className="text-sm font-semibold mb-1">Locaux ({s.spaces.length})</h4><div className="flex flex-wrap gap-1">{s.spaces.map((x: string, i: number) => <span key={i} className="chip bg-sunken">{x || "—"}</span>)}</div></div>}
      <div className="text-[11px] text-muted">{num(s.entities, 0)} entités STEP · {num(s.property_sets, 0)} jeu(x) de propriétés</div>
      <Notice>{v.notice}</Notice>
    </div>
  );
}

export function StructuredView({ docId, version }: { docId: string; version?: number }) {
  const [v, setV] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setV(null); setErr(null);
    api.get(`/api/documents/${docId}/view${version ? `?version=${version}` : ""}`).then(setV).catch((e) => setErr(e.message));
  }, [docId, version]);
  if (err) return <ErrorBox error={err} />;
  if (!v) return <Spinner label="Préparation de l'aperçu…" />;
  if (v.kind === "sheet") return <SheetView v={v} />;
  if (v.kind === "html") return <article className="doc-html max-h-[65vh] overflow-y-auto scrollbar-thin rounded-lg border border-line bg-white p-6" dangerouslySetInnerHTML={{ __html: v.html }} />;
  if (v.kind === "svg") return <SvgView v={v} />;
  if (v.kind === "ifc") return <IfcView v={v} />;
  return <ErrorBox error="Aperçu non disponible." />;
}

/* ------------------------------------------------------------------------------------------ annotations */

export type Annotation = { id: string; page: number; kind: string; geometry: { x: number; y: number; w: number; h: number }; text: string;
  color: string; author: string; author_id: string; resolved: boolean; created_at: string; version: number };

export function useAnnotations(docId: string, version: number | undefined, enabled: boolean) {
  const { toastError } = useApp();
  const [items, setItems] = useState<Annotation[]>([]);
  const reload = useCallback(() => {
    if (!enabled) return;
    api.get(`/api/documents/${docId}/annotations${version ? `?version=${version}` : ""}`).then((r: any) => setItems(r)).catch(toastError);
  }, [docId, version, enabled, toastError]);
  useEffect(() => { reload(); }, [reload]);
  return { items, reload };
}

/** Calque d'annotation posé sur une page (image) : cliquer = repère, glisser = zone. */
export function AnnotLayer({ page, items, drawing, onCreate, highlight }: {
  page: number; items: Annotation[]; drawing: boolean; highlight?: string | null;
  onCreate: (page: number, g: { x: number; y: number; w: number; h: number }) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [tmp, setTmp] = useState<{ x0: number; y0: number; x: number; y: number } | null>(null);
  const rel = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
  };
  const mine = items.filter((a) => a.page === page);
  return (
    <div ref={ref} className={`absolute inset-0 ${drawing ? "cursor-crosshair" : "pointer-events-none"}`} data-testid={`annot-layer-${page}`}
      onMouseDown={(e) => { if (!drawing) return; e.preventDefault(); const p = rel(e); setTmp({ x0: p.x, y0: p.y, x: p.x, y: p.y }); }}
      onMouseMove={(e) => { if (tmp) { const p = rel(e); setTmp({ ...tmp, x: p.x, y: p.y }); } }}
      onMouseUp={() => {
        if (!tmp) return;
        const g = { x: Math.min(tmp.x0, tmp.x), y: Math.min(tmp.y0, tmp.y), w: Math.abs(tmp.x - tmp.x0), h: Math.abs(tmp.y - tmp.y0) };
        setTmp(null);
        onCreate(page, g.w < 0.01 && g.h < 0.01 ? { x: tmp.x0, y: tmp.y0, w: 0, h: 0 } : g);
      }}>
      {mine.map((a) => {
        const n = items.indexOf(a) + 1;
        const on = highlight === a.id;
        return a.geometry.w > 0 || a.geometry.h > 0 ? (
          <div key={a.id} title={a.text} className={`absolute border-2 rounded-sm ${a.resolved ? "opacity-40" : ""} ${on ? "ring-4 ring-offset-1" : ""}`}
            style={{ left: `${a.geometry.x * 100}%`, top: `${a.geometry.y * 100}%`, width: `${a.geometry.w * 100}%`, height: `${a.geometry.h * 100}%`, borderColor: a.color, background: a.color + "1f" }}>
            <span className="absolute -top-2.5 -left-2.5 h-5 min-w-5 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center" style={{ background: a.color }}>{n}</span>
          </div>
        ) : (
          <span key={a.id} title={a.text} className={`absolute -translate-x-1/2 -translate-y-1/2 h-5 min-w-5 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center shadow ${a.resolved ? "opacity-40" : ""} ${on ? "ring-4" : ""}`}
            style={{ left: `${a.geometry.x * 100}%`, top: `${a.geometry.y * 100}%`, background: a.color }}>{n}</span>
        );
      })}
      {tmp && <div className="absolute border-2 border-dashed border-danger bg-danger/10" style={{ left: `${Math.min(tmp.x0, tmp.x) * 100}%`, top: `${Math.min(tmp.y0, tmp.y) * 100}%`, width: `${Math.abs(tmp.x - tmp.x0) * 100}%`, height: `${Math.abs(tmp.y - tmp.y0) * 100}%` }} />}
    </div>
  );
}

export function AnnotList({ items, onChanged, onFocus }: { items: Annotation[]; onChanged: () => void; onFocus: (id: string) => void }) {
  const { user, perms, toastError } = useApp();
  if (!items.length) return <div className="text-sm text-muted">Aucune annotation sur cette version. {perms.write && "Activez « Annoter », puis cliquez (repère) ou faites glisser (zone) sur la page."}</div>;
  const canEdit = (a: Annotation) => perms.write && (a.author_id === user?.id || perms.delete);
  return (
    <ol className="space-y-2" aria-label="Annotations">
      {items.map((a, i) => (
        <li key={a.id} className={`rounded-lg border border-line p-2.5 text-sm ${a.resolved ? "opacity-60" : ""}`} onMouseEnter={() => onFocus(a.id)}>
          <div className="flex items-start gap-2">
            <span className="h-5 min-w-5 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center mt-0.5" style={{ background: a.color }}>{i + 1}</span>
            <div className="flex-1 min-w-0"><div className={a.resolved ? "line-through" : ""}>{a.text}</div>
              <div className="text-[11px] text-muted">Page {a.page} · {a.author} · {dateTimeFr(a.created_at)}{a.resolved ? " · traitée" : ""}</div></div>
            {canEdit(a) && <>
              <button className="btn-ghost p-1" title={a.resolved ? "Rouvrir" : "Marquer comme traitée"} aria-label={a.resolved ? "Rouvrir" : "Marquer comme traitée"}
                onClick={async () => { try { await api.call("PUT", `/api/documents/annotations/${a.id}`, { resolved: !a.resolved, version: a.version }); onChanged(); } catch (e) { toastError(e); } }}>
                {a.resolved ? <Circle size={14} /> : <CheckCircle2 size={14} />}</button>
              <button className="btn-ghost p-1 text-danger" title="Supprimer l'annotation" aria-label="Supprimer l'annotation"
                onClick={async () => { if (!window.confirm("Supprimer cette annotation ?")) return; try { await api.del(`/api/documents/annotations/${a.id}`); onChanged(); } catch (e) { toastError(e); } }}><Trash2 size={14} /></button></>}
          </div>
        </li>))}
    </ol>
  );
}
