# Journal des versions

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
