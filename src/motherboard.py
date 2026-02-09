import serial
import struct
import time
from serial.tools.list_ports import comports
import nanokicker


class Motherboard:
    """
    Manages the connection to the motherboard and all attached NanoKicker devices.
    """

    MAX_DEVICES = 20

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
            print("Error: Could not find Raspberry Pi Pico motherboard.")

    def _find_pico_port(self):
        """Automatically find the COM port for the Raspberry Pi Pico."""
        print("Searching for Raspberry Pi Pico motherboard...")
        ports = comports()
        for port in ports:
            if "Pico" in port.description or "Serial" in port.description:
                print(f"Found motherboard on {port.device}")
                return port.device
        return None

    def connect(self):
        """Establishes a serial connection with the motherboard."""
        if not self.port:
            print("Error: No serial port specified or found.")
            return
        try:
            # The motherboard firmware doesn't care about the baud rate for USB CDC
            self.serial = serial.Serial(self.port, timeout=1)
            print(f"Successfully connected to {self.port}")
        except serial.SerialException as e:
            self.serial = None
            print(f"Error opening serial port {self.port}: {e}")

    def disconnect(self):
        """Closes the serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Disconnected from motherboard.")
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
            print("Error: Not connected to motherboard.")
            return None

        command = struct.pack(">BBI", device_id, action, value)
        print(f"Sending command: {command.hex()}")

        try:
            # Clear the input buffer to ensure we don't read stale data or debug messages
            self.serial.reset_input_buffer()
            self.serial.write(command)
            self.serial.flush()

            # The motherboard firmware prints debug messages. We'll read them to keep the buffer clean.
            # We expect a specific response for "get" commands, or just debug text for "set" commands.
            if read_response:
                # For getters, the firmware sends back a 4-byte value directly.
                response_bytes = self.serial.read(4)
                if len(response_bytes) == 4:
                    response = struct.unpack(">I", response_bytes)[0]
                    print(f"Motherboard response: {response_bytes}")
                    print(f"Motherboard response (int): {response}")
                    return response
                else:
                    # Also print any text that came instead of the bytes
                    print(
                        f"Motherboard (unexpected response): {response_bytes.decode('utf-8').strip()}"
                    )
                    return None
            else:
                # For setters, we just read the line of text it sends back.
                # This has a timeout, so it won't block forever.
                line = self.serial.readline().decode("utf-8").strip()
                if "error" in line:
                    print(f"Motherboard Error: {line}")
                return None

        except serial.SerialException as e:
            print(f"Serial error during command send: {e}")
            if self.serial is not None:
                self.disconnect()
                if self.disconnect_callback:
                    self.disconnect_callback()
            return None

    def scan_for_nanokickers(self):
        """
        Scans for connected NanoKicker devices by pinging each possible ID.
        A 'ping' is a 'get_mode' command, as it's a simple read operation.
        """
        if not (self.serial and self.serial.is_open):
            print("Error: Not connected to motherboard.")
            return

        print(f"Scanning for NanoKickers (0-{self.MAX_DEVICES - 1})...")
        self.nanokickers.clear()

        # 758254858 is the integer representation of "-2\r\n" (Big Endian), likely an error code.
        ERROR_RESPONSE_MINUS_1 = 758254857
        ERROR_RESPONSE_MINUS_2 = 4278190079
        ERROR_RESPONSE_MINUS_3 = 758254859

        for i in range(self.MAX_DEVICES):
            # The motherboard firmware handshake is the most reliable way to check for a device.
            # Pinging for a value is the next best thing. We'll try to get the mode.
            # A successful response indicates a device is present.
            print(f"Pinging device {i}...")
            response = self.send_command(
                device_id=i, action=21, read_response=True
            )  # action 21 is GET_MODE

            print("Response:", response)
            if response is not None and response != ERROR_RESPONSE_MINUS_2:
                print(f"Found NanoKicker at device_id {i}")
                kicker = nanokicker.NanoKicker(device_id=i, motherboard=self)
                kicker.mode = response  # We already have the mode, so store it.
                self.nanokickers[i] = kicker

            time.sleep(0.05)  # Small delay to not overwhelm the serial port

        print(f"Scan complete. Found {len(self.nanokickers)} device(s).")
        return self.nanokickers

    def __getitem__(self, key):
        """Allows accessing nanokickers like a dictionary, e.g., mb[0]."""
        return self.nanokickers.get(key)

    def __repr__(self):
        return f"Motherboard(port='{self.port}', connected={self.serial is not None}, devices={list(self.nanokickers.keys())})"
