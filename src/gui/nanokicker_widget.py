from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFrame,
    QGridLayout,
    QComboBox,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIntValidator, QDoubleValidator


class NanoKickerWidget(QFrame):
    """
    A collapsible widget to control a single NanoKicker device.
    """

    def __init__(self, nanokicker_device, parent=None):
        super().__init__(parent)
        self.nanokicker = nanokicker_device
        self.is_expanded = True

        self._init_ui()
        self.setFrameShape(QFrame.StyledPanel)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Title Bar ---
        self.title_bar = QWidget()
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(5, 5, 5, 5)

        self.toggle_button = QPushButton("▼")
        self.toggle_button.setFixedSize(20, 20)
        self.toggle_button.setStyleSheet("QPushButton { border: none; }")

        self.title_label = QLabel(f"NanoKicker #{self.nanokicker.device_id}")
        self.title_label.setStyleSheet("font-weight: bold;")

        title_layout.addWidget(self.toggle_button)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # --- Content Area ---
        self.content_area = QWidget()
        content_layout = QGridLayout(self.content_area)

        # Frequency
        content_layout.addWidget(QLabel("Frequency (Hz):"), 0, 0)
        self.freq_input = QLineEdit()
        self.freq_input.setValidator(QIntValidator(0, 200000))  # Freq range
        content_layout.addWidget(self.freq_input, 0, 1)

        # Amplitude
        content_layout.addWidget(QLabel("Amplitude:"), 1, 0)
        self.amp_input = QLineEdit()
        self.amp_input.setValidator(
            QDoubleValidator(0.0, 24.0, 2)
        )  # Amplitude range
        content_layout.addWidget(self.amp_input, 1, 1)

        # Mode
        content_layout.addWidget(QLabel("Mode:"), 2, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            ["Off", "Sine", "Square", "Triangle"]
        )  # Assuming mode values 0, 1, 2, 3
        content_layout.addWidget(self.mode_combo, 2, 1)

        # Buttons
        button_layout = QHBoxLayout()
        self.set_button = QPushButton("Set Parameters")
        self.get_button = QPushButton("Get Parameters")
        button_layout.addWidget(self.get_button)
        button_layout.addWidget(self.set_button)
        content_layout.addLayout(button_layout, 3, 0, 1, 2)

        # --- Advanced Section ---
        self.advanced_checkbox = QCheckBox("Advanced Settings")
        content_layout.addWidget(self.advanced_checkbox, 4, 0, 1, 2)

        self.advanced_frame = QFrame()
        self.advanced_frame.setVisible(False)
        adv_layout = QGridLayout(self.advanced_frame)
        adv_layout.setContentsMargins(0, 5, 0, 0)

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

        adv_btns = QHBoxLayout()
        self.set_adv_btn = QPushButton("Set Adv")
        self.save_mem_btn = QPushButton("Save Mem")
        self.load_mem_btn = QPushButton("Load Mem")
        adv_btns.addWidget(self.set_adv_btn)
        adv_btns.addWidget(self.save_mem_btn)
        adv_btns.addWidget(self.load_mem_btn)
        adv_layout.addLayout(adv_btns, 7, 0, 1, 2)

        content_layout.addWidget(self.advanced_frame, 7, 0, 1, 2)

        layout.addWidget(self.title_bar)
        layout.addWidget(self.content_area)

        # --- Connections ---
        self.toggle_button.clicked.connect(self.toggle_view)
        self.set_button.clicked.connect(self.set_parameters)
        self.get_button.clicked.connect(self.get_parameters)

        self.advanced_checkbox.toggled.connect(self.toggle_advanced)
        self.set_adv_btn.clicked.connect(self.set_advanced_parameters)
        self.save_mem_btn.clicked.connect(self.save_to_memory)
        self.load_mem_btn.clicked.connect(self.load_from_memory)

        # --- Animation Setup for Collapsing ---
        self.animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutQuart)

        self.get_parameters()

    # --- UI Slots and Actions ---

    def toggle_view(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.toggle_button.setText("▼")
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.content_area.sizeHint().height())
        else:
            self.toggle_button.setText("▶")
            self.animation.setStartValue(self.content_area.sizeHint().height())
            self.animation.setEndValue(0)
        self.animation.start()

    def toggle_advanced(self, checked):
        self.advanced_frame.setVisible(checked)
        if self.is_expanded:
            # Allow the area to expand to fit the new content
            self.content_area.setMaximumHeight(16777215)

    def set_parameters(self):
        """Read values from UI and send them to the device."""
        try:
            freq = int(self.freq_input.text())
            amp = float(self.amp_input.text())

            # Map UI index to AD9833 mode: 0->0, 1->1, 2->2, 3->4 (Triangle)
            mode_map = {0: 0, 1: 1, 2: 2, 3: 4}
            mode = mode_map.get(self.mode_combo.currentIndex(), 0)

            self.nanokicker.set_frequency(freq)
            self.nanokicker.set_amplitude(amp)
            self.nanokicker.set_mode(mode)

        except ValueError:
            print("Error: Invalid input for frequency or amplitude.")

    def set_advanced_parameters(self):
        try:
            # self.nanokicker.set_startup_enabled(self.startup_check.isChecked())
            if self.vin_input.text():
                self.nanokicker.set_vin(float(self.vin_input.text()))
            if self.vout_input.text():
                self.nanokicker.set_vout(float(self.vout_input.text()))
            if self.pot_range_input.text():
                self.nanokicker.set_pot_range(
                    float(self.pot_range_input.text())
                )
            if self.rg_trim_input.text():
                self.nanokicker.set_r_g_trim(float(self.rg_trim_input.text()))
            if self.rf_trim_input.text():
                self.nanokicker.set_r_f_trim(float(self.rf_trim_input.text()))
            if self.wiper_input.text():
                self.nanokicker.set_wiper(int(self.wiper_input.text()))
        except ValueError:
            print("Error: Invalid input for advanced parameters.")

    def save_to_memory(self):
        self.nanokicker.save_settings()

    def load_from_memory(self):
        self.nanokicker.load_settings()
        self.get_parameters()

    def get_parameters(self):
        """Read parameters from device and update the UI."""
        self.nanokicker.read_all_parameters()

        self.freq_input.setText(str(self.nanokicker.frequency or 0))
        self.amp_input.setText(f"{self.nanokicker.amplitude or 0:.2f}")

        # Map AD9833 mode to UI index: 0->0, 1->1, 2->2, 3->2 (Square2), 4->3 (Triangle)
        mode_map = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3}
        if self.nanokicker.mode is not None:
            self.mode_combo.setCurrentIndex(
                mode_map.get(self.nanokicker.mode, 0)
            )

        # Advanced
        self.startup_check.setChecked(bool(self.nanokicker.startup_enabled))
        self.vin_input.setText(f"{self.nanokicker.vin or 0.0:.2f}")
        self.vout_input.setText(f"{self.nanokicker.vout or 0.0:.2f}")
        self.pot_range_input.setText(str(self.nanokicker.pot_range or 0.0))
        self.rg_trim_input.setText(str(self.nanokicker.r_g_trim or 0.0))
        self.rf_trim_input.setText(str(self.nanokicker.r_f_trim or 0.0))
        self.wiper_input.setText(str(self.nanokicker.wiper or 0))
