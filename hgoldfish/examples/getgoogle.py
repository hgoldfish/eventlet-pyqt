import logging; logging.basicConfig(level = logging.DEBUG)
from hgoldfish.utils import eventlet
from eventlet.green import urllib
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QTextBrowser

class TestWidget(QTextBrowser):
    def __init__(self):
        QTextBrowser.__init__(self)
        self.operations = eventlet.GreenletGroup()

    def mousePressEvent(self, event):
        if event.button() == Qt.MidButton:
            self.operations.spawn(self.getpage)
        QTextBrowser.mousePressEvent(self, event)

    def getpage(self):
        page = urllib.urlopen("http://code.google.com/p/eventlet-pyqt/").read().decode("utf-8")
        self.setHtml(page)

app = QApplication([])
w = TestWidget()
w.show()
eventlet.start_application(quitOnLastWindowClosed = True)