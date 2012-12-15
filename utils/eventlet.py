# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division
try:
    str = unicode
except NameError:
    pass

"""
integrate eventlet with qt.
how to use:
    from utils.eventlet import start_application
    app = QApplication()
    start_application()

As we can not block the main loop, so I design a type named GreenletGroup.
    def __init__(self):
        self.operations = eventlet.GreenletGroup()

    def onButtonClicked(self):
        @self.operations.run()
        def _(self):
            conn = eventlet.connect(("www.example.com", 80))
            conn.send("GET / HTTP 1.0\r\n\r\n")
            QMessageBox.information(self, "test", conn.recv(1024))

"""
import sys, logging, functools, inspect, weakref, gc, heapq, threading
from PyQt4.QtCore import Qt, QSocketNotifier, QTimer, \
        QCoreApplication, QObject, pyqtSlot, QMetaObject, Q_ARG
from eventlet import spawn, sleep, spawn_after, kill, Timeout, with_timeout, GreenPool, \
        GreenPile, Queue, import_patched, connect, listen, getcurrent
from eventlet.hubs import use_hub, get_hub
from eventlet.hubs.hub import BaseHub
from eventlet.support import greenlets as greenlet, clear_sys_exc_info
from eventlet.event import Event
from eventlet.green import socket

logger = logging.getLogger(__name__)

__all__ = ["GreenletGroup", "runInNewThread", "waitForDeferred",
        "start_application", "stop_application", "SystemExceptions",
        "scheduleCall"]
__all__ += ["sleep", "spawn", "spawn_after", "kill", "Timeout", "with_timeout", \
        "GreenPool", "GreenPile", "Queue", "import_patched", \
        "connect", "listen", "getcurrent", "GreenletExit", "Event", "socket"] #from eventlet

GreenletExit = greenlet.GreenletExit

SystemExceptions = (GreenletExit, SystemExit, weakref.ReferenceError)


def scheduleCall(func, *args, **kwargs):
    def wrapper():
        try:
            func(*args, **kwargs)
        except:
            logger.exception("scheduleCall检测到莫名错误。")
    QTimer.singleShot(0, wrapper)

class QtListener:
    def __init__(self, evtype, fileno, cb):
        self.evtype, self.fileno, self.cb = evtype, fileno, cb
        self.notifier = QSocketNotifier(fileno, self.eventType(evtype))
        self.notifier.activated.connect(cb)

    def __del__(self):
        self.notifier.setEnabled(False)
        self.notifier = None

    def eventType(self, evtype):
        assert evtype in (BaseHub.READ, BaseHub.WRITE)
        if evtype == BaseHub.READ:
            return QSocketNotifier.Read
        elif evtype == BaseHub.WRITE:
            return QSocketNotifier.Write

class QtHub(BaseHub):
    READ = BaseHub.READ
    WRITE = BaseHub.WRITE

    def __init__(self):
        BaseHub.__init__(self)
        self.lclass = QtListener
        self.greenlets = []

    def run(self, *args, **kwargs):
        self.stopping = False
        self.running = True
        try:
            getattr(QCoreApplication, "exec_")()
        except AttributeError:
            getattr(QCoreApplication, "exec")()
        QCoreApplication.processEvents()
        self.stopping = True
        self.running = False

    def abort(self, wait = False):
        self.stopping = True
        gc.collect()
        aliveGreenlets = self._countManagedGreenlets()
        if aliveGreenlets <= 0:
            QCoreApplication.instance().quit()
        else:
            logger.warning("Wait for %s greenlets to terminate.", aliveGreenlets)
            QTimer.singleShot(1000, self._foreToQuitApplication)
        if wait:
            assert self.greenlet is not greenlet.getcurrent(), \
                    "Can't abort with wait from inside the hub's greenlet."
            self.switch()

    def add_timer(self, timer):
        def done():
            self.timer_canceled(timer)
            try:
                timer()
            except:
                clear_sys_exc_info()
        timer._impl = QTimer()
        timer._impl.setSingleShot(True)
        timer._impl.timeout.connect(done)
        timer._impl.setInterval(timer.seconds * 1000)
        timer._impl.start()
        scheduled_time = self.clock() + timer.seconds
        heapq.heappush(self.timers, (scheduled_time, timer))
        return scheduled_time

    def timer_canceled(self, timer):
        try:
            timer._impl.stop()
            del timer._impl
        except AttributeError:
            pass
        try:
            removeListItem(self.timers, lambda item: item[1] is timer)
            heapq.heapify(self.timers)
        except ValueError:
            pass

    def _foreToQuitApplication(self):
        gc.collect()
        if self._countManagedGreenlets() > 0:
            logger.warning("尚有%s个greenlet未退出。强制退出Qt事件循环", len(self.greenlets))
        QCoreApplication.instance().quit()

    def _addManagedGreenlets(self, greenlet):
        assert greenlet is not None
        greenlet.link(self._tryToQuit2)
        ref = weakref.ref(greenlet, self._tryToQuit)
        self.greenlets.append(ref)

    def _countManagedGreenlets(self):
        return len([ref for ref in self.greenlets if ref()])

    def _tryToQuit(self, ref_):
        self.greenlets = [ref for ref in self.greenlets if ref is not ref_]
        if self.stopping and len(self.greenlets) == 0:
            QCoreApplication.instance().quit()

    def _tryToQuit2(self, greenlet):
        self.greenlets = [ref for ref in self.greenlets if ref() is not greenlet]
        if self.stopping and len(self.greenlets) == 0:
            QCoreApplication.instance().quit()

Hub = QtHub
use_hub(sys.modules[__name__])

def start_application(quitOnLastWindowClosed = True):
    if quitOnLastWindowClosed:
        app = QCoreApplication.instance()
        if hasattr(app, "lastWindowClosed"):
            app.lastWindowClosed.connect(stop_application, Qt.UniqueConnection)
            app.setQuitOnLastWindowClosed(False)
    get_hub().switch()
    listenerCount = len(get_hub().listeners[BaseHub.READ]) + len(get_hub().listeners[BaseHub.WRITE])
    if listenerCount > 0:
        logger.warning("You have %d open socket left.", listenerCount)
    if len(get_hub().timers) > 0:
        logger.warning("You have left %d timers.", len(get_hub().timers))

def stop_application():
    get_hub().abort()


def _killall_helper(greenlets):
    for ref, name in greenlets:
        greenlet = ref()
        if greenlet is None:
            continue
        try:
            greenlet.kill()
            if greenlet:
                #调用GreenThread.kill()会立即切换到这个GreenThread。
                #但是并不保证结束后才切回来。但是保证结束后一定会切回来。
                #所以这里会有一个.wait()
                try:
                    greenlet.wait()
                except:
                    logger.exception("There are some error occured in greenlet.")
                    clear_sys_exc_info()
        except:
            clear_sys_exc_info()
    del greenlets[:] #防止在__del__()里面再次启动greenlet
    gc.collect()

class GreenletGroup:
    #TODO 让GreenletGroup在非Qt环境下也可以使用。
    def __init__(self):
        self.greenlets = []

    def __del__(self):
        self.killall()

    def add(self, greenlet, name = None):
        ref = weakref.ref(greenlet)
        self.greenlets.append((ref, name))
        try:
            get_hub()._addManagedGreenlets(greenlet)
        except AttributeError:
            pass

    def get(self, name):
        for ref, name_ in self.greenlets:
            if name == name_:
                return ref()
        return None

    def kill(self, name):
        g = self.get(name)
        if g is not None:
            try:
                g.kill()
                g.wait()
            except:
                pass

    def killall(self):
        if len(self.greenlets) == 0:
            return
        t = spawn(_killall_helper, self.greenlets)
        try:
            get_hub()._addManagedGreenlets(t)
        except:
            pass

    def spawnWithName(self, name, func, *args, **kwargs):
        func_self = getattr(func, "__self__", None)
        if func_self is not None:
            q = QuitGreenletWhenNotExists()
            func_self = weakref.proxy(func_self, q)
            func = func.__func__
            def wrapper_bound():
                try:
                    func(func_self, *args, **kwargs)
                except (GreenletExit, weakref.ReferenceError):
                    clear_sys_exc_info()
                except:
                    logger.exception("greenlet抛出异常。")
                    clear_sys_exc_info()
            t = spawn(wrapper_bound)
            q.setGreenlet(t)
        else:
            def wrapper_notbound():
                try:
                    func(*args, **kwargs)
                except GreenletExit:
                    clear_sys_exc_info()
                except:
                    logger.exception("greenlet抛出异常。")
                    clear_sys_exc_info()
            t = spawn(wrapper_notbound)
        self.add(t, name)
        return t

    def spawn(self, func, *args, **kwargs):
        return self.spawnWithName(None, func, *args, **kwargs)

    def run(self, *allow_closure):
        def run_impl(func):
            func = getattr(func, "__func__", func)
            if getattr(func, "__closure__", None):
                for cell in func.__closure__:
                    for v in allow_closure:
                        if cell.cell_contents is v:
                            break
                    else:
                        assert False, "闭包引用了未明确指定的变量"
            args = inspect.getargspec(func).args
            l = sys._getframe(1).f_locals
            v = {}
            q = QuitGreenletWhenNotExists()
            for arg in args:
                v[arg] = weakref.proxy(l[arg], q)
            def wrapper():
                try:
                    func(**v)
                except (GreenletExit, weakref.ReferenceError):
                    clear_sys_exc_info()
                except:
                    logger.exception("greenlet抛出异常。")
                    clear_sys_exc_info()
            t = spawn(wrapper)
            self.add(t, None)
            q.setGreenlet(t)
        return run_impl

class QuitGreenletWhenNotExists:
    def setGreenlet(self, greenlet):
        self.greenlet = weakref.ref(greenlet)

    def __call__(self, ref):
        g = self.greenlet()
        if g is None:
            return
        try:
            g.kill()
        except:
            pass

def spawnInGreenlet(greenletGroupAttrName = "operations"):
    def decoration(wrapped):
        def wrapper(self, *args, **kwargs):
            operations = getattr(self, greenletGroupAttrName)
            operations.spawn(wrapped, self, *args, **kwargs)
        functools.update_wrapper(wrapper, wrapped)
        return wrapper
    return decoration

class _DeferCallMainThreadStub(QObject):
    @pyqtSlot("PyQt_PyObject", "PyQt_PyObject")
    def _slot_callback(self, done, result):
        done.send(result)

    @pyqtSlot("PyQt_PyObject", "PyQt_PyObject")
    def _slot_errback(self, done, exception):
        done.send_exception(exception)

class DeferCallThread(threading.Thread):
    mainThreadStub = _DeferCallMainThreadStub()

    def __init__(self, done, func, args, kwargs):
        threading.Thread.__init__(self)
        self.daemon = True
        self.func = func
        self.done = done
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*(self.args), **(self.kwargs))
        except Exception as e:
            logger.exception("deferToThread caught exception: %r", e)
            QMetaObject.invokeMethod(DeferCallThread.mainThreadStub, "_slot_errback", Qt.QueuedConnection,
                    Q_ARG("PyQt_PyObject", self.done), Q_ARG("PyQt_PyObject", e))
        else:
            QMetaObject.invokeMethod(DeferCallThread.mainThreadStub, "_slot_callback", Qt.QueuedConnection,
                    Q_ARG("PyQt_PyObject", self.done), Q_ARG("PyQt_PyObject", result))
        finally:
            del self.func, self.done, self.args, self.kwargs


def runInNewThread(func, *args, **kwargs):
    done = Event()
    t = DeferCallThread(done, func, args, kwargs)
    t.start()
    return done.wait()

def waitForDeferred(df):
    done = Event()
    def send_exception(result):
        if isinstance(result, Exception):
            done.send_exception(result)
        else:
            done.send_exception(Exception(result))
    df.addCallbacks(done.send, send_exception)
    return done.wait()

def removeListItem(l, e, repeat = False):
    if hasattr(e, "__call__"):
        judge = e
    else:
        judge = lambda f: f is e
    if not repeat:
        for i, f in enumerate(l):
            if judge(f):
                l.pop(i)
                return 1
        else:
            return 0
    else:
        i = len(l) - 1
        count = 0
        for f in reversed(l):
            if judge(f):
                l.pop(i)
                count += 1
        return count
