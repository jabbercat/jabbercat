import asyncio

import aioxmpp.structs

import mlxc.client

from . import Qt
from .ui.roster import Ui_roster_window


class RosterWindow(Qt.QMainWindow, Ui_roster_window):
    def __init__(self, main):
        super().__init__()

        self._main = main

        self.setupUi(self)

    def closeEvent(self, event):
        result = super().closeEvent(event)
        self._main._done_future.set_result(0)
        return result


class MLXCQt:
    def __init__(self, event_loop):
        self._loop = event_loop
        self._client = mlxc.client.Client()
        self._roster = RosterWindow(self)
        self._done_future = asyncio.Future()

    @asyncio.coroutine
    def run(self):
        self._client.load_state()
        self._roster.show()
        return (yield from self._done_future)
