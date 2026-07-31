import logging

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
)
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5 import sip

from ..calibration import AMPLITUDE_MAX
from .modes import UI_INDEX_TO_DEVICE_MODE, DEVICE_MODE_TO_UI_INDEX
from .calibration_dialog import CalibrationDialog

logger = logging.getLogger(__name__)


class ControlPanel(QWidget):
    """
    The single interface used to command NanoKicker devices.

    Basic parameters (frequency, amplitude, mode) can be sent to however
    many devices are currently selected in the grid. Advanced parameters
    only make sense for one device at a time, so that section is only
    enabled while exactly one device is selected -- MainWindow enforces
    that a second selection collapses back down to the first, per
    select_kicker()'s "advanced settings are single-device" rule.
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._advanced_shown = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.target_label = QLabel("No device selected")
        self.target_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.target_label)

        # --- Basic parameters ---
        basic_group = QFrame()
        basic_group.setFrameShape(QFrame.StyledPanel)
        form = QFormLayout(basic_group)

        # Disabled until a device is selected -- otherwise an empty, editable
        # field is indistinguishable from one genuinely showing "no value".
        self.freq_input = QLineEdit()
        self.freq_input.setValidator(QIntValidator(0, 200000))
        self.freq_input.setEnabled(False)
        form.addRow("Frequency (Hz):", self.freq_input)

        self.amp_input = QLineEdit()
        self.amp_input.setValidator(QDoubleValidator(0.0, AMPLITUDE_MAX, 2))
        self.amp_input.setEnabled(False)
        form.addRow("Amplitude:", self.amp_input)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Off", "Sine", "Square", "Triangle"])
        self.mode_combo.setEnabled(False)
        form.addRow("Mode:", self.mode_combo)

        self.set_button = QPushButton("Set")
        self.set_button.setEnabled(False)
        self.set_button.clicked.connect(self._on_set_clicked)
        form.addRow(self.set_button)

        layout.addWidget(basic_group)

        # Frequency/amplitude apply as soon as Enter is pressed or the field
        # loses focus (editingFinished covers both); mode applies as soon as
        # it's picked from the dropdown ("activated" only fires on user
        # interaction, not on the setCurrentIndex() calls used to sync the
        # UI from a device read).
        self.freq_input.editingFinished.connect(self._apply_frequency)
        self.amp_input.editingFinished.connect(self._apply_amplitude)
        self.mode_combo.activated.connect(self._apply_mode)

        # --- Advanced parameters (single device only) ---
        self.advanced_checkbox = QCheckBox("Advanced Settings")
        self.advanced_checkbox.setEnabled(False)
        self.advanced_checkbox.toggled.connect(self._on_advanced_toggled)
        layout.addWidget(self.advanced_checkbox)

        self.advanced_frame = QFrame()
        self.advanced_frame.setFrameShape(QFrame.StyledPanel)
        self.advanced_frame.setVisible(False)
        adv_layout = QGridLayout(self.advanced_frame)

        self.startup_check = QCheckBox("Startup Enabled")
        adv_layout.addWidget(self.startup_check, 0, 0, 1, 2)

        adv_layout.addWidget(QLabel("Vin:"), 1, 0)
        self.vin_input = QLineEdit()
        self.vin_input.setValidator(QDoubleValidator())
        adv_layout.addWidget(self.vin_input, 1, 1)

        adv_layout.addWidget(QLabel("Vout:"), 2, 0)
        self.vout_input = QLineEdit()
        self.vout_input.setValidator(QDoubleValidator())
        adv_layout.addWidget(self.vout_input, 2, 1)

        adv_layout.addWidget(QLabel("Pot Range:"), 3, 0)
        self.pot_range_input = QLineEdit()
        self.pot_range_input.setValidator(QDoubleValidator())
        adv_layout.addWidget(self.pot_range_input, 3, 1)

        adv_layout.addWidget(QLabel("R_G Trim:"), 4, 0)
        self.rg_trim_input = QLineEdit()
        self.rg_trim_input.setValidator(QDoubleValidator())
        adv_layout.addWidget(self.rg_trim_input, 4, 1)

        adv_layout.addWidget(QLabel("R_F Trim:"), 5, 0)
        self.rf_trim_input = QLineEdit()
        self.rf_trim_input.setValidator(QDoubleValidator())
        adv_layout.addWidget(self.rf_trim_input, 5, 1)

        adv_layout.addWidget(QLabel("Wiper:"), 6, 0)
        self.wiper_input = QLineEdit()
        self.wiper_input.setValidator(QIntValidator())
        adv_layout.addWidget(self.wiper_input, 6, 1)

        # 2x2 instead of a single row: four buttons inline get truncated at
        # the panel's width.
        adv_btns = QGridLayout()
        self.set_adv_btn = QPushButton("Set Adv")
        self.save_mem_btn = QPushButton("Save Mem")
        self.load_mem_btn = QPushButton("Load Mem")
        self.calibrate_btn = QPushButton("Calibrate…")
        adv_btns.addWidget(self.set_adv_btn, 0, 0)
        adv_btns.addWidget(self.save_mem_btn, 0, 1)
        adv_btns.addWidget(self.load_mem_btn, 1, 0)
        adv_btns.addWidget(self.calibrate_btn, 1, 1)
        adv_layout.addLayout(adv_btns, 7, 0, 1, 2)

        self.set_adv_btn.clicked.connect(self._on_set_advanced_clicked)
        self.save_mem_btn.clicked.connect(self._on_save_mem_clicked)
        self.load_mem_btn.clicked.connect(self._on_load_mem_clicked)
        self.calibrate_btn.clicked.connect(self._on_calibrate_clicked)

        layout.addWidget(self.advanced_frame)
        layout.addStretch()

    # --- Target selection (driven by MainWindow.select_kicker) ---

    def set_target_devices(self, device_ids):
        """Called whenever the grid selection changes."""
        if not device_ids:
            self.target_label.setText("No device selected")
        elif len(device_ids) == 1:
            self.target_label.setText(f"Editing: NanoKicker #{device_ids[0]}")
        else:
            ids = ", ".join(str(d) for d in device_ids)
            self.target_label.setText(f"Editing {len(device_ids)} devices: {ids}")

        has_target = bool(device_ids)
        self.freq_input.setEnabled(has_target)
        self.amp_input.setEnabled(has_target)
        self.mode_combo.setEnabled(has_target)
        self.set_button.setEnabled(has_target)

        single = len(device_ids) == 1
        self.advanced_checkbox.setEnabled(single)
        if not single and self.advanced_checkbox.isChecked():
            self.advanced_checkbox.setChecked(False)

    def load_basic_from(self, mode, frequency, amplitude):
        """Populate the basic fields from a device's last known values.

        Never overwrites a field the user currently has focused, so a
        background poll/read can't clobber input mid-edit.
        """
        if frequency is not None and not self.freq_input.hasFocus():
            self.freq_input.setText(str(frequency))
        if amplitude is not None and not self.amp_input.hasFocus():
            self.amp_input.setText(f"{amplitude:.2f}")
        if mode is not None and not self.mode_combo.hasFocus():
            self.mode_combo.setCurrentIndex(DEVICE_MODE_TO_UI_INDEX.get(mode, 0))

    def load_advanced_from_dict(self, params: dict):
        """Populate the advanced fields from a full parameter read.

        Never overwrites a field the user currently has focused.
        """
        if not self.startup_check.hasFocus():
            self.startup_check.setChecked(bool(params.get("startup_enabled")))
        if not self.vin_input.hasFocus():
            self.vin_input.setText(f"{params.get('vin') or 0.0:.2f}")
        if not self.vout_input.hasFocus():
            self.vout_input.setText(f"{params.get('vout') or 0.0:.2f}")
        if not self.pot_range_input.hasFocus():
            self.pot_range_input.setText(str(params.get("pot_range") or 0.0))
        if not self.rg_trim_input.hasFocus():
            self.rg_trim_input.setText(str(params.get("r_g_trim") or 0.0))
        if not self.rf_trim_input.hasFocus():
            self.rf_trim_input.setText(str(params.get("r_f_trim") or 0.0))
        if not self.wiper_input.hasFocus():
            self.wiper_input.setText(str(params.get("wiper") or 0))

    def get_basic_values(self):
        """Parse the basic fields. Raises ValueError on bad input."""
        frequency = int(self.freq_input.text())
        amplitude = float(self.amp_input.text())
        mode = UI_INDEX_TO_DEVICE_MODE.get(self.mode_combo.currentIndex(), 0)
        return frequency, amplitude, mode

    def _single_target(self):
        ids = self.main_window.selected_device_ids
        return ids[0] if len(ids) == 1 else None

    def _send(self, device_id, method_name, value=None):
        if sip.isdeleted(self.main_window):
            return
        self.main_window.trigger_call_setter.emit(device_id, method_name, value)

    # --- Basic parameters: apply to every currently selected device ---

    def _apply_frequency(self):
        # editingFinished can still fire from Qt's own teardown logic (a
        # focused field losing focus as the window is destroyed) after
        # main_window's C++ object is already gone.
        if sip.isdeleted(self.main_window):
            return
        try:
            frequency = int(self.freq_input.text())
        except ValueError:
            logger.warning("Invalid input for frequency.")
            return
        for device_id in self.main_window.selected_device_ids:
            self._send(device_id, "set_frequency", frequency)

    def _apply_amplitude(self):
        if sip.isdeleted(self.main_window):
            return
        try:
            amplitude = float(self.amp_input.text())
        except ValueError:
            logger.warning("Invalid input for amplitude.")
            return
        for device_id in self.main_window.selected_device_ids:
            self._send(device_id, "set_amplitude", amplitude)

    def _apply_mode(self):
        if sip.isdeleted(self.main_window):
            return
        mode = UI_INDEX_TO_DEVICE_MODE.get(self.mode_combo.currentIndex(), 0)
        for device_id in self.main_window.selected_device_ids:
            self._send(device_id, "set_mode", mode)

    def _on_set_clicked(self):
        try:
            frequency, amplitude, mode = self.get_basic_values()
        except ValueError:
            logger.warning("Invalid input for frequency or amplitude.")
            return
        for device_id in self.main_window.selected_device_ids:
            self._send(device_id, "set_frequency", frequency)
            self._send(device_id, "set_amplitude", amplitude)
            self._send(device_id, "set_mode", mode)

    # --- Advanced parameters: single device only ---

    def _on_advanced_toggled(self, checked):
        selected = self.main_window.selected_device_ids
        if checked and len(selected) > 1:
            # Collapse to the first-selected device. select_kicker() re-enters
            # here indirectly via set_target_devices(), and since the checkbox
            # is already checked at that point, MainWindow's selection-update
            # path fetches the params itself -- no need to also do it below.
            self.main_window.select_kicker(selected[0], additive=False)
        elif checked and len(selected) == 1:
            self.main_window.trigger_get_parameters.emit(selected[0])

        showing = checked and self._single_target() is not None
        self.advanced_frame.setVisible(showing)
        if showing != self._advanced_shown:
            self.main_window.grow_or_shrink_for(self.advanced_frame, showing)
            self._advanced_shown = showing

    def _on_set_advanced_clicked(self):
        device_id = self._single_target()
        if device_id is None:
            return
        try:
            if self.vin_input.text():
                self._send(device_id, "set_vin", float(self.vin_input.text()))
            if self.vout_input.text():
                self._send(device_id, "set_vout", float(self.vout_input.text()))
            if self.pot_range_input.text():
                self._send(device_id, "set_pot_range", float(self.pot_range_input.text()))
            if self.rg_trim_input.text():
                self._send(device_id, "set_r_g_trim", float(self.rg_trim_input.text()))
            if self.rf_trim_input.text():
                self._send(device_id, "set_r_f_trim", float(self.rf_trim_input.text()))
            if self.wiper_input.text():
                self._send(device_id, "set_wiper", int(self.wiper_input.text()))
        except ValueError:
            logger.warning("Invalid input for advanced parameters.")

    def _on_save_mem_clicked(self):
        device_id = self._single_target()
        if device_id is not None:
            self._send(device_id, "save_settings")

    def _on_load_mem_clicked(self):
        device_id = self._single_target()
        if device_id is not None:
            self.main_window.trigger_load_settings.emit(device_id)

    def _on_calibrate_clicked(self):
        device_id = self._single_target()
        if device_id is None:
            return
        dialog = CalibrationDialog(self, device_id, self)
        dialog.exec_()
