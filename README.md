# DomoLink Freebox Home

Intégration Home Assistant (HACS) pour **Freebox OS & Freebox Home** (Alarme, Capteurs domotiques, Volets Somfy, Lumières, Caméras RTSP/HLS, Débits WAN, Températures), issue de la rétro-ingénierie de `fr.freebox.network` et `fr.freebox.security`.

## Fonctionnalités
- Appairage physique officiel Freebox LCD (`POST login/authorize/` + `GET login/authorize/{trackId}`).
- Authentification `HMAC-SHA1(app_token, challenge)` (`POST login/session/`, header `X-Fbx-App-Auth`).
- **Alarme** (`alarm_control_panel`), **Détecteurs** (ouverture, mouvement, fumée, batterie faible), **Volets** (`cover`), **Lumières** (`light`), **Prises/Interrupteurs** (`switch`), **Caméras** (`camera` RTSP/HLS), **Débit/Température/Bouton Reboot**.
