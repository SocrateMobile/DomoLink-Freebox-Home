# DomoLink Freebox Home

Intégration Home Assistant (HACS) complète pour **Freebox OS & Freebox Home**, issue de la rétro-ingénierie des APK officiels `fr.freebox.network`, `fr.freebox.security` et `fr.free.moncomptefree`.

## Fonctionnalités (v2.0.0)
- **Appairage physique LCD** (`POST login/authorize/`) + session `HMAC-SHA1(app_token, challenge)`.
- **Wi-Fi & Répéteurs** : interrupteur Wi-Fi global, interrupteurs par SSID (`wifi/bss/`), bouton WPS, création de clé Wi-Fi invité (`create_wifi_guest_key`), état/LED/redémarrage des répéteurs Wi-Fi.
- **Réseau LAN & Présence** : `device_tracker` pour les appareils connectés, compteur d'appareils actifs, service **Wake-on-LAN** (`wake_on_lan`), interrupteurs de contrôle parental par profil.
- **Stockage, Téléphonie, VPN & Player** : espace libre des partitions disque (%), appels manqués & répondeur (+ bouton/service *Marquer comme lus*), serveurs & clients VPN, redémarrage Freebox Server & Player TV.
- **Système** : débits WAN, IPv4, volume téléchargé/envoyé, température, luminosité écran OLED (`number`), statut mise à jour firmware (`update`).
- **Domotique Freebox Home** *(si disponible sur la Freebox)* : alarme (`alarm_control_panel`), détecteurs ouverture/mouvement/fumée, volets (`cover`), lumières (`light`), prises (`switch`) et caméras RTSP/HLS (`camera`).
