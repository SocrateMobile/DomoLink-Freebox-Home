"""Constants for the DomoLink Freebox Home integration."""

from datetime import timedelta

DOMAIN = "domolink_freebox_home"
MANUFACTURER = "Freebox SAS"

DEFAULT_HOST = "mafreebox.freebox.fr"
DEFAULT_PORT = 80
DEFAULT_USE_HTTPS = False

APP_ID = "fr.domolink.freebox_home"
APP_NAME = "DomoLink Freebox Home"
APP_VERSION = "1.0.0"
DEVICE_NAME = "Home Assistant"

CONF_APP_TOKEN = "app_token"
CONF_API_VERSION = "api_version"
CONF_USE_HTTPS = "use_https"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
