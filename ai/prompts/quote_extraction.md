Tu extrais les données d'un devis de travaux français. Réponds UNIQUEMENT par un objet JSON valide, sans texte autour,
au format :
{"company_name": str|null, "reference": str|null, "quote_date": "AAAA-MM-JJ"|null, "validity_days": int|null,
 "delay_text": str|null, "delay_days": int|null, "payment_terms": str|null, "default_vat": number|null,
 "declared_ht": number|null, "declared_tva": number|null, "declared_ttc": number|null,
 "exclusions": [str], "reserves": [str], "conditions": [str], "variants": [str],
 "lines": [{"code": str|null, "section": str|null, "designation": str, "quantity": number|null, "unit": str|null,
            "unit_price": number|null, "total_ht": number|null, "vat_rate": number|null,
            "status": "inclus"|"exclu"|"optionnel"|"variante"|"a_verifier"}]}
Règles :
- Recopie les nombres tels qu'écrits (format décimal avec point), ne calcule rien, ne complète rien.
- "exclu" uniquement si le devis l'exclut expressément (« non compris », « hors lot », « à la charge du client »).
- Une prestation simplement absente ne figure pas dans les lignes.
- "optionnel" pour les options, "variante" pour les variantes, "a_verifier" en cas de doute (PM, à définir).
- Ignore les lignes de sous-total et de total dans "lines".

TEXTE DU DEVIS :
{{text}}
