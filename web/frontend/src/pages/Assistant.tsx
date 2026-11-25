import { Sparkles, Send, X, Plus, Trash2, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr } from "../lib/format";
import { Card, Markdown, Notice, PageHeader, Select, Spinner } from "../components/ui";

const SUGGESTIONS = [
  "Quels sont les risques principaux du projet en cours ?",
  "Résume les écarts entre les devis du lot gros œuvre.",
  "Quelle est l'emprise au sol autorisée dans le règlement de PLU ?",
  "Quelles actions ont été décidées lors de la dernière réunion de chantier ?",
  "Quelles tâches sont en retard et quel est leur impact ?",
  "Quelles exigences du CCTP concernent les fondations ?",
];

function Chat({ compact = false }: { compact?: boolean }) {
  const { projectId, projects, toastError } = useApp();
  const status = useApi<any>("/api/assistant/status");
  const convs = useApi<any[]>(compact ? null : "/api/conversations");
  const [pid, setPid] = useState(projectId || "");
  const [cid, setCid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { setPid(projectId || ""); }, [projectId]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);
  const open = async (id: string) => {
    const c = await api.get(`/api/conversations/${id}`);
    setCid(id); setMsgs(c.messages || []); setPid(c.project_id || "");
  };
  const ask = async (question: string) => {
    if (!question.trim()) return;
    setMsgs((m) => [...m, { role: "user", content: question }]);
    setQ("");
    setBusy(true);
    try {
      const r = await api.call("POST", "/api/assistant/ask", { question, project_id: pid || null, conversation_id: cid });
      setCid(r.conversation_id);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources, mode: r.mode }]);
      convs.reload();
    } catch (e: any) {
      toastError(e);
      setMsgs((m) => [...m, { role: "assistant", content: `_${e.message}_`, sources: [] }]);
    } finally { setBusy(false); }
  };
  const s = status.data;
  return (
    <div className={`grid gap-6 ${compact ? "" : "lg:grid-cols-[240px_1fr]"} h-full`}>
      {!compact && (
        <Card title="Conversations" actions={<button className="btn-ghost p-1" onClick={() => { setCid(null); setMsgs([]); }} title="Nouvelle conversation"><Plus size={15} /></button>} pad={false}>
          <ul className="max-h-[60vh] overflow-y-auto scrollbar-thin">{(convs.data || []).map((c) => (
            <li key={c.id} className={`flex items-center group ${cid === c.id ? "bg-sunken" : ""}`}>
              <button className="flex-1 text-left px-4 py-2 text-sm min-w-0" onClick={() => open(c.id)}><div className="truncate">{c.title}</div><div className="text-[11px] text-muted">{dateFr(c.updated_at)} · {c.count} message(s)</div></button>
              <button className="opacity-0 group-hover:opacity-100 p-2 text-muted hover:text-danger" onClick={async () => { await api.del(`/api/conversations/${c.id}`); if (cid === c.id) { setCid(null); setMsgs([]); } convs.reload(); }} aria-label="Supprimer"><Trash2 size={13} /></button>
            </li>))}</ul>
        </Card>
      )}
      <div className="flex flex-col min-h-0 h-full">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <Select className="w-64 py-1.5" value={pid} onChange={setPid} placeholder="Contexte : toute l'agence" options={projects.map((p) => ({ value: p.id, label: `Projet ${p.code} – ${p.name}` }))} />
          {s && <span className={`chip ${s.available ? "bg-ok/15 text-ok" : "bg-warn/15 text-warn"}`}>{s.available ? `${s.provider === "anthropic" ? "Claude" : "Modèle"} ${s.model || ""}${s.external ? " · externe" : " · local"}` : "Mode sans IA générative (recherche documentaire)"}</span>}
          {s?.available && s.external && !s.allow_confidential && <span className="chip bg-sunken text-muted" title="Les documents et projets confidentiels ne sont pas transmis"><ShieldCheck size={12} /> confidentiels protégés</span>}
        </div>
        {s && !s.available && msgs.length === 0 && <div className="mb-3"><Notice>Aucun fournisseur d'IA n'est configuré : l'assistant répond en citant les passages les plus pertinents de vos documents (recherche RAG locale). Un administrateur peut connecter Claude, Mistral, OpenAI ou un modèle local (Ollama) dans Paramètres › Intelligence artificielle.</Notice></div>}
        <div className={`flex-1 overflow-y-auto scrollbar-thin space-y-4 ${compact ? "" : "card p-4 min-h-[50vh]"}`}>
          {msgs.length === 0 && (
            <div className="grid sm:grid-cols-2 gap-2">{SUGGESTIONS.map((x) => <button key={x} onClick={() => ask(x)} className="text-left text-sm rounded-lg border border-line p-3 hover:border-sage">{x}</button>)}</div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
              {m.role === "user" ? <div className="bg-forest text-white dark:text-bg rounded-xl rounded-br-sm px-3.5 py-2 text-sm max-w-[85%] whitespace-pre-wrap">{m.content}</div> : (
                <div className="max-w-full">
                  <div className="flex items-center gap-1.5 text-xs text-muted mb-1"><Sparkles size={12} className="text-sage" /> Assistant {m.mode === "extractif" && "· mode extractif"}</div>
                  <Markdown text={m.content} />
                  {m.sources?.length > 0 && (
                    <details className="mt-2"><summary className="text-xs text-sage cursor-pointer">{m.sources.length} source(s) citée(s)</summary>
                      <ul className="mt-1.5 space-y-1.5">{m.sources.map((src: any) => (
                        <li key={src.ref} className="text-xs rounded-md bg-sunken p-2"><b>[{src.ref}]</b> <Link className="text-sage" to={`/documents?doc=${src.document_id}`}><FileText size={11} className="inline" /> {src.document}</Link>{src.page ? `, p. ${src.page}` : ""}
                          <div className="text-muted mt-0.5 line-clamp-3">{src.excerpt}</div></li>))}</ul></details>)}
                </div>)}
            </div>))}
          {busy && <Spinner label="Analyse des documents et du contexte…" />}
          <div ref={end} />
        </div>
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <textarea rows={compact ? 2 : 2} className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Posez une question sur vos projets, devis, règlements, réunions…"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q); } }} />
          <button className="btn-primary self-end" disabled={busy || !q.trim()} aria-label="Envoyer"><Send size={16} /></button>
        </form>
        <p className="text-[11px] text-muted mt-1.5">Les réponses sont une aide à la décision et citent leurs sources lorsque possible. Vérifiez toujours les informations réglementaires.</p>
      </div>
    </div>
  );
}

export function AssistantPage() {
  return (
    <div>
      <PageHeader title="Assistant IA" icon={<Sparkles size={22} />} subtitle="Interrogez vos documents (RAG), vos projets et vos archives. Les réponses citent leurs sources." />
      <Chat />
    </div>
  );
}

export function AssistantDrawer() {
  const { assistantOpen, setAssistantOpen } = useApp();
  if (!assistantOpen) return null;
  return (
    <div className="fixed inset-0 z-[60] no-print" onClick={() => setAssistantOpen(false)}>
      <div className="absolute inset-0 bg-black/20" />
      <aside className="absolute right-0 top-0 bottom-0 w-full sm:w-[480px] bg-bg border-l border-line shadow-xl flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-line"><div className="font-semibold flex items-center gap-2"><Sparkles size={16} className="text-sage" /> Assistant Archipel41</div>
          <button className="btn-ghost p-1.5" onClick={() => setAssistantOpen(false)} aria-label="Fermer"><X size={18} /></button></div>
        <div className="flex-1 min-h-0 p-4"><Chat compact /></div>
      </aside>
    </div>
  );
}
