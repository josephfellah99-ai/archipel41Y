import { MessageSquare, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateTimeFr } from "../lib/format";
import { AsyncButton, Empty, Spinner } from "./ui";

/** Fil d'échanges rattaché à un élément (projet, document, tâche, rendez-vous).
 *  Mentionnez un collaborateur avec « @Prénom » ou « @Prénom Nom » : il reçoit une notification. */
export function Comments({ entity, entityId, guest = false, canWrite }: { entity: string; entityId: string; guest?: boolean; canWrite?: boolean }) {
  const { perms, toastError, user } = useApp();
  const url = guest ? `/api/guest/comments?entity=${entity}&entity_id=${entityId}` : `/api/comments?entity=${entity}&entity_id=${entityId}`;
  const list = useApi<any[]>(url);
  const users = useApi<any[]>(guest ? null : "/api/users");
  const [body, setBody] = useState("");
  const [edit, setEdit] = useState<{ id: string; body: string } | null>(null);
  const writable = canWrite ?? perms.write;
  const send = async () => {
    try {
      await api.call("POST", guest ? "/api/guest/comments" : "/api/comments", { entity, entity_id: entityId, body });
      setBody("");
      list.reload();
    } catch (e) { toastError(e); }
  };
  const save = async () => {
    if (!edit) return;
    try { await api.call("PUT", `/api/comments/${edit.id}`, { body: edit.body }); setEdit(null); list.reload(); } catch (e) { toastError(e); }
  };
  const del = async (id: string) => {
    if (!window.confirm("Supprimer ce commentaire ?")) return;
    try { await api.call("DELETE", `/api/comments/${id}`); list.reload(); } catch (e) { toastError(e); }
  };
  // Suggestion de mention : dernier mot commençant par « @ »
  const m = /@([\p{L}.-]*)$/u.exec(body);
  const suggestions = m && users.data ? users.data.filter((u) => u.full_name.toLowerCase().includes(m[1].toLowerCase())).slice(0, 5) : [];
  return (
    <div>
      {list.loading && !list.data ? <Spinner /> : !list.data?.length ? (
        <Empty title="Aucun échange" icon={<MessageSquare size={18} />}>Questions, décisions, remarques : tout reste rattaché à cet élément, au lieu d'être dispersé dans les e-mails.</Empty>
      ) : (
        <ul className="space-y-3 mb-4">{list.data.map((c) => (
          <li key={c.id} className="flex gap-3">
            <div className={`h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[11px] font-semibold text-white ${c.guest ? "bg-muted" : "bg-sage"}`}>
              {c.author_name.split(" ").map((s: string) => s[0]).slice(0, 2).join("")}</div>
            <div className="min-w-0 flex-1">
              <div className="text-xs text-muted"><b className="text-ink font-medium">{c.author_name}</b> · {dateTimeFr(c.created_at)}{c.edited && " · modifié"}</div>
              {edit?.id === c.id ? (
                <div className="mt-1 space-y-2"><textarea className="input min-h-[70px]" value={edit?.body ?? ""} onChange={(e) => setEdit({ id: c.id, body: e.target.value })} />
                  <div className="flex gap-2"><AsyncButton className="btn-primary py-1" onClick={save} disabled={!edit?.body.trim()}>Enregistrer</AsyncButton>
                    <button className="btn-secondary py-1" onClick={() => setEdit(null)}>Annuler</button></div></div>
              ) : <div className="text-sm whitespace-pre-wrap mt-0.5">{c.body}</div>}
            </div>
            {!guest && (c.mine || perms.admin) && edit?.id !== c.id && (
              <div className="flex gap-1 shrink-0">
                {c.mine && <button className="btn-ghost p-1.5" aria-label="Modifier" onClick={() => setEdit({ id: c.id, body: c.body })}><Pencil size={13} /></button>}
                <button className="btn-ghost p-1.5 text-danger" aria-label="Supprimer" onClick={() => del(c.id)}><Trash2 size={13} /></button>
              </div>)}
          </li>))}</ul>
      )}
      {writable && (
        <div className="relative">
          <textarea className="input min-h-[70px]" placeholder={guest ? "Votre message à l'agence…" : "Écrire un message… (@Prénom pour mentionner un collaborateur)"}
            value={body} onChange={(e) => setBody(e.target.value)} aria-label="Nouveau commentaire" maxLength={5000} />
          {suggestions.length > 0 && (
            <div className="absolute z-10 left-2 bottom-full mb-1 card py-1 text-sm min-w-[220px]">
              {suggestions.map((u) => <button key={u.id} type="button" className="block w-full text-left px-3 py-1.5 hover:bg-sunken"
                onClick={() => setBody(body.replace(/@([\p{L}.-]*)$/u, `@${u.full_name} `))}>{u.full_name}{u.id === user?.id ? " (vous)" : ""}</button>)}
            </div>)}
          <div className="flex justify-end mt-2"><AsyncButton onClick={send} disabled={!body.trim()}>Publier</AsyncButton></div>
        </div>
      )}
    </div>
  );
}
