import asyncio
import sys

import PyQt4.Qt as Qt
import PyQt4.uic

import quamash

app = Qt.QApplication(sys.argv)

roster = PyQt4.uic.loadUi("data/roster.ui")
asyncio.set_event_loop(quamash.QEventLoop(app=app))

@asyncio.coroutine
def task():
    roster.show()
    while True:
        yield from asyncio.sleep(1)

loop = asyncio.get_event_loop()
loop.run_until_complete(task())
