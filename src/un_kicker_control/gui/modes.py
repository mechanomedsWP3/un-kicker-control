# Device mode values (SET_MODE/GET_MODE), matching MODE_* in the firmware's
# communication-protocol.hpp. Pulsed alternates the DDS between off and sine
# at a configurable pulse frequency/duty cycle (see the Advanced section's
# Pulse Frequency/Duty Cycle fields), using whatever carrier frequency and
# amplitude are already set.
#
# The UI dropdown index and the device mode value are identical (0-4), so
# both maps below are simple identities -- kept as separate maps rather than
# passing the raw int through so a future divergence stays a one-line change.
MODE_NAMES = {0: "Off", 1: "Sine", 2: "Square", 3: "Triangle", 4: "Pulsed"}
UI_INDEX_TO_DEVICE_MODE = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
DEVICE_MODE_TO_UI_INDEX = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
