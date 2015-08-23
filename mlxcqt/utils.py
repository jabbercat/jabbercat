import asyncio
import contextlib
import functools

from . import Qt


def asyncified_done(task):
    task.result()


def asyncified_unblock(dlg, cursor, task):
    dlg.setCursor(cursor)
    dlg.setEnabled(True)


def asyncify(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        task = asyncio.async(fn(*args, **kwargs))
        task.add_done_callback(asyncified_done)
    return wrapper


def asyncify_blocking(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        prev_cursor = self.cursor()
        self.setEnabled(False)
        self.setCursor(Qt.Qt.WaitCursor)
        try:
            task = asyncio.async(fn(self, *args, **kwargs))
        except:
            self.setEnabled(True)
            self.setCursor(prev_cursor)
            raise
        task.add_done_callback(asyncified_done)
        task.add_done_callback(functools.partial(
            asyncified_unblock,
            self, prev_cursor))

    return wrapper


@contextlib.contextmanager
def block_widget(widget):
    prev_cursor = widget.cursor()
    widget.setEnabled(False)
    widget.setCursor(Qt.Qt.WaitCursor)
    try:
        yield
    finally:
        widget.setCursor(prev_cursor)
        widget.setEnabled(True)

@asyncio.coroutine
def block_widget_for_coro(widget, coro):
    with block_widget(widget):
        yield from coro

@asyncio.coroutine
def exec_async(dlg, set_modal=Qt.Qt.WindowModal):
    future = asyncio.Future()
    def done(result):
        nonlocal future
        future.set_result(result)
    dlg.finished.connect(done)
    if set_modal is not None:
        dlg.windowModality = set_modal
    dlg.show()
    try:
        return (yield from future)
    except asyncio.CancelledError:
        print("being cancelled, rejecting dialogue and re-raising")
        dlg.finished.disconnect(done)
        dlg.reject()
        raise
