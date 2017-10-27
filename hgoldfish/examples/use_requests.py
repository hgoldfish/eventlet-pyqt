import logging; logging.basicConfig(level = logging.DEBUG)
from hgoldfish.utils import eventlet
requests = eventlet.import_patched("requests")

try:
    from PyQt4.QtCore import Qt
    from PyQt4.QtGui import QApplication, QTextBrowser
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QApplication, QTextBrowser


class TestWidget(QTextBrowser):
    def __init__(self):
        QTextBrowser.__init__(self)
        self.operations = eventlet.GreenletGroup()
        self.setPlainText("click middle button to navigate www.163.com")

    def mousePressEvent(self, event):
        if event.button() == Qt.MidButton:
            self.operations.spawn(self.getpage)
            self.operations.spawnWithName("print_number", self.printNumbers)
        QTextBrowser.mousePressEvent(self, event)

    def printNumbers(self):
        i = 0
        while True:
            eventlet.sleep(0.1)
            i += 1
            self.append(str(i))

    def getpage(self):
        page = requests.get("http://www.163.com").text
        self.setPlainText(page)
        self.operations.kill("print_number")

if __name__ == "__main__":
    app = QApplication([])
    w = TestWidget()
    w.show()
    eventlet.start_application(quitOnLastWindowClosed = True)
