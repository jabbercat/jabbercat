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

locale = Qt.QLocale.system().name()
qttr = Qt.QTranslator(parent=app)
if not qttr.load("qt_" + locale,
                 Qt.QLibraryInfo.location(Qt.QLibraryInfo.TranslationsPath)):
    logging.warning("failed to load Qt translations for %s", locale)
else:
    app.installTranslator(qttr)

qttr = Qt.QTranslator(parent=app)
if not qttr.load("qttranslations/mlxcqt_" + locale):
    logging.warning("failed to load MLXC translations for %s", locale)
else:
    app.installTranslator(qttr)

asyncio.set_event_loop(quamash.QEventLoop(app=app))
loop = asyncio.get_event_loop()
main = mlxcqt.main.QtMain(loop)
returncode = loop.run_until_complete(main.run())
del main
del app
asyncio.set_event_loop(None)
del loop

# try very hard to evict app from memory...
import gc
gc.collect()

sys.exit(returncode)
