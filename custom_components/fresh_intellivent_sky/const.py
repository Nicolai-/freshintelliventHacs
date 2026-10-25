"""Constants for the Fresh Intellivent Sky integration."""

DOMAIN = "fresh_intellivent_sky"

NAME = ["Intellivent SKY", "Intellivent ICE"]

DISPATCH_DETECTION = f"{DOMAIN}.detection"

DEFAULT_SCAN_INTERVAL = 120
TIMEOUT = 30.0
DEFAULT_CACHE_DEVICE_INFO = True
DEFAULT_MAX_UPDATE_RETRIES = 2
# Failed reads come in short spells, so a retry right away rarely helps.
UPDATE_RETRY_DELAY = 5.0
# The fan often rejects the first read after the auth write with GATT
# "Unlikely Error", so give it a moment and retry that read in place.
AUTH_SETTLE_DELAY = 1.0
SENSOR_READ_ATTEMPTS = 3
SENSOR_READ_RETRY_DELAY = 1.0

AUTH_MANUAL = "auth_manual"
AUTH_FETCH = "auth_fetch"
NO_AUTH = "no_auth"
AUTH_CODE_ONLY_ZERO = "auth_code_only_zero"
AUTH_CODE_EMPTY = "auth_code_empty"

CONF_AUTH_KEY = "auth_key"
CONF_CACHE_DEVICE_INFO = "cache_device_info"
CONF_MAX_UPDATE_RETRIES = "max_update_retries"
CONF_SCAN_INTERVAL = "scan_interval"

DETECTION_OFF = "Off"

BOOST_UPDATE = "boost_update"
CONSTANT_SPEED_UPDATE = "constant_speed_update"
PAUSE_UPDATE = "pause_update"

# Last known boost configuration, kept separately from the reported state
# because the fan reports the *remaining* time while a boost is running.
BOOST_SETTINGS = "boost_settings"

# Values the official app writes when the boost button is pressed. It asks for
# 2500 RPM, which the fan (and pyfreshintellivent) clamps to the 2400 maximum.
BOOST_RPM_DEFAULT = 2400
BOOST_SECONDS_DEFAULT = 600

BOOST_RPM_MIN = 800
BOOST_RPM_MAX = 2400
BOOST_SECONDS_MIN = 60
BOOST_SECONDS_MAX = 3600

AIRING_MODE_UPDATE = "airing_update"
HUMIDITY_MODE_UPDATE = "humidity_mode_update"
LIGHT_AND_VOC_MODE_UPDATE = "light_and_voc_mode_update"
TIMER_MODE_UPDATE = "timer_mode_update"

DETECTION_KEY = "detection"
ENABLED_KEY = "enabled"
DELAY_KEY = "delay"
RPM_KEY = "rpm"
MINUTES_KEY = "minutes"
SECONDS_KEY = "seconds"
