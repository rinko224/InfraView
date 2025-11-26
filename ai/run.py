# run.py
import sys
from PySide2.QtWidgets import QApplication
from component.main_ui import MainUI

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainUI()
    window.show()
    sys.exit(app.exec_())