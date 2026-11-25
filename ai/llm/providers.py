"""Couche d'abstraction des fournisseurs d'IA.

Fournisseurs pris en charge :
- « aucun »       : mode sans IA générative (moteurs déterministes uniquement) ;
- « anthropic »   : Claude via le SDK officiel Anthropic ;
- « openai_compat » : toute API compatible OpenAI (OpenAI, Mistral, Azure OpenAI,
                    Ollama ou LM Studio en local…).

Chaque fournisseur indique s'il est EXTERNE (les données quittent le poste) :
l'application refuse alors d'y envoyer des documents confidentiels sauf
autorisation explicite de l'administrateur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"


class AIError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)


class Provider:
    name = "aucun"
    external = False
    supports_embeddings = False

    @property
    def available(self) -> bool:
        return False

    def chat(self, system: str, messages: list[dict], max_tokens: int = 4000) -> ChatResult:
        raise AIError("Aucun fournisseur d'IA générative n'est configuré.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise AIError("Ce fournisseur ne propose pas d'embeddings.")

    def describe(self) -> dict:
        return {"provider": self.name, "external": self.external, "available": self.available,
                "embeddings": self.supports_embeddings}


class NoProvider(Provider):
    pass


class AnthropicProvider(Provider):
    name = "anthropic"
    external = True

    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None,
                 effort: str = "medium", timeout: float = 120.0):
        self.api_key = api_key
        self.model = model or DEFAULT_ANTHROPIC_MODEL
        self.base_url = base_url or None
        self.effort = effort
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _client(self):
        import anthropic

        kwargs = {"api_key": self.api_key, "timeout": self.timeout, "max_retries": 2}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return anthropic.Anthropic(**kwargs)

    def chat(self, system: str, messages: list[dict], max_tokens: int = 4000) -> ChatResult:
        import anthropic

        msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
        try:
            client = self._client()
            params = dict(model=self.model, max_tokens=max_tokens, system=system, messages=msgs,
                          output_config={"effort": self.effort})
            if self.model.startswith(("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")):
                # Repli côté serveur si le modèle décline la requête (catégories de sécurité)
                resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default", **params)
            else:
                resp = client.messages.create(**params)
        except anthropic.AuthenticationError:
            raise AIError("Clé API Anthropic refusée : vérifiez-la dans Paramètres › Intelligence artificielle.")
        except anthropic.RateLimitError:
            raise AIError("Limite de débit Anthropic atteinte : réessayez dans quelques instants.")
        except anthropic.APIStatusError as exc:
            raise AIError(f"Erreur du fournisseur Anthropic ({exc.status_code}) : {exc.message}")
        except anthropic.APIConnectionError:
            raise AIError("Impossible de joindre l'API Anthropic (connexion Internet ou pare-feu).")
        if resp.stop_reason == "refusal":
            raise AIError("Le modèle a décliné cette demande. Reformulez la question.")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        return ChatResult(text=text, provider=self.name, model=resp.model, usage=usage)


class OpenAICompatProvider(Provider):
    """API compatible OpenAI : OpenAI, Mistral (https://api.mistral.ai/v1), Ollama
    (http://localhost:11434/v1), LM Studio, Azure OpenAI (passerelle compatible)…"""

    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str | None, model: str, embedding_model: str | None = None,
                 external: bool | None = None, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.timeout = timeout
        host = httpx.URL(self.base_url).host or ""
        self.external = external if external is not None else host not in ("localhost", "127.0.0.1", "::1")
        self.supports_embeddings = bool(embedding_model)

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.model)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = httpx.post(self.base_url + path, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise AIError(f"Impossible de joindre le fournisseur d'IA ({self.base_url}) : {exc}")
        if r.status_code in (401, 403):
            raise AIError("Clé API refusée par le fournisseur d'IA.")
        if r.status_code >= 400:
            raise AIError(f"Erreur du fournisseur d'IA ({r.status_code}) : {r.text[:300]}")
        return r.json()

    def chat(self, system: str, messages: list[dict], max_tokens: int = 4000) -> ChatResult:
        msgs = [{"role": "system", "content": system}] + [
            {"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
        data = self._post("/chat/completions", {"model": self.model, "messages": msgs, "max_tokens": max_tokens})
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raise AIError("Réponse inattendue du fournisseur d'IA.")
        return ChatResult(text=text, provider=self.name, model=data.get("model", self.model), usage=data.get("usage") or {})

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_model:
            raise AIError("Aucun modèle d'embeddings configuré.")
        data = self._post("/embeddings", {"model": self.embedding_model, "input": texts})
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]


def build_provider(cfg: dict | None) -> Provider:
    cfg = cfg or {}
    kind = cfg.get("provider") or "aucun"
    if kind == "anthropic" and cfg.get("api_key"):
        return AnthropicProvider(cfg["api_key"], cfg.get("model"), cfg.get("base_url"), cfg.get("effort") or "medium")
    if kind == "openai_compat" and cfg.get("base_url") and cfg.get("model"):
        return OpenAICompatProvider(cfg["base_url"], cfg.get("api_key"), cfg["model"], cfg.get("embedding_model"),
                                    cfg.get("external"))
    return NoProvider()
