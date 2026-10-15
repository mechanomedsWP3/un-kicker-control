# Nano Kicker control

Libraries and GUI to control and configure the NanoKicker device.

The package talks to a NanoKicker **motherboard** (a Raspberry Pi Pico acting as a USB serial device) that hosts up to 10 NanoKicker devices. It provides:

- a Python library (`Motherboard`, `NanoKicker`) for scripting the hardware, and
- the **NanoKicker Control Center**, a PyQt5 desktop GUI built on top of it.

## Installation

Requirements:

- Python 3.8 or newer
- A NanoKicker motherboard connected over USB

Dependencies (`PyQt5` and `pyserial`) are installed automatically. Using a virtual environment is recommended.

### Linux / macOS

```bash
git clone <repository-url>
cd un-kicker-control

python3 -m venv .venv
source .venv/bin/activate

pip install .
```

**Linux only:** your user needs permission to open the serial port. Add yourself to the `dialout` group (`uucp` on Arch), then log out and back in:

```bash
sudo usermod -aG dialout $USER
```

If the GUI fails to start with a Qt "xcb" platform plugin error, install the missing system library, e.g. on Debian/Ubuntu: `sudo apt install libxcb-xinerama0 libxcb-cursor0`.

### Windows

Install Python from [python.org](https://www.python.org/downloads/) (tick "Add python.exe to PATH"), then in PowerShell:

```powershell
git clone <repository-url>
cd un-kicker-control

python -m venv .unk_venv
.unk_venv\Scripts\Activate.ps1

pip install .
```

If PowerShell refuses to run the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat` from Command Prompt. No extra USB driver is needed; the motherboard shows up as a `COM` port.

## Launching the GUI

With the virtual environment active, any of the following works on all platforms:

```bash
un-kicker-control
# or
python -m un_kicker_control
```

## Creating a desktop shortcut (Windows)

To open the GUI with a double-click instead of a terminal, create a shortcut that launches it with the virtual environment's `pythonw.exe` (the windowless Python, so no console window appears).

1. Right-click the desktop, choose **New → Shortcut**.
2. For the location, enter the full path to `pythonw.exe` in your virtual environment, followed by `-m un_kicker_control`, e.g.

   ```
   C:\path\to\un-kicker-control\.venv\Scripts\pythonw.exe -m un_kicker_control
   ```

3. Name it "NanoKicker Control" and finish.

To make it available from the Start menu, copy the shortcut into `%APPDATA%\Microsoft\Windows\Start Menu\Programs`. If you move or recreate the virtual environment, recreate the shortcut too.

## Using the GUI

### 1. Connect to the motherboard

1. Plug in the motherboard. The **Motherboard Port** drop-down lists available serial ports and automatically selects a Raspberry Pi Pico if it finds one. Click **Refresh** if you plugged it in after launching.
2. Click **Connect**. The status line shows `Connected` and how many devices are responding.
3. Click **Disconnect** when done. If the connection drops unexpectedly the status shows `Connection Lost`; reconnect with **Connect**.

Tick **Show Logs** to reveal a log panel at the bottom of the window, useful for diagnosing communication problems.

### 2. The device grid

The left side shows one tile per motherboard slot (0-9), displaying each device's current **mode**, **frequency** and **amplitude**. The motherboard is polled once per second, so devices appear, disappear and update automatically; there is no manual scan. Responding devices are listed first; slots with nothing attached are dimmed and marked "Not found".

Tiles are read-only; clicking one *selects* it:

- **Click** a tile to select only that device.
- **Ctrl-click** (Cmd-click on macOS) to add or remove devices from the selection.

### 3. Controlling devices

The panel on the right controls whichever devices are selected (its header shows e.g. `Editing: NanoKicker #3` or `Editing 2 devices: 1, 4`). It is disabled until a device is selected.

| Field | Meaning |
| --- | --- |
| Frequency (Hz) | Output frequency, 0-200000 Hz |
| Amplitude | Output amplitude, measured from 0 to the positive peak (half the peak-to-peak voltage) |
| Mode | Off, Sine, Square, Triangle or Pulsed |
| Pulse Period (s) | Pulsed mode only: how often the output toggles on/off |
| Pulse Length (s) | Pulsed mode only: how long the output stays on within each period |

Changes are sent as you make them: press **Enter** or leave a text field to apply it, and picking a mode applies it immediately. **Set** sends all the basic fields at once. When several devices are selected, the values are sent to all of them; the panel shows the first selected device's values.

Two buttons at the top of the window act on **every responding device**, regardless of selection:

- **Apply to All** sends the panel's frequency, amplitude, mode and pulse timing to all devices.
- **Stop All** sets every device to **Off**. Use it as an emergency stop.

### 4. Advanced settings (single device)

Tick **Advanced Settings** to show low-level parameters for one device. It is only available when exactly one device is selected (selecting a second device while it is open keeps only the first).

- **Startup Enabled**, **Vin**, **Vout**, **Pot Range**, **R_G Trim**, **R_F Trim**, **Wiper**: hardware parameters; click **Set Adv** to send them.
- **Save Mem** stores the device's current settings in its non-volatile memory so they survive a power cycle.
- **Load Mem** restores the saved settings and refreshes the panel.

## Using the library from Python

```python
from un_kicker_control.motherboard import Motherboard

mb = Motherboard()            # auto-detects a Raspberry Pi Pico, or pass port="COM3" / "/dev/ttyACM0"
print(mb.poll_devices())      # {device_id: {"responsive": ..., "mode": ..., ...}}

kicker = mb[0]                # NanoKicker in slot 0
kicker.set_frequency(1000)    # Hz
kicker.set_amplitude(5.0)
kicker.set_mode(1)            # 0 Off, 1 Sine, 2 Square, 3 Triangle, 4 Pulsed
kicker.read_all_parameters()
print(kicker)

mb.disconnect()
```

## Troubleshooting

- **No port listed / cannot connect:** check the USB cable, click **Refresh**, and on Linux confirm you are in the `dialout` group. Only one program can hold the serial port at a time.
- **0 devices responding:** the motherboard is connected but no NanoKicker answered; check power (the devices run from a 24 V supply) and their connections.
