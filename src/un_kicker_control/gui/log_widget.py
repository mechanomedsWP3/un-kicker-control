import logging

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LEVELS = {
    "Debug": logging.DEBUG,
    "Info": logging.INFO,
    "Warning": logging.WARNING,
    "Error": logging.ERROR,
}


class QtLogHandler(QObject, logging.Handler):
    """A logging handler that forwards formatted records to a Qt signal.

    Emitting the signal from a worker thread and connecting it to a slot on a
    widget living in the GUI thread is safe: Qt queues the call onto the
    receiver's thread automatically.
    """

    new_record = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.new_record.emit(msg)


class LogPanel(QWidget):
    """A panel that displays live application log output, with level filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.handler = QtLogHandler()
        self.handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
            )
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(list(LEVELS.keys()))
        self.level_combo.setCurrentText("Debug")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self.level_combo)
        toolbar.addStretch()
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(2000)  # cap memory use for long sessions
        self.text_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self.text_edit)

        self.handler.new_record.connect(self._append_line)
        self._on_level_changed(self.level_combo.currentText())

    def attach(self, logger_name: str = "un_kicker_control"):
        """Attach this panel's handler to the given logger and ensure it emits at DEBUG."""
        target = logging.getLogger(logger_name)
        target.setLevel(logging.DEBUG)
        target.addHandler(self.handler)

    def detach(self, logger_name: str = "un_kicker_control"):
        logging.getLogger(logger_name).removeHandler(self.handler)

    def _on_level_changed(self, level_name: str):
        self.handler.setLevel(LEVELS[level_name])

    def _append_line(self, line: str):
        self.text_edit.appendPlainText(line)

    def clear(self):
        self.text_edit.clear()
