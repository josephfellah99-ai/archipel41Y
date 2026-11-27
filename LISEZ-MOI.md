# Installateur Windows d'Archipel41 1.1.0

Nouveautés de la 1.1.0 :
- **Correctif** : l'aperçu d'un PDF pouvait arrêter le moteur local (« Le moteur local d'Archipel41 s'est arrêté de façon
  inattendue »). Cause trouvée et corrigée ; en cas d'incident imprévu, le moteur redémarre désormais tout seul.
- Saisie fiable des montants (« 12 500,50 », « 1 250 000 »), des coordonnées et des dates dans tous les formulaires.
- Connexion Administrateur / Collaborateur / Invité, autorisations par module et par projet, invitations.
- Module Équipe, notifications, commentaires ; page Chantiers.
- Historique et activité : modifications (avant/après), connexions, journal des erreurs, diagnostic.
- Comparateur : lecture plus sûre des nombres, remarques techniques, coût réel et économies.

**Vos données sont conservées** : installez simplement la 1.1.0 par-dessus la 1.0.0 (la base est mise à jour
automatiquement au premier démarrage). Par précaution, faites une sauvegarde avant (Paramètres › Sauvegardes).

## Installation

GitHub limite la taille des fichiers : l'installateur (164 Mo) est donc découpé en deux morceaux.

1. Sur cette page, cliquez sur le bouton vert **Code**, puis **Download ZIP**.
2. Ouvrez le dossier **Téléchargements**, faites un clic droit sur le fichier ZIP › **Extraire tout…** › **Extraire**.
3. Dans le dossier extrait, double-cliquez sur **INSTALLER_ARCHIPEL41.bat**.
   - Si Windows affiche « Windows a protégé votre ordinateur » : **Informations complémentaires** › **Exécuter quand même**.
4. Le script rassemble les deux morceaux, vérifie le fichier (empreinte SHA-256) puis lance l'installation.

Empreinte SHA-256 de l'installateur : `a539593e16abd9b0f4642341150c9a5c2e3f635ca71fd41ae11e60ff2c00d146`

Le code source se trouve sur la branche `evolution-environnement`.
