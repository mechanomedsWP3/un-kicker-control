import logging
import sys
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QComboBox,
    QCheckBox,
    QLabel,
    QFrame,
)
from PyQt5.QtCore import (
    QThread,
    QObject,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtSlot,
    Qt,
)

from ..motherboard import Motherboard
from .device_tile import DeviceTile
from .control_panel import ControlPanel
from .log_widget import LogPanel

logger = logging.getLogger(__name__)

# The device grid is indexed by device_id and is this many columns wide
# (Motherboard.MAX_DEVICES devices, so 5 columns gives 2 rows).
GRID_COLUMNS = 5

POLL_INTERVAL_MS = 1000
REFLOW_DURATION_MS = 300


class Worker(QObject):
    """
    A worker object that performs long-running tasks in a separate thread.

    Every NanoKicker command (from the GUI) is funneled through this single
    worker thread, so serial I/O never blocks the GUI event loop and calls
    to the shared serial port stay serialized.
    """

    ports_found = pyqtSignal(list, str)  # ports, auto-detected pico port (or "")
    connection_status = pyqtSignal(bool, str)
    poll_ready = pyqtSignal(dict)  # {device_id: {"responsive", "mode", "frequency", "amplitude"}}
    parameters_ready = pyqtSignal(int, dict)  # device_id, parameter dict

    def __init__(self):
        super().__init__()
        self.motherboard = None

    def _handle_disconnect(self):
        """Callback for when motherboard detects disconnection."""
        self.connection_status.emit(False, "Connection Lost")
        self.motherboard = None

    def _get_kicker(self, device_id):
        return self.motherboard[device_id] if self.motherboard else None

    @staticmethod
    def _kicker_to_dict(kicker):
        return {
            "mode": kicker.mode,
            "frequency": kicker.frequency,
            "amplitude": kicker.amplitude,
            "startup_enabled": kicker.startup_enabled,
            "vin": kicker.vin,
            "vout": kicker.vout,
            "pot_range": kicker.pot_range,
            "r_g_trim": kicker.r_g_trim,
            "r_f_trim": kicker.r_f_trim,
            "wiper": kicker.wiper,
        }

    @pyqtSlot()
    def find_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        preferred = Motherboard.find_pico_port() or ""
        self.ports_found.emit(ports, preferred)

    @pyqtSlot(str)
    def connect_motherboard(self, port):
        self.motherboard = Motherboard(
            port=port, disconnect_callback=self._handle_disconnect
        )
        if self.motherboard and self.motherboard.serial:
            self.connection_status.emit(True, f"Connected to {port}")
        else:
            self.connection_status.emit(False, "Failed to connect.")
            self.motherboard = None

    @pyqtSlot()
    def poll_devices(self):
        if self.motherboard:
            self.poll_ready.emit(self.motherboard.poll_devices())

    @pyqtSlot()
    def disconnect_motherboard(self):
        if self.motherboard:
            self.motherboard.disconnect()
        self.connection_status.emit(False, "Disconnected")

    @pyqtSlot(int, str, object)
    def call_setter(self, device_id, method_name, value):
        """Call a single NanoKicker setter method (e.g. 'set_frequency') by name."""
        kicker = self._get_kicker(device_id)
        if kicker is None:
            return
        method = getattr(kicker, method_name, None)
        if method is None:
            logger.error("Unknown NanoKicker method: %s", method_name)
            return
        method() if value is None else method(value)

    @pyqtSlot(int)
    def read_parameters(self, device_id):
        kicker = self._get_kicker(device_id)
        if kicker is None:
            return
        kicker.read_all_parameters()
        self.parameters_ready.emit(device_id, self._kicker_to_dict(kicker))

    @pyqtSlot(int)
    def load_settings(self, device_id):
        kicker = self._get_kicker(device_id)
        if kicker is None:
            return
        kicker.load_settings()
        kicker.read_all_parameters()
        self.parameters_ready.emit(device_id, self._kicker_to_dict(kicker))


class MainWindow(QMainWindow):
    """
    The main application window for controlling the NanoKicker motherboard.

    The grid always shows all Motherboard.MAX_DEVICES slots and only ever
    displays state (mode/frequency/amplitude); every command is issued
    through the single shared ControlPanel, targeting whichever device(s)
    are currently selected in the grid.
    """

    # Signals to trigger tasks in the worker thread
    trigger_find_ports = pyqtSignal()
    trigger_connect = pyqtSignal(str)
    trigger_poll = pyqtSignal()
    trigger_disconnect = pyqtSignal()
    trigger_call_setter = pyqtSignal(int, str, object)  # device_id, method_name, value
    trigger_get_parameters = pyqtSignal(int)
    trigger_load_settings = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NanoKicker Control Center")
        self.setMinimumSize(900, 600)

        self.tiles = {}  # device_id -> DeviceTile, all MAX_DEVICES created up front
        self.selected_device_ids = []  # ordered: [0] is "the first one selected"
        self.responsive_device_ids = set()
        self.last_poll_results = {}
        self._polling = False
        self._tile_animations = {}  # device_id -> in-flight QPropertyAnimation

        self._init_ui()
        self._init_worker_thread()

        # setMinimumSize() above effectively resizes the (still-empty) window
        # immediately, before the grid/control panel exist -- without this,
        # the window would stay clamped at that stale size instead of
        # growing to fit the fully-built content computed just above.
        self.resize(self.sizeHint())

    def _init_ui(self):
        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Control Panel: connection + global actions ---
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_panel_layout = QVBoxLayout(control_panel)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Motherboard Port:"))
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)

        connection_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)

        self.status_label = QLabel("Status: Not Connected")

        # Apply to All / Stop All: act on every responsive device regardless
        # of the current grid selection (unlike the ControlPanel's own Set
        # button, which only targets the selection).
        broadcast_layout = QHBoxLayout()
        self.apply_all_button = QPushButton("Apply to All")
        self.apply_all_button.setEnabled(False)
        self.apply_all_button.setToolTip(
            "Send the shared panel's frequency/amplitude/mode to every "
            "responsive device, regardless of the current selection."
        )
        self.stop_all_button = QPushButton("Stop All")
        self.stop_all_button.setStyleSheet(
            "QPushButton { color: #b00020; font-weight: bold; }"
        )
        broadcast_layout.addWidget(self.apply_all_button)
        broadcast_layout.addWidget(self.stop_all_button)

        self.show_logs_checkbox = QCheckBox("Show Logs")

        control_panel_layout.addLayout(port_layout)
        control_panel_layout.addLayout(connection_layout)
        control_panel_layout.addLayout(broadcast_layout)
        control_panel_layout.addWidget(self.status_label)
        control_panel_layout.addWidget(self.show_logs_checkbox)

        main_layout.addWidget(control_panel)

        # --- Device grid (left) + shared command panel (right) ---
        # No scroll area: the grid always holds exactly MAX_DEVICES tiles,
        # so it's sized to its natural content instead of being scrollable.
        body_layout = QHBoxLayout()

        self.kicker_container = QWidget()
        self.kicker_layout = QGridLayout(self.kicker_container)
        self.kicker_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        body_layout.addWidget(self.kicker_container, 2)

        self.control_panel = ControlPanel(self)
        self.control_panel.setMinimumWidth(300)
        self.control_panel.setMaximumWidth(360)
        body_layout.addWidget(self.control_panel, 1)

        main_layout.addLayout(body_layout)

        # --- Log Panel (hidden by default) ---
        self.log_panel = LogPanel()
        self.log_panel.attach()
        self.log_panel.setVisible(False)
        self.log_panel.setMinimumHeight(150)
        self.log_panel.setMaximumHeight(250)
        main_layout.addWidget(self.log_panel)

        # --- Connections ---
        self.refresh_button.clicked.connect(self.find_ports)
        self.connect_button.clicked.connect(self.connect_to_motherboard)
        self.disconnect_button.clicked.connect(self.disconnect_from_motherboard)
        self.apply_all_button.clicked.connect(self.apply_to_all)
        self.stop_all_button.clicked.connect(self.stop_all)
        self.show_logs_checkbox.toggled.connect(self._on_show_logs_toggled)

        # --- Build the always-present grid, one tile per possible slot ---
        for device_id in range(Motherboard.MAX_DEVICES):
            self.tiles[device_id] = DeviceTile(device_id, self)
        self._relayout_grid()

    def _init_worker_thread(self):
        self.worker_thread = QThread()
        self.worker = Worker()

        self.worker.moveToThread(self.worker_thread)

        # Connect worker signals to main thread slots
        self.worker.ports_found.connect(self.update_port_list)
        self.worker.connection_status.connect(self.on_connection_status_changed)
        self.worker.poll_ready.connect(self.on_poll_ready)
        self.worker.parameters_ready.connect(self.on_parameters_ready)

        # Connect main thread signals to worker slots
        self.trigger_find_ports.connect(self.worker.find_ports)
        self.trigger_connect.connect(self.worker.connect_motherboard)
        self.trigger_poll.connect(self.worker.poll_devices)
        self.trigger_disconnect.connect(self.worker.disconnect_motherboard)
        self.trigger_call_setter.connect(self.worker.call_setter)
        self.trigger_get_parameters.connect(self.worker.read_parameters)
        self.trigger_load_settings.connect(self.worker.load_settings)

        self.worker_thread.start()
        self.find_ports()  # Initial port scan

    # --- Connection lifecycle ---

    def find_ports(self):
        self.refresh_button.setEnabled(False)
        self.trigger_find_ports.emit()

    def connect_to_motherboard(self):
        port = self.port_combo.currentText()
        if port:
            self.connect_button.setEnabled(False)
            self.port_combo.setEnabled(False)
            self.trigger_connect.emit(port)

    def disconnect_from_motherboard(self):
        self._stop_polling()
        self._reset_devices()
        self.trigger_disconnect.emit()

    def update_port_list(self, ports, preferred):
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if preferred and preferred in ports:
            self.port_combo.setCurrentIndex(ports.index(preferred))
        self.refresh_button.setEnabled(True)

    def on_connection_status_changed(self, is_connected, message):
        self.status_label.setText(f"Status: {message}")
        self.connect_button.setEnabled(not is_connected)
        self.disconnect_button.setEnabled(is_connected)
        self.port_combo.setEnabled(not is_connected)
        self.refresh_button.setEnabled(not is_connected)

        if is_connected:
            self._start_polling()
        else:
            self._stop_polling()
            self._reset_devices()

    # --- 1Hz polling: doubles as continuous discovery ---

    def _start_polling(self):
        self._polling = True
        self._poll_now()

    def _stop_polling(self):
        self._polling = False

    def _poll_now(self):
        if self._polling:
            self.trigger_poll.emit()

    def on_poll_ready(self, results):
        self.last_poll_results = results
        self.responsive_device_ids = {
            device_id for device_id, r in results.items() if r.get("responsive")
        }

        still_valid = [d for d in self.selected_device_ids if d in self.responsive_device_ids]
        if still_valid != self.selected_device_ids:
            self.selected_device_ids = still_valid
            self._update_selection_ui()

        for device_id, tile in self.tiles.items():
            r = results.get(device_id, {})
            tile.set_data(
                r.get("mode"), r.get("frequency"), r.get("amplitude"),
                r.get("responsive", False),
            )
        self._relayout_grid()

        self.status_label.setText(
            f"Status: Connected. {len(self.responsive_device_ids)} device(s) responding."
        )
        self.apply_all_button.setEnabled(bool(self.responsive_device_ids))

        if self._polling:
            QTimer.singleShot(POLL_INTERVAL_MS, self._poll_now)

    def _reset_devices(self):
        self.selected_device_ids = []
        self.responsive_device_ids = set()
        self.last_poll_results = {}
        for tile in self.tiles.values():
            tile.set_data(None, None, None, False)
        self._relayout_grid()
        self._update_selection_ui()
        self.apply_all_button.setEnabled(False)

    def _relayout_grid(self):
        """Active devices first (by id), inactive ones after (by id).

        Tiles that actually change cell slide to their new position instead
        of jumping there, by snapping the layout to its new state instantly
        and then animating each moved tile back from where it visually was.
        """
        old_positions = {device_id: tile.pos() for device_id, tile in self.tiles.items()}

        ordered = sorted(
            self.tiles.keys(), key=lambda d: (d not in self.responsive_device_ids, d)
        )
        for index, device_id in enumerate(ordered):
            row, col = divmod(index, GRID_COLUMNS)
            self.kicker_layout.addWidget(self.tiles[device_id], row, col, Qt.AlignTop)
        self.kicker_layout.activate()  # resolve new geometries synchronously

        for device_id, tile in self.tiles.items():
            new_pos = tile.pos()
            old_pos = old_positions[device_id]
            if new_pos != old_pos:
                self._animate_tile_move(tile, old_pos, new_pos)

    def _animate_tile_move(self, tile, old_pos, new_pos):
        previous = self._tile_animations.pop(tile.device_id, None)
        if previous is not None:
            previous.stop()

        tile.move(old_pos)  # undo activate()'s instant jump; animate from here
        anim = QPropertyAnimation(tile, b"pos", self)
        anim.setDuration(REFLOW_DURATION_MS)
        anim.setStartValue(old_pos)
        anim.setEndValue(new_pos)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.finished.connect(lambda: self._tile_animations.pop(tile.device_id, None))
        self._tile_animations[tile.device_id] = anim
        anim.start()

    # --- Window growth: newly revealed panels (advanced settings, logs)
    # push the window taller instead of squeezing existing content, so
    # fields don't need a manual resize to stay readable. ---

    def _on_show_logs_toggled(self, checked):
        self.log_panel.setVisible(checked)
        self.grow_or_shrink_for(self.log_panel, checked)

    def grow_or_shrink_for(self, widget, growing):
        delta = max(widget.sizeHint().height(), widget.minimumHeight())
        if delta <= 0:
            return
        if growing:
            self.resize(self.width(), self.height() + delta)
        else:
            self.resize(self.width(), max(self.minimumHeight(), self.height() - delta))

    # --- Selection ---

    def select_kicker(self, device_id, additive=False):
        if device_id not in self.responsive_device_ids:
            return
        # Advanced settings are single-device only: while that section is
        # open, every click replaces the selection instead of extending it.
        if self.control_panel.advanced_checkbox.isChecked():
            additive = False

        if additive:
            if device_id in self.selected_device_ids:
                self.selected_device_ids.remove(device_id)
            else:
                self.selected_device_ids.append(device_id)
        else:
            self.selected_device_ids = [device_id]

        self._update_selection_ui()

    def _update_selection_ui(self):
        for device_id, tile in self.tiles.items():
            tile.set_selected(device_id in self.selected_device_ids)

        self.control_panel.set_target_devices(self.selected_device_ids)

        if self.selected_device_ids:
            first_id = self.selected_device_ids[0]
            last = self.last_poll_results.get(first_id, {})
            self.control_panel.load_basic_from(
                last.get("mode"), last.get("frequency"), last.get("amplitude")
            )
            if len(self.selected_device_ids) == 1 and self.control_panel.advanced_checkbox.isChecked():
                self.trigger_get_parameters.emit(first_id)

    def on_parameters_ready(self, device_id, params):
        if self.selected_device_ids == [device_id]:
            self.control_panel.load_basic_from(
                params.get("mode"), params.get("frequency"), params.get("amplitude")
            )
            self.control_panel.load_advanced_from_dict(params)

    # --- Global actions (selection-independent) ---

    def apply_to_all(self):
        try:
            frequency, amplitude, mode = self.control_panel.get_basic_values()
        except ValueError:
            logger.warning("Invalid input for frequency or amplitude.")
            return
        for device_id in self.responsive_device_ids:
            self.trigger_call_setter.emit(device_id, "set_frequency", frequency)
            self.trigger_call_setter.emit(device_id, "set_amplitude", amplitude)
            self.trigger_call_setter.emit(device_id, "set_mode", mode)

    def stop_all(self):
        for device_id in self.responsive_device_ids:
            self.trigger_call_setter.emit(device_id, "set_mode", 0)

    def closeEvent(self, event):
        """Ensure worker thread and polling are cleaned up on exit."""
        self._stop_polling()
        self.disconnect_from_motherboard()
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.log_panel.detach()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
