; Archipel41 – personnalisation de l'installateur NSIS
!macro customUnInstall
  ; Les données de l'utilisateur (%APPDATA%\Archipel41) sont conservées par défaut.
  MessageBox MB_YESNO|MB_ICONQUESTION "Souhaitez-vous également supprimer vos données Archipel41 (base locale, documents, sauvegardes) ?$\r$\n$\r$\nRépondez « Non » pour les conserver (recommandé si vous réinstallez)." /SD IDNO IDNO keep
    RMDir /r "$APPDATA\Archipel41"
  keep:
!macroend
