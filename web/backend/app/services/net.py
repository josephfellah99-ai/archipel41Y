"""Messages d'erreur réseau compréhensibles (jamais de nom d'exception technique affiché à l'utilisateur)."""
import httpx


def explain(exc: BaseException, service: str = "Le service") -> str:
    if isinstance(exc, (httpx.ProxyError, httpx.ConnectError, httpx.ConnectTimeout)):
        return f"{service} est injoignable : vérifiez la connexion internet (ou le pare-feu / proxy de l'agence), puis réessayez."
    if isinstance(exc, httpx.TimeoutException):
        return f"{service} n'a pas répondu à temps. Réessayez dans quelques instants."
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return f"{service} a refusé l'accès ({code}) : vérifiez l'adresse ou les droits d'accès."
        if code == 429:
            return f"{service} limite le nombre de requêtes (429). Réessayez dans quelques minutes."
        return f"{service} a répondu par une erreur ({code})."
    if isinstance(exc, httpx.HTTPError):
        return f"{service} est injoignable ou a renvoyé une réponse invalide."
    return f"{service} a renvoyé une réponse illisible."
