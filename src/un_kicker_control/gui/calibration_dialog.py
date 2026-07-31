import logging

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QMessageBox,
    QHeaderView,
    QComboBox,
)
from PyQt5.QtGui import QIntValidator, QDoubleValidator

from ..calibration import AMPLITUDE_MAX, CalibrationStore

logger = logging.getLogger(__name__)


class CalibrationDialog(QDialog):
    """
    Manual, app-side voltage calibration for a single NanoKicker.

    Requires a working oscilloscope on the actuator's terminals: the user
    drives a known frequency/amplitude, reads the real voltage on the scope,
    and records the pair here. Once a few frequencies have been recorded, the
    "desired voltage" section inverts the interpolated correction curve so a
    real target voltage can be requested directly instead of guessing a
    commanded amplitude.
    """

    def __init__(self, control_panel, device_id, parent=None):
        super().__init__(parent)
        self.control_panel = control_panel
        self.device_id = device_id
        self.store = CalibrationStore()

        self.setWindowTitle(f"Voltage Calibration — NanoKicker #{self.device_id}")
        self.setMinimumWidth(480)

        self._init_ui()
        self._refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Requires an oscilloscope probing the actuator's terminals.\n"
            "1) Set a frequency and commanded amplitude, and send it to the device.\n"
            "2) Read the actual voltage on the scope and record it below.\n"
            "3) Repeat for the frequencies you plan to use."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # --- Record a calibration point ---
        add_group = QGroupBox("Record a calibration point")
        form = QFormLayout(add_group)

        self.freq_input = QLineEdit(self.control_panel.freq_input.text())
        self.freq_input.setValidator(QIntValidator(0, 200000))
        form.addRow("Frequency (Hz):", self.freq_input)

        self.commanded_input = QLineEdit(self.control_panel.amp_input.text())
        self.commanded_input.setValidator(QDoubleValidator(0.0, AMPLITUDE_MAX, 3))
        form.addRow("Commanded Amplitude:", self.commanded_input)

        self.send_button = QPushButton("Send to Device")
        self.send_button.setToolTip(
            "Drive the device at this frequency/amplitude so it can be measured."
        )
        self.send_button.clicked.connect(self._send_to_device)
        form.addRow(self.send_button)

        self.measured_input = QLineEdit()
        self.measured_input.setValidator(QDoubleValidator(0.0, 1000.0, 3))
        self.measured_unit_combo = QComboBox()
        # Calibration points are stored internally as peak-to-peak, matching
        # the device's own "Amplitude" setpoint, but a scope reading is just
        # as often taken as a single-sided (0-to-peak) amplitude.
        self.measured_unit_combo.addItems(["Peak-to-Peak (Vpp)", "Amplitude (0-Peak)"])
        measured_row = QHBoxLayout()
        measured_row.addWidget(self.measured_input)
        measured_row.addWidget(self.measured_unit_combo)
        form.addRow("Measured Voltage (scope):", measured_row)

        self.add_button = QPushButton("Add Point")
        self.add_button.clicked.connect(self._add_point)
        form.addRow(self.add_button)

        layout.addWidget(add_group)

        # --- Existing points ---
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Frequency (Hz)", "Commanded", "Measured (Vpp)", "Gain"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.remove_button = QPushButton("Remove Selected Point")
        self.remove_button.clicked.connect(self._remove_selected)
        layout.addWidget(self.remove_button)

        # --- Apply a desired actuator voltage ---
        apply_group = QGroupBox("Apply a desired actuator voltage")
        apply_form = QFormLayout(apply_group)

        self.desired_input = QLineEdit()
        self.desired_input.setValidator(QDoubleValidator(0.0, 1000.0, 3))
        apply_form.addRow("Desired Voltage (V):", self.desired_input)

        self.preview_label = QLabel("—")
        apply_form.addRow("Commanded amplitude would be:", self.preview_label)

        preview_button = QPushButton("Preview")
        preview_button.clicked.connect(self._preview_commanded)
        self.apply_button = QPushButton("Compute && Apply")
        self.apply_button.clicked.connect(self._apply_desired_voltage)

        btn_row = QHBoxLayout()
        btn_row.addWidget(preview_button)
        btn_row.addWidget(self.apply_button)
        apply_form.addRow(btn_row)

        layout.addWidget(apply_group)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _refresh_table(self):
        points = self.store.points(self.device_id)
        self.table.setRowCount(len(points))
        for row, point in enumerate(points):
            self.table.setItem(row, 0, QTableWidgetItem(str(point["frequency"])))
            self.table.setItem(
                row, 1, QTableWidgetItem(f"{point['commanded_amplitude']:.3f}")
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(f"{point['measured_voltage']:.3f}")
            )
            self.table.setItem(row, 3, QTableWidgetItem(f"{point['gain']:.4f}"))

    def _send_to_device(self):
        try:
            frequency = int(self.freq_input.text())
            amplitude = float(self.commanded_input.text())
        except ValueError:
            QMessageBox.warning(
                self, "Invalid input", "Enter a valid frequency and amplitude."
            )
            return
        self.control_panel._send(self.device_id, "set_frequency", frequency)
        self.control_panel._send(self.device_id, "set_amplitude", amplitude)

    def _add_point(self):
        try:
            frequency = int(self.freq_input.text())
            commanded = float(self.commanded_input.text())
            measured = float(self.measured_input.text())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid input",
                "Enter valid frequency, commanded, and measured values.",
            )
            return
        # Normalize to peak-to-peak before storing, since that's the unit
        # commanded_amplitude (and the device's own Amplitude setpoint) uses.
        if self.measured_unit_combo.currentText().startswith("Amplitude"):
            measured *= 2
        try:
            self.store.add_point(self.device_id, frequency, commanded, measured)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid input", str(e))
            return
        self._refresh_table()

    def _remove_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.store.remove_point(self.device_id, row)
        self._refresh_table()

    def _compute_commanded(self):
        try:
            frequency = int(self.freq_input.text())
            desired = float(self.desired_input.text())
        except ValueError:
            QMessageBox.warning(
                self, "Invalid input", "Enter a valid frequency and desired voltage."
            )
            return None
        commanded = self.store.commanded_amplitude_for(self.device_id, frequency, desired)
        if commanded is None:
            QMessageBox.information(
                self,
                "No calibration data",
                "Record at least one calibration point for this device first.",
            )
            return None
        if not (0.0 < commanded <= AMPLITUDE_MAX):
            QMessageBox.warning(
                self,
                "Out of range",
                f"The required commanded amplitude ({commanded:.2f}) is outside "
                f"the device's 0-{AMPLITUDE_MAX:g} range at this frequency. "
                "This voltage isn't reachable here.",
            )
            return None
        return frequency, commanded

    def _preview_commanded(self):
        result = self._compute_commanded()
        if result is None:
            return
        _, commanded = result
        self.preview_label.setText(f"{commanded:.3f}")

    def _apply_desired_voltage(self):
        result = self._compute_commanded()
        if result is None:
            return
        frequency, commanded = result
        self.preview_label.setText(f"{commanded:.3f}")
        self.control_panel._send(self.device_id, "set_frequency", frequency)
        self.control_panel._send(self.device_id, "set_amplitude", commanded)
        self.control_panel.freq_input.setText(str(frequency))
        self.control_panel.amp_input.setText(f"{commanded:.2f}")
