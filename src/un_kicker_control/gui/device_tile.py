import logging

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QGraphicsOpacityEffect

from .modes import MODE_NAMES

logger = logging.getLogger(__name__)

INACTIVE_OPACITY = 0.4
FADE_DURATION_MS = 250


class DeviceTile(QFrame):
    """
    Read-only summary tile for one NanoKicker grid slot (mode, frequency,
    amplitude). All commands go through the shared ControlPanel -- this
    widget only displays state and reports clicks as selection.

    A tile that hasn't responded to the last poll fades to a dimmed opacity
    and is disabled once the fade finishes, which also stops it from
    receiving the mouse clicks that would select it.
    """

    def __init__(self, device_id, main_window, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.main_window = main_window
        self.is_selected = False
        self.is_responsive = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(
            "Click to select. Ctrl/Cmd-click to add to the current selection."
        )

        layout = QVBoxLayout(self)
        self.title_label = QLabel(f"NanoKicker #{device_id}")
        self.title_label.setStyleSheet("font-weight: bold;")
        self.mode_label = QLabel("—")
        self.freq_label = QLabel("—")
        self.amp_label = QLabel("—")
        self.status_label = QLabel("Not found")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")

        for w in (
            self.title_label,
            self.mode_label,
            self.freq_label,
            self.amp_label,
            self.status_label,
        ):
            layout.addWidget(w)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(INACTIVE_OPACITY)
        self.setGraphicsEffect(self._opacity_effect)

        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._opacity_anim.setDuration(FADE_DURATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._opacity_anim.finished.connect(self._on_fade_finished)

        self.setEnabled(False)

    def _on_fade_finished(self):
        # Only disable interaction once fully dimmed, so the tile stays
        # clickable for the whole fade-in but doesn't accept clicks partway
        # through fading out.
        if not self.is_responsive:
            self.setEnabled(False)

    def set_data(self, mode, frequency, amplitude, responsive):
        self.is_responsive = responsive
        if responsive:
            self.setEnabled(True)
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity_effect.opacity())
        self._opacity_anim.setEndValue(1.0 if responsive else INACTIVE_OPACITY)
        self._opacity_anim.start()
        if mode is not None:
            self.mode_label.setText(f"Mode: {MODE_NAMES.get(mode, mode)}")
        if frequency is not None:
            self.freq_label.setText(f"{frequency} Hz")
        if amplitude is not None:
            self.amp_label.setText(f"{amplitude:.2f} Vpp")
        self.status_label.setVisible(not responsive)
        self._apply_style()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._apply_style()

    def _apply_style(self):
        if self.is_selected and self.is_responsive:
            self.setStyleSheet("DeviceTile { border: 2px solid #2a82da; }")
        else:
            self.setStyleSheet("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            additive = bool(event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier))
            self.main_window.select_kicker(self.device_id, additive=additive)
        super().mousePressEvent(event)
