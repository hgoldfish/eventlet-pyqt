Integrate eventlet with Qt's eventloop.
It is very simple to use:

    from hgoldfish.utils import eventlet
    app = QApplication()
    eventlet.start_application()

After starting the Qt's eventloop, we can make connections as in `select`-based eventlet applications.

    try:
        from eventlet.green.urllib import urlopen
    except ImportError:  # for py3k
        from eventlet.green.urllib.request import urlopen

    def fetchUrl(url):
        page = urlopen(url).read()
        print(page)

A complete simple example, click *Middle Button* to download :

    import logging; logging.basicConfig(level = logging.DEBUG)
    from hgoldfish.utils import eventlet
    try:
        from eventlet.green.urllib import urlopen
    except ImportError:  # py3k
        from eventlet.green.urllib.request import urlopen

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
            page = urlopen("http://www.163.com/").read().decode("gbk", "replace")
            self.setPlainText(page)
            self.operations.kill("print_number")

    if __name__ == "__main__":
        app = QApplication([])
        w = TestWidget()
        w.show()
        eventlet.start_application(quitOnLastWindowClosed = True)

Unfortunely, as the greenlet module is broken, we must be very careful to spawn greenlets.

  * *DO NOT* throw any exceptions from greenlet. Or that Python will crash.
  * Greenlets *SHOULD NOT* keep references to its owner. As this situation causes cycled references.If you want to do so, use weakref, or give a try to `GreenletGroup`, which pass the weak reference of parameters to target function.
  * *DO NOT* start a local Qt eventloop. If you want to do so, use `runLocalLoop()`. Pay attention to `QMessageBox` and `QDialog`.
  * Clear exceptions before yield to another greenlet. The Python provide `sys.exc_clar()` to do so.

This module provide this functions:

  * `runInNewThread(func, *args, **kwargs)`
    Start a new thread to run `func` with arguments provided. Block current greenlet, wait for the new thread to finished, and return the value `func` returned.

  * `start_application(quitOnLastWindowClosed = True)`
    Start the Qt Application.

  * `stop_application()`
    Stop the Qt Application. Wait 1 second for greenlets to stop.

  * `exc_clear()`
    For Python 2.x version, it is `sys.exc_clear()`. For Python 3.x, it does nothing.

  * `runLocalLoop(eventloop)` & `runDialog(dialog)`
    Alias for `callMethodInEventLoop(eventloop.exec)`

  * `callMethodInEventLoop(func, *args, **kwargs)`
    Dialogs and local eventloops must run in the greenlet where Qt's main eventloop live in.

The GreenletGroup manages greenlets. It has several methods you may like.

  * `spawnWithName(name, func, *args, **kwargs)`
    Spawn a new greenlet named `name` to run the given func with past arguments. All the arguments are past as weakref.proxy.

  * `spawn(func, *args, **kwargs)`
    Alias for `spawnWithName(None, func, *args, **kwargs)`

  * `get(name)`
    Get the greenlet which named `name`.

  * `kill(name)`
    Kill the greenlet which named `name`

  * `killall()`
    Kill all managed greenlets.
