from __future__ import print_function

from hgoldfish.utils import eventlet
from PyQt4.QtCore import QCoreApplication

class DependsOnCurrentPosition:
    def __init__(self):
        self.gate = eventlet.Event()
        self.currentPosition = 0

    def wait(self, i):
        while i > self.currentPosition + 5:
            try:
                self.gate.wait()
            finally:
                self.gate.reset()

    def setCurrentPosition(self, pos):
        self.currentPosition = pos
        self.gate.send(None)


if __name__ == "__main__":
    import logging; logging.basicConfig(level = logging.DEBUG)
    gate = DependsOnCurrentPosition()
    def t1():
        gate.wait(10)
        print("t1: exit")

    def t2():
        for i in range(10):
            gate.setCurrentPosition(i)
            print("t2:", i)
            eventlet.sleep(1)
        eventlet.stop_application()

    def t3():
        g1, g2 = eventlet.spawn(t1), eventlet.spawn(t2)
        g1.wait(), g2.wait()

    app = QCoreApplication([])
    g3 = eventlet.spawn(t3)
    eventlet.start_application()