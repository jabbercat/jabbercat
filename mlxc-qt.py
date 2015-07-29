#!/usr/bin/env python3
import asyncio
import logging
import os.path
import sys

os.environ["QUAMASH_QTIMPL"] = "PyQt5"

import mlxcqt.Qt as Qt
import quamash

app = Qt.QApplication(sys.argv)

import mlxcqt.main

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("quamash").setLevel(logging.INFO)
logging.getLogger("aioxmpp").setLevel(logging.DEBUG)

asyncio.set_event_loop(quamash.QEventLoop(app=app))
loop = asyncio.get_event_loop()
main = mlxcqt.main.MLXCQt(loop)
returncode = loop.run_until_complete(main.run())
del main
del app
asyncio.set_event_loop(None)
del loop

# try very hard to evict app from memory...
import gc
gc.collect()

sys.exit(returncode)
