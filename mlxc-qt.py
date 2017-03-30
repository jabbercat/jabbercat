#!/usr/bin/env python3
import asyncio
import logging
import os.path
import sys

os.environ["QUAMASH_QTIMPL"] = "PyQt5"

import mlxcqt.Qt as Qt
import quamash

app = Qt.QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

import mlxcqt.main

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("quamash").setLevel(logging.INFO)
logging.getLogger("aioxmpp").setLevel(logging.WARNING)
logging.getLogger("aioxmpp.XMLStream").setLevel(logging.DEBUG)

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

Qt.QResource.registerResource("resources.rcc")

asyncio.set_event_loop(quamash.QEventLoop(app=app))
loop = asyncio.get_event_loop()
main = mlxcqt.main.QtMain(loop)
try:
    returncode = loop.run_until_complete(main.run())
finally:
    loop.close()
    # try very hard to evict parts from memory
    import gc
    gc.collect()
    del main
    gc.collect()
    del app
    asyncio.set_event_loop(None)
    del loop
    gc.collect()

sys.exit(returncode)
