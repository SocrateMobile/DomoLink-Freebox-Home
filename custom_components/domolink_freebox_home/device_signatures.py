"""Comprehensive brand, model, category, and MDI icon recognition for Freebox LAN/Wi-Fi clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .home_helpers import host_type_icon


@dataclass(frozen=True)
class DeviceClassification:
    """Resolved brand, model/family, French category, and MDI icon for a LAN host."""

    brand: str
    model: str
    category: str
    icon: str


# Ordered from most specific (model/product keywords) to broader brand/vendor rules.
# Each entry: (keywords_tuple, brand, model, category, icon)
_SIGNATURE_RULES: tuple[tuple[tuple[str, ...], str, str, str, str], ...] = (
    # --- Apple ---
    (("iphone",), "Apple", "iPhone", "Smartphone", "mdi:cellphone"),
    (("ipad",), "Apple", "iPad", "Tablette", "mdi:tablet"),
    (("macbook",), "Apple", "MacBook", "Ordinateur portable", "mdi:laptop"),
    (("imac", "mac-studio", "mac studio", "mac-mini", "mac mini", "mac-pro", "mac pro"), "Apple", "Mac", "Ordinateur", "mdi:desktop-mac"),
    (("apple-watch", "apple watch", "watchos"), "Apple", "Apple Watch", "Montre connectée", "mdi:watch"),
    (("homepod",), "Apple", "HomePod", "Audio / Enceinte", "mdi:speaker-wireless"),
    (("apple-tv", "apple tv", "appletv"), "Apple", "Apple TV", "TV / Streaming", "mdi:television-box"),
    (("airport", "time capsule"), "Apple", "AirPort", "Réseau", "mdi:router-wireless"),

    # --- Consoles de jeu ---
    (("ps5", "ps4", "ps3", "playstation", "sony interactive"), "Sony", "PlayStation", "Console de jeu", "mdi:sony-playstation"),
    (("xbox",), "Microsoft", "Xbox", "Console de jeu", "mdi:microsoft-xbox"),
    (("nintendo", "switch", "wii"), "Nintendo", "Nintendo Switch", "Console de jeu", "mdi:nintendo-switch"),
    (("steamdeck", "steam-deck", "steam deck"), "Valve", "Steam Deck", "Console de jeu", "mdi:gamepad-variant"),
    (("oculus", "meta quest", "quest-2", "quest-3", "quest 3"), "Meta", "Meta Quest", "VR / Gaming", "mdi:virtual-reality"),

    # --- NAS & Serveurs ---
    (("synology", "diskstation", "rackstation", "ds21", "ds22", "ds42", "ds72", "ds92", "ds15", "ds16", "ds18"), "Synology", "Synology NAS", "NAS / Stockage", "mdi:nas"),
    (("asustor", "lockerstor", "drivestor", "nimbustor", "flashstor"), "Asustor", "Asustor NAS", "NAS / Stockage", "mdi:nas"),
    (("truenas", "freenas", "ixsystems"), "TrueNAS", "TrueNAS", "NAS / Stockage", "mdi:nas"),
    (("qnap", "ts-2", "ts-4", "tvs-"), "QNAP", "QNAP NAS", "NAS / Stockage", "mdi:nas"),
    (("unraid",), "Unraid", "Unraid Server", "NAS / Stockage", "mdi:nas"),
    (("openmediavault", "omv-"), "OpenMediaVault", "OMV NAS", "NAS / Stockage", "mdi:nas"),
    (("terramaster", "ugreen nas", "mycloud", "wdmycloud", "buffalo linkstation"), "NAS", "NAS", "NAS / Stockage", "mdi:nas"),
    (("proxmox", "pve"), "Proxmox", "Proxmox VE", "Serveur", "mdi:server"),
    (("homeassistant", "home-assistant", "hassio", "hassos"), "Home Assistant", "Home Assistant", "Domotique / Serveur", "mdi:home-assistant"),
    (("raspberry", "raspi", "rpi-", "rpi4", "rpi5"), "Raspberry Pi", "Raspberry Pi", "Serveur / SBC", "mdi:raspberry-pi"),
    (("vmware", "esxi", "vsphere"), "VMware", "ESXi", "Serveur", "mdi:server"),
    (("minisforum", "beelink", "intel nuc", "nuc-"), "Mini PC", "Mini PC / NUC", "Serveur / PC", "mdi:desktop-tower"),

    # --- Audio & Home-Cinéma ---
    (("denon", "heos", "avr-x", "avr-s"), "Denon", "Denon AVR / HEOS", "Audio / Home-Cinéma", "mdi:amplifier"),
    (("marantz", "sr50", "sr60", "sr70", "cinema "), "Marantz", "Marantz AVR", "Audio / Home-Cinéma", "mdi:amplifier"),
    (("onkyo", "tx-nr", "tx-rz", "integra"), "Onkyo", "Onkyo AVR", "Audio / Home-Cinéma", "mdi:amplifier"),
    (("pioneer", "vsx-"), "Pioneer", "Pioneer AVR", "Audio / Home-Cinéma", "mdi:amplifier"),
    (("yamaha", "musiccast", "rx-v", "rx-a"), "Yamaha", "Yamaha MusicCast", "Audio / Home-Cinéma", "mdi:amplifier"),
    (("sonos",), "Sonos", "Sonos", "Audio / Enceinte", "mdi:speaker-wireless"),
    (("bose", "soundtouch"), "Bose", "Bose", "Audio / Enceinte", "mdi:speaker-wireless"),
    (("devialet", "phantom", "dione"), "Devialet", "Devialet", "Audio / Enceinte", "mdi:speaker-wireless"),
    (("harman", "jbl", "bang & olufsen", "beosound", "marshall", "wiim", "bluesound", "kef", "focal", "cabasse"), "Audio Hi-Fi", "Enceinte Hi-Fi", "Audio / Enceinte", "mdi:speaker-wireless"),

    # --- Caméras & Sécurité ---
    (("reolink", "rlc-", "rln-", "trackmix", "argus"), "Reolink", "Caméra Reolink", "Caméra / Sécurité", "mdi:cctv"),
    (("arlo", "vmb4", "vmb5", "vmc4", "vmc5"), "Arlo", "Caméra Arlo", "Caméra / Sécurité", "mdi:cctv"),
    (("ezviz", "hikvision", "cs-c", "c3wn", "c6n", "c8c", "db1c"), "Ezviz", "Caméra Ezviz", "Caméra / Sécurité", "mdi:cctv"),
    (("dahua", "imou", "amcrest"), "Dahua / Imou", "Caméra IP", "Caméra / Sécurité", "mdi:cctv"),
    (("eufy", "anker security"), "Eufy", "Caméra Eufy", "Caméra / Sécurité", "mdi:cctv"),
    (("ring-", "ring doorbell", "ring cam", "blink-"), "Ring / Blink", "Caméra / Sonnette", "Caméra / Sécurité", "mdi:cctv"),
    (("tapo", "c100", "c200", "c210", "c310", "c320", "c500", "c520"), "TP-Link Tapo", "Tapo", "Caméra / Domotique", "mdi:cctv"),
    (("axis communications", "foscam", "wyze", "unifi protect"), "Caméra IP", "Caméra IP", "Caméra / Sécurité", "mdi:cctv"),
    (("ajax", "verisure", "somfy protect"), "Alarme", "Système d'alarme", "Sécurité", "mdi:shield-home"),
    (("nuki", "tedee", "yale", "august lock"), "Serrure connectée", "Serrure connectée", "Sécurité", "mdi:lock-smart"),

    # --- Domotique, IoT & ESP ---
    (("esphome",), "ESPHome", "Module ESPHome", "Domotique / IoT", "mdi:chip"),
    (("tasmota",), "Tasmota", "Module Tasmota", "Domotique / IoT", "mdi:chip"),
    (("wled",), "WLED", "Contrôleur WLED", "Éclairage / LED", "mdi:led-strip-variant"),
    (("espressif", "esp32", "esp8266", "esp-"), "Espressif / ESP", "Module ESP", "Domotique / IoT", "mdi:chip"),
    (("sonoff", "ewelink", "itead", "nspanel", "zbbridge"), "Sonoff", "Sonoff / eWeLink", "Domotique / IoT", "mdi:light-switch"),
    (("shelly", "allterco"), "Shelly", "Shelly", "Domotique / IoT", "mdi:electric-switch"),
    (("tuya", "smartlife", "smart_life", "beken", "tywe"), "Tuya", "Tuya / SmartLife", "Domotique / IoT", "mdi:home-automation"),
    (("aqara", "lumi"), "Aqara", "Aqara", "Domotique / IoT", "mdi:home-automation"),
    (("yeelight",), "Yeelight", "Yeelight", "Éclairage", "mdi:lightbulb"),
    (("roborock", "dreame", "mi-robot", "mi robot", "roomba", "irobot", "ecovacs", "deebot"), "Aspirateur Robot", "Robot aspirateur", "Électroménager", "mdi:robot-vacuum"),
    (("philips-hue", "philips hue", "signify", "hue-bridge", "hue bridge"), "Philips Hue", "Philips Hue", "Éclairage", "mdi:lightbulb-group"),
    (("govee", "nanoleaf", "lifx", "wiz-", "twinkly"), "Éclairage connecté", "Éclairage LED", "Éclairage", "mdi:lightbulb-on"),
    (("tado", "netatmo", "nest-thermostat", "ecobee", "sensibo", "somfy", "cozytouch", "atlantic", "daikin", "mitsubishi"), "Climat / Chauffage", "Thermostat / PAC", "Énergie / Confort", "mdi:thermostat"),
    (("meross", "switchbot", "broadlink", "kasa", "legrand", "wiser", "dirigera", "tradfri", "ikea"), "Domotique", "Module domotique", "Domotique / IoT", "mdi:home-automation"),
    (("dyson",), "Dyson", "Dyson", "Électroménager", "mdi:air-purifier"),
    (("withings",), "Withings", "Withings", "Santé connectée", "mdi:scale-bathroom"),

    # --- TV & Boîtiers Streaming ---
    (("bravia",), "Sony", "Sony Bravia TV", "TV / Streaming", "mdi:television"),
    (("webos", "lg-tv", "lg tv", "lgtv", "oled55", "oled65", "oled77", "nanocell"), "LG", "LG Smart TV", "TV / Streaming", "mdi:television"),
    (("hisense", "vidaa"), "Hisense", "Hisense TV", "TV / Streaming", "mdi:television"),
    (("tcl-", "tcl tv", "tcl ", "tcl_"), "TCL", "TCL TV", "TV / Streaming", "mdi:television"),
    (("essentielb", "essentiel b", "essentiel-b", "boulanger"), "Essentiel B", "Essentiel B", "TV / Électronique", "mdi:television"),
    (("samsung-tv", "samsung tv", "qled", "the frame", "tizen", "[tv] samsung"), "Samsung", "Samsung Smart TV", "TV / Streaming", "mdi:television"),
    (("philips tv", "ambilight", "tp vision"), "Philips", "Philips TV", "TV / Streaming", "mdi:television"),
    (("panasonic", "viera"), "Panasonic", "Panasonic TV", "TV / Streaming", "mdi:television"),
    (("nvidia shield", "shield-android", "shieldtv"), "NVIDIA", "NVIDIA Shield TV", "TV / Streaming", "mdi:television-box"),
    (("google-tv", "google tv", "googletv", "google tv streamer", "chromecast", "sabrina", "boreal", "androidtv", "android-tv"), "Google", "Google TV / Chromecast", "TV / Streaming", "mdi:television-box"),
    (("mi-box", "mi box", "mibox", "xiaomi tv box", "xiaomi-tv-box", "mi tv stick", "mi-tv-stick", "mitv-stick", "mdz-22", "mdz-24", "mdz-27", "mdz-28"), "Xiaomi", "Xiaomi TV Box / Stick", "TV / Streaming", "mdi:television-box"),
    (("xiaomi tv", "xiaomi-tv", "mi tv", "mi-tv", "mitv", "redmi tv", "redmi-tv", "xiaomi a pro", "xiaomi s mini", "xiaomi q2", "xiaomi p1", "xiaomi f2"), "Xiaomi", "Xiaomi Smart TV", "TV / Streaming", "mdi:television"),
    (("firetv", "fire-tv", "fire tv", "aftm", "aftk"), "Amazon", "Fire TV", "TV / Streaming", "mdi:television-box"),
    (("roku", "formuler", "zidoo"), "Box TV", "Lecteur Streaming", "TV / Streaming", "mdi:television-box"),

    # --- Smartphones, Tablettes & Constructeurs généralistes ---
    (("galaxy-tab", "galaxy tab", "sm-t", "sm-x"), "Samsung", "Galaxy Tab", "Tablette", "mdi:tablet"),
    (("galaxy-watch", "galaxy watch", "sm-r"), "Samsung", "Galaxy Watch", "Montre connectée", "mdi:watch"),
    (("galaxy", "sm-s", "sm-g", "sm-a", "sm-f", "samsung"), "Samsung", "Samsung", "Smartphone / Électronique", "mdi:cellphone"),
    (("redmi", "poco", "xiaomi", "mi-1", "mi 1", "mi-pad"), "Xiaomi", "Xiaomi / Redmi", "Smartphone / IoT", "mdi:cellphone"),
    (("pixel-", "pixel ", "google nest", "google home"), "Google", "Google Pixel / Nest", "Smartphone / Domotique", "mdi:google"),
    (("oneplus", "oppo", "realme", "vivo", "honor", "huawei", "nothing phone", "motorola", "fairphone"), "Smartphone", "Smartphone Android", "Smartphone", "mdi:cellphone"),
    (("sony", "xperia"), "Sony", "Sony", "Audio / TV / Mobile", "mdi:television"),
    (("lg electronics", "lg thinq"), "LG", "LG", "TV / Électroménager", "mdi:television"),
    (("apple",), "Apple", "Appareil Apple", "Apple", "mdi:apple"),

    # --- Énergie, Solaire & Véhicules électriques ---
    (("tesla",), "Tesla", "Tesla", "Véhicule électrique", "mdi:car-electric"),
    (("wallbox", "easee", "zaptec", "evbox", "ohme", "ve-tronic", "borne"), "Borne VE", "Borne de recharge", "Énergie / VE", "mdi:ev-station"),
    (("enphase", "envoy", "solaredge", "fronius", "sma solar", "apsystems", "hoymiles", "zendure", "ecoflow", "bluetti", "anker solix"), "Solaire / Batterie", "Onduleur / Batterie", "Énergie / Solaire", "mdi:solar-power"),

    # --- Imprimantes & Imprimantes 3D ---
    (("bambu", "prusa", "creality", "voron", "octoprint", "klipper", "mainsail", "fluidd", "anycubic", "elegoo"), "Imprimante 3D", "Imprimante 3D", "Imprimante 3D", "mdi:printer-3d"),
    (("brother", "epson", "canon", "xerox", "lexmark", "kyocera", "hp laserjet", "hp officejet", "hp envy", "hp deskjet", "deskjet", "officejet", "laserjet"), "Imprimante", "Imprimante", "Imprimante", "mdi:printer"),

    # --- Réseau ---
    (("ubiquiti", "unifi", "ubnt", "uap-", "usw-", "udm"), "Ubiquiti", "UniFi", "Réseau", "mdi:access-point"),
    (("mikrotik", "routerboard"), "MikroTik", "MikroTik", "Réseau", "mdi:router-network"),
    (("cisco", "meraki", "aruba", "ruckus"), "Réseau Pro", "Switch / AP", "Réseau", "mdi:router-network"),
    (("netgear", "orbi", "nighthawk", "tp-link", "omada", "deco", "asus router", "gl-inet", "glinet", "linksys", "d-link", "zyxel"), "Réseau", "Routeur / Mesh / Switch", "Réseau", "mdi:router-wireless"),
    (("freebox", "iliad", "fbx"), "Freebox", "Équipement Freebox", "Réseau Freebox", "mdi:router-wireless"),

    # --- PC / Ordinateurs ---
    (("dell", "lenovo", "thinkpad", "hewlett", "hp-", "asus", "acer", "msi-", "gigabyte", "surface", "framework", "razer", "alienware"), "PC", "Ordinateur", "Ordinateur", "mdi:laptop"),
)


def classify_lan_host(host: dict[str, Any], active: bool = True) -> DeviceClassification:
    """Classify a Freebox LAN/Wi-Fi host into (brand, model, category, mdi_icon)."""
    parts: list[str] = [
        str(host.get("primary_name") or ""),
        str(host.get("vendor_name") or ""),
        str(host.get("host_type") or ""),
    ]
    for entry in host.get("names") or []:
        if isinstance(entry, dict) and entry.get("name"):
            parts.append(str(entry["name"]))
    sig = " ".join(parts).lower()

    for keywords, brand, model, category, icon in _SIGNATURE_RULES:
        if any(kw in sig for kw in keywords):
            return DeviceClassification(
                brand=brand,
                model=model,
                category=category,
                icon=icon,
            )

    vendor = str(host.get("vendor_name") or "").strip()
    host_type = str(host.get("host_type") or "").strip()
    return DeviceClassification(
        brand=vendor or "Inconnu",
        model=host_type or "Périphérique réseau",
        category=host_type or "Réseau",
        icon=host_type_icon(host_type, active),
    )
