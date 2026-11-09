"""Constants for Ubuntu Linux SSH."""
from datetime import timedelta

DOMAIN = "ubuntu_linux"
DEFAULT_PORT = 22
DEFAULT_USER = "ha-monitor"
SCAN_INTERVAL = timedelta(seconds=60)
KEY_DIRECTORY = ".storage/ubuntu_linux_keys"
COMMAND = "/usr/local/bin/ha-ubuntu-monitor"
