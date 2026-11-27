# Journal des versions

## 1.1.0 – 27/11/2026
Comparateur de devis : lecture plus sûre des nombres, remarques techniques, optimisation économique à qualité constante.
- Lecture des lignes : les nombres techniques de la désignation (Uw 1,3, Ø 90, EI 30, année…) ne sont plus pris pour une
  quantité ; colonne TVA sans « % » reconnue ; découpage retenu en priorité si quantité × PU = montant, sinon ligne signalée.
- Caractéristiques techniques lues dans les libellés (épaisseur, classe de béton, R, Uw/Ug/Up, λ, diamètre, coupe-feu,
  acoustique, dosage, dimensions, UPEC) et comparées à la DPGF et entre offres.
- Remarques techniques classées (gravité, thème, impact en euros, action recommandée).
- Coût réel probable par offre (coûts cachés), leviers de négociation ciblant la médiane des offres conformes, plancher
  réaliste du lot ; prix anormalement bas et prestations inférieures exclus des cibles.
- Exports Excel, Word, PDF : feuilles « Optimisation », « Leviers de négociation », « Remarques techniques ».
- 13 tests supplémentaires (78 au total, SQLite et PostgreSQL) ; 28 vérifications de bout en bout.

## 1.0.0 – 25/11/2026
Première version.
- 11 modules : tableau de bord, projets et chantiers (phases ESQ→AOR), devis et comparateur, agenda, planning Gantt et météo,
  urbanisme, assistant IA (RAG), documents, clients et entreprises, finances, rapports (PDF, XLSX, DOCX, CSV).
- Extraction des devis : PDF natifs et scannés (OCR), images, XLS/XLSX, CSV, DOC/DOCX, ZIP ; moteur de calcul déterministe ;
  comparateur à 7 statuts avec DPGF et CCTP ; conclusion argumentée (règles, IA facultative).
- Local-first : application Windows (SQLite) synchronisée avec un serveur central (PostgreSQL/PostGIS/pgvector), PWA hors connexion,
  gestion des conflits.
- Sécurité : rôles, isolation par agence, projets confidentiels, chiffrement des secrets, journal d'audit, sauvegardes vérifiées.
- Installateur Windows NSIS (français) et version portable, avec Python et Tesseract OCR embarqués.
