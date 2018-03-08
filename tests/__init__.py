import asyncio
import sys

import quamash

from jabbercat import Qt


def setup_package():
    global app, loop
    app = Qt.QApplication(sys.argv[:1])
    Qt.QResource.registerResource("resources.rcc")
    loop = quamash.QEventLoop(app=app)
    asyncio.set_event_loop(loop)


def teardown_package():
    app = None
    loop.close()
    asyncio.set_event_loop(None)
