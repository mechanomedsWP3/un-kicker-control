import struct


class NanoKicker:
    """A class to represent and control a single NanoKicker device."""

    def __init__(self, device_id: int, motherboard):
        if not (0 <= device_id < 20):
            raise ValueError("Device ID must be between 0 and 19.")

        self.device_id = device_id
        self.motherboard = motherboard

        # --- Device State ---
        self.mode = None
        self.frequency = None
        self.amplitude = None
        self.startup_enabled = None
        self.vin = None
        self.vout = None
        self.pot_range = None
        self.r_g_trim = None
        self.r_f_trim = None
        self.wiper = None

    def _send_command(
        self, action: int, value: int = 0, read_response: bool = False
    ):
        """Wrapper to call the motherboard's send_command method."""
        return self.motherboard.send_command(
            self.device_id, action, value, read_response
        )

    def _float_to_int(self, value: float) -> int:
        """Reinterprets the bits of a float as an integer (IEEE 754 Little Endian)."""
        return struct.unpack("<I", struct.pack("<f", value))[0]

    def _int_to_float(self, value: int) -> float:
        """Reinterprets the bits of an integer as a float (IEEE 754 Little Endian)."""
        return struct.unpack("<f", struct.pack("<I", value))[0]

    # --- SETTER Methods ---
    def set_mode(self, mode: int):
        """Sets the operational mode of the device."""
        self.mode = mode
        self._send_command(1, mode)

    def set_frequency(self, frequency: int):
        """Sets the output frequency in Hz."""
        self.frequency = frequency
        self._send_command(2, frequency)

    def set_amplitude(self, amplitude: float):
        """Sets the output amplitude."""
        self.amplitude = amplitude
        print("Setting amplitude to:", amplitude)
        self._send_command(3, self._float_to_int(amplitude))

    def set_wiper(self, wiper: int):
        """Sets wiper position"""
        self.wiper = wiper
        self._send_command(4, wiper)

    def set_startup_enabled(self, enabled: bool):
        """Configures whether the device is enabled on startup."""
        self.startup_enabled = enabled
        self._send_command(11, int(enabled))

    def set_vin(self, vin: float):
        self.vin = vin
        self._send_command(12, self._float_to_int(vin))

    def set_vout(self, vout: float):
        self.vout = vout
        self._send_command(13, self._float_to_int(vout))

    def set_pot_range(self, pot_range: float):
        self.pot_range = pot_range
        self._send_command(14, self._float_to_int(pot_range))

    def set_r_g_trim(self, trim: float):
        self.r_g_trim = trim
        self._send_command(15, self._float_to_int(trim))

    def set_r_f_trim(self, trim: float):
        self.r_f_trim = trim
        self._send_command(16, self._float_to_int(trim))

    def save_settings(self):
        """Saves the current settings to the device's non-volatile memory."""
        self._send_command(17)

    def load_settings(self):
        """Loads settings from the device's non-volatile memory."""
        self._send_command(18)

    # --- GETTER Methods ---
    def get_mode(self):
        self.mode = self._send_command(21, read_response=True)
        return self.mode

    def get_frequency(self):
        response = self._send_command(22, read_response=True)
        if response is not None:
            self.frequency = response
        return self.frequency

    def get_amplitude(self):
        response = self._send_command(23, read_response=True)
        if response is not None:
            self.amplitude = self._int_to_float(response)
        return self.amplitude

    def get_wiper(self):
        response = self._send_command(24, read_response=True)
        if response is not None:
            self.wiper = response
        return self.wiper

    def get_startup_enabled(self):
        self.startup_enabled = self._send_command(31, read_response=True)
        return self.startup_enabled

    def get_vin(self):
        response = self._send_command(32, read_response=True)
        if response is not None:
            self.vin = self._int_to_float(response)
        return self.vin

    def get_vout(self):
        response = self._send_command(33, read_response=True)
        if response is not None:
            self.vout = self._int_to_float(response)
        return self.vout

    def get_pot_range(self):
        response = self._send_command(34, read_response=True)
        if response is not None:
            self.pot_range = self._int_to_float(response)
        return self.pot_range

    def get_r_g_trim(self):
        response = self._send_command(35, read_response=True)
        if response is not None:
            self.r_g_trim = self._int_to_float(response)
        return self.r_g_trim

    def get_r_f_trim(self):
        response = self._send_command(36, read_response=True)
        if response is not None:
            self.r_f_trim = self._int_to_float(response)
        return self.r_f_trim

    def read_all_parameters(self):
        """Reads all parameters from the device and updates the object's state."""
        print(f"--- Reading all parameters for device {self.device_id} ---")
        self.get_mode()
        self.get_frequency()
        self.get_amplitude()
        self.get_startup_enabled()
        self.get_vin()
        self.get_vout()
        self.get_pot_range()
        self.get_r_g_trim()
        self.get_r_f_trim()
        self.get_wiper()
        print("--- Finished reading ---")

    def __repr__(self):
        return (
            f"NanoKicker(device_id={self.device_id}, "
            f"mode={self.mode}, "
            f"frequency={self.frequency}, "
            f"amplitude={self.amplitude})"
        )
