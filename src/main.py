import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    """
    Initializes and runs the NanoKicker Control Center GUI.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
