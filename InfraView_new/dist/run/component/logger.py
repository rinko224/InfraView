import logging
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QPlainTextEdit

class GuiLogger:
    def __init__(self, text_widget: QPlainTextEdit):
        self.text_widget = text_widget

    def log(self, message: str):
        self.text_widget.appendPlainText(message)
        self.text_widget.verticalScrollBar().setValue(
            self.text_widget.verticalScrollBar().maximum()
        )

class QtLogEmitter(QObject):
    log_signal = Signal(str)

class QtHandle(logging.Handler):
    def __init__(self):
        super().__init__()
        self.emitter = QtLogEmitter()

    def emit(self, record):
        msg = self.format(record)
        self.emitter.log_signal.emit(msg)    

