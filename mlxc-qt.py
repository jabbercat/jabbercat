import asyncio
import os.path
import sys

import PyQt4.Qt as Qt
import PyQt4.uic

import quamash

sys.path.insert(0, os.path.abspath("../asyncio-xmpp"))
sys.path.insert(0, os.path.abspath("../asyncio_xmpp"))

app = Qt.QApplication(sys.argv)

import mlxc.roster
roster = mlxc.roster.Roster()
asyncio.set_event_loop(quamash.QEventLoop(app=app))

@asyncio.coroutine
def task():
    roster.show()
    settings = Qt.QSettings("zombofant.net", "mlxc")
    trayicon = Qt.QSystemTrayIcon(roster)
    trayicon.setIcon(Qt.QIcon.fromTheme("edit-copy"))
    trayicon.setToolTip("Hello World!")
    trayicon.setVisible(True)
    print(trayicon.icon())

    while True:
        yield from asyncio.sleep(1)


loop = asyncio.get_event_loop()
loop.run_until_complete(task())
