# AD9833 mode values as sent/read from the device, and how they map to the
# shared control panel's 4-item dropdown (Off, Sine, Square, Triangle).
# Device values 2 and 3 are both square-wave variants and both render as
# "Square" in the UI, since this app doesn't distinguish between them.
MODE_NAMES = {0: "Off", 1: "Sine", 2: "Square", 3: "Square", 4: "Triangle"}
UI_INDEX_TO_DEVICE_MODE = {0: 0, 1: 1, 2: 2, 3: 4}
DEVICE_MODE_TO_UI_INDEX = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3}
