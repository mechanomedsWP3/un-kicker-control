import logging
import serial
import struct
from serial.tools.list_ports import comports
from . import nanokicker

logger = logging.getLogger(__name__)


class Motherboard:
    """
    Manages the connection to the motherboard and all attached NanoKicker devices.
    """

    MAX_DEVICES = 10

    # GET_MODE (and any other getter) returns one of these in place of real
    # device data when a slot doesn't respond: the motherboard's raw int32
    # error codes -1 (bad id), -2 (handshake failure), -3 (SPI ack mismatch),
    # misread as big-endian unsigned by send_command()'s getter path.
    ERROR_RESPONSE_MINUS_1 = 758254857
    ERROR_RESPONSE_MINUS_2 = 4278190079
    ERROR_RESPONSE_MINUS_3 = 758254859

    def __init__(self, port: str = None, disconnect_callback=None):
        self.port = port
        self.serial = None
        self.nanokickers = {}  # Using a dict to store kickers by device_id
        self.disconnect_callback = disconnect_callback

        if not self.port:
            self.port = self._find_pico_port()

        if self.port:
            self.connect()
        else:
            logger.error("Could not find Raspberry Pi Pico motherboard.")

    PICO_VID = 0x2E8A  # Raspberry Pi Foundation USB vendor ID

    @classmethod
    def find_pico_port(cls):
        """Return the first COM port belonging to a Raspberry Pi Pico, or None."""
        for port in comports():
            if port.vid == cls.PICO_VID or "Pico" in (port.description or ""):
                return port.device
        return None

    def _find_pico_port(self):
        return self.__class__.find_pico_port()

    def connect(self):
        """Establishes a serial connection with the motherboard."""
        if not self.port:
            logger.error("No serial port specified or found.")
            return
        try:
            # The motherboard firmware doesn't care about the baud rate for USB CDC
            self.serial = serial.Serial(self.port, timeout=1)
            logger.info("Successfully connected to %s", self.port)
        except serial.SerialException as e:
            self.serial = None
            logger.error("Error opening serial port %s: %s", self.port, e)

    def disconnect(self):
        """Closes the serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected from motherboard.")
            self.serial = None

    def send_command(
        self,
        device_id: int,
        action: int,
        value: int = 0,
        read_response: bool = False,
    ):
        """
        Sends a command to a specific NanoKicker device via the motherboard.

        Args:
            device_id: The ID of the target NanoKicker (0-19).
            action: The command action code.
            value: The integer value for the command.
            read_response: Whether to wait for and read a 4-byte response.

        Returns:
            The integer response from the device if read_response is True, otherwise None.
        """
        if not (self.serial and self.serial.is_open):
            logger.error("Not connected to motherboard.")
            return None

        command = struct.pack(">BBI", device_id, action, value)
        # Lazy %-formatting means this costs nothing unless DEBUG logging is enabled.
        logger.debug("Sending command: %s", command.hex())

        try:
            # Clear the input buffer to ensure we don't read stale data or debug messages
            self.serial.reset_input_buffer()
            self.serial.write(command)
            self.serial.flush()

            # Getters get a 4-byte big-endian value straight from the device.
            # Setters get a 4-byte little-endian int32 ack from the motherboard
            # itself (0 on success, a negative error code on failure) -- both
            # are fixed-length binary replies, so both are read the same way.
            if read_response:
                response_bytes = self.serial.read(4)
                if len(response_bytes) == 4:
                    response = struct.unpack(">I", response_bytes)[0]
                    logger.debug("Motherboard response: %s (%d)", response_bytes, response)
                    return response
                else:
                    logger.warning(
                        "Motherboard (unexpected response): %s",
                        response_bytes.decode("utf-8", errors="replace").strip(),
                    )
                    return None
            else:
                response_bytes = self.serial.read(4)
                if len(response_bytes) == 4:
                    status = struct.unpack("<i", response_bytes)[0]
                    if status != 0:
                        logger.warning(
                            "Motherboard Error: setter failed (code %d) for device %d action %d",
                            status, device_id, action,
                        )
                else:
                    logger.warning(
                        "Motherboard: no acknowledgment for setter (device %d action %d)",
                        device_id, action,
                    )
                return None

        except serial.SerialException as e:
            logger.error("Serial error during command send: %s", e)
            if self.serial is not None:
                self.disconnect()
                if self.disconnect_callback:
                    self.disconnect_callback()
            return None

    def poll_devices(self):
        """
        Ping every possible device slot (0..MAX_DEVICES-1) for its basic
        parameters (mode, frequency, amplitude). This doubles as discovery:
        a slot going quiet is exactly what "no longer responsive" means, so
        there's no separate one-shot scan step -- this is called once on
        connect and then on every 1Hz poll tick.

        Returns {device_id: {"responsive": bool, "mode", "frequency",
        "amplitude"}}. Unresponsive slots report the last known values if
        the device has been seen before, or None if it never has been.
        """
        if not (self.serial and self.serial.is_open):
            logger.error("Not connected to motherboard.")
            return {}

        error_responses = (
            self.ERROR_RESPONSE_MINUS_1,
            self.ERROR_RESPONSE_MINUS_2,
            self.ERROR_RESPONSE_MINUS_3,
        )

        results = {}
        for device_id in range(self.MAX_DEVICES):
            # send_command already blocks for the response, so each ping is
            # fully synchronized with the device before the next one starts.
            response = self.send_command(
                device_id=device_id, action=21, read_response=True
            )  # action 21 is GET_MODE
            responsive = response is not None and response not in error_responses

            kicker = self.nanokickers.get(device_id)
            if responsive:
                if kicker is None:
                    logger.info("Found NanoKicker at device_id %d", device_id)
                    kicker = nanokicker.NanoKicker(device_id=device_id, motherboard=self)
                    self.nanokickers[device_id] = kicker
                kicker.mode = response
                kicker.get_frequency()
                kicker.get_amplitude()

            results[device_id] = {
                "responsive": responsive,
                "mode": kicker.mode if kicker else None,
                "frequency": kicker.frequency if kicker else None,
                "amplitude": kicker.amplitude if kicker else None,
            }

        return results

    def __getitem__(self, key):
        """Allows accessing nanokickers like a dictionary, e.g., mb[0]."""
        return self.nanokickers.get(key)

    def __repr__(self):
        return f"Motherboard(port='{self.port}', connected={self.serial is not None}, devices={list(self.nanokickers.keys())})"
