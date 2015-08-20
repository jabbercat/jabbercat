import asyncio

import aioxmpp.structs

import mlxc.client
import mlxc.main

from . import Qt
from .ui.roster import Ui_roster_window


class RosterWindow(Qt.QMainWindow, Ui_roster_window):
    def __init__(self, mlxc):
        super().__init__()

        self._mlxc = mlxc

        self.setupUi(self)

        self.action_quit.triggered.connect(
            self._on_quit)

    def _on_quit(self):
        self._mlxc.main.quit()

    def closeEvent(self, event):
        result = super().closeEvent(event)
        self._mlxc.main.quit()
        return result


class MLXCQt:
    def __init__(self, main, event_loop):
        self.main = main
        self.loop = event_loop
        self.client = mlxc.client.Client()
        self.roster = RosterWindow(self)

    @asyncio.coroutine
    def run(self, main_future):
        self.client.load_state()
        self.roster.show()
        yield from main_future


class QtMain(mlxc.main.Main):
    @asyncio.coroutine
    def run_core(self):
        mlxc = MLXCQt(self, self.loop)
        yield from mlxc.run(self.main_future)
        del mlxc
