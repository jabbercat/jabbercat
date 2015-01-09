#!/usr/bin/env python3
import asyncio
import logging
import os.path
import sys

os.environ["QUAMASH_QTIMPL"] = "PyQt5"
sys.path.insert(0, os.path.abspath("../asyncio-xmpp"))
sys.path.insert(0, os.path.abspath("../asyncio_xmpp"))

import mlxc.qt.Qt as Qt
import quamash

app = Qt.QApplication(sys.argv)

import mlxc.qt.main

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("quamash").setLevel(logging.INFO)
logging.getLogger("asyncio_xmpp").setLevel(logging.INFO)

asyncio.set_event_loop(quamash.QEventLoop(app=app))
loop = asyncio.get_event_loop()
main = mlxc.qt.main.MLXCQt(loop)
loop.run_forever()
result = main.returncode
del main
del app

sys.exit(result)
