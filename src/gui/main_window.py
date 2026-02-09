import sys
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QScrollArea,
    QFrame,
)
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, Qt

from motherboard import Motherboard
from gui.nanokicker_widget import NanoKickerWidget


class Worker(QObject):
    """
    A worker object that performs long-running tasks in a separate thread.
    """

    ports_found = pyqtSignal(list)
    connection_status = pyqtSignal(bool, str)
    scan_results = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.motherboard = None

    def _handle_disconnect(self):
        """Callback for when motherboard detects disconnection."""
        self.connection_status.emit(False, "Connection Lost")
        self.motherboard = None

    @pyqtSlot()
    def find_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.ports_found.emit(ports)

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
    def scan_for_kickers(self):
        if self.motherboard:
            found_kickers = self.motherboard.scan_for_nanokickers()
            self.scan_results.emit(found_kickers)
        self.finished.emit()

    @pyqtSlot()
    def disconnect_motherboard(self):
        if self.motherboard:
            self.motherboard.disconnect()
        self.connection_status.emit(False, "Disconnected")


class MainWindow(QMainWindow):
    """
    The main application window for controlling the NanoKicker motherboard.
    """

    # Signals to trigger tasks in the worker thread
    trigger_find_ports = pyqtSignal()
    trigger_connect = pyqtSignal(str)
    trigger_scan = pyqtSignal()
    trigger_disconnect = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NanoKicker Control Center")
        self.setMinimumSize(400, 500)

        self._init_ui()
        self._init_worker_thread()

    def _init_ui(self):
        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Control Panel ---
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_panel_layout = QVBoxLayout(control_panel)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Motherboard Port:"))
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)

        # Connection buttons
        connection_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)

        # Status label
        self.status_label = QLabel("Status: Not Connected")

        # Scan button
        self.scan_button = QPushButton("Scan for NanoKickers")
        self.scan_button.setEnabled(False)

        control_panel_layout.addLayout(port_layout)
        control_panel_layout.addLayout(connection_layout)
        control_panel_layout.addWidget(self.scan_button)
        control_panel_layout.addWidget(self.status_label)

        main_layout.addWidget(control_panel)

        # --- NanoKicker Display Area ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.kicker_container = QWidget()
        self.kicker_layout = QVBoxLayout(self.kicker_container)
        self.kicker_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.kicker_container)

        main_layout.addWidget(scroll_area)

        # --- Connections ---
        self.refresh_button.clicked.connect(self.find_ports)
        self.connect_button.clicked.connect(self.connect_to_motherboard)
        self.disconnect_button.clicked.connect(self.disconnect_from_motherboard)
        self.scan_button.clicked.connect(self.scan_for_kickers)

    def _init_worker_thread(self):
        self.worker_thread = QThread()
        self.worker = Worker()

        self.worker.moveToThread(self.worker_thread)

        # Connect worker signals to main thread slots
        self.worker.ports_found.connect(self.update_port_list)
        self.worker.connection_status.connect(self.on_connection_status_changed)
        self.worker.scan_results.connect(self.display_kicker_widgets)

        # Connect main thread signals to worker slots
        self.trigger_find_ports.connect(self.worker.find_ports)
        self.trigger_connect.connect(self.worker.connect_motherboard)
        self.trigger_scan.connect(self.worker.scan_for_kickers)
        self.trigger_disconnect.connect(self.worker.disconnect_motherboard)

        self.worker_thread.start()
        self.find_ports()  # Initial port scan

    # --- UI Slots and Actions ---
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
        self.clear_kicker_widgets()
        self.trigger_disconnect.emit()

    def scan_for_kickers(self):
        self.scan_button.setEnabled(False)
        self.status_label.setText("Status: Scanning for devices...")
        self.clear_kicker_widgets()
        self.trigger_scan.emit()

    def update_port_list(self, ports):
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        self.refresh_button.setEnabled(True)

    def on_connection_status_changed(self, is_connected, message):
        self.status_label.setText(f"Status: {message}")
        self.connect_button.setEnabled(not is_connected)
        self.disconnect_button.setEnabled(is_connected)
        self.scan_button.setEnabled(is_connected)
        self.port_combo.setEnabled(not is_connected)
        self.refresh_button.setEnabled(not is_connected)

        if not is_connected:
            self.clear_kicker_widgets()

    def display_kicker_widgets(self, found_kickers):
        if not found_kickers:
            self.status_label.setText(
                "Status: Connected. No NanoKickers found."
            )
        else:
            self.status_label.setText(
                f"Status: Connected. Found {len(found_kickers)} device(s)."
            )

        for device_id, kicker_obj in found_kickers.items():
            kicker_widget = NanoKickerWidget(kicker_obj)
            self.kicker_layout.addWidget(kicker_widget)

        self.scan_button.setEnabled(True)

    def clear_kicker_widgets(self):
        while self.kicker_layout.count():
            child = self.kicker_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def closeEvent(self, event):
        """Ensure worker thread is cleaned up on exit."""
        self.disconnect_from_motherboard()
        self.worker_thread.quit()
        self.worker_thread.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
