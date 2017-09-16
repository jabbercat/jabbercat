import asyncio

import aioxmpp.structs

from . import Qt, utils
from .ui.dlg_input_jid import Ui_dlg_input_jid


class DlgInputJID(Qt.QDialog, Ui_dlg_input_jid):
    def __init__(self, title, text, parent):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.validator = utils.JIDValidator()

        self.label.setText(text)
        self.setWindowTitle(title)
        self.jid.setValidator(self.validator)

    @asyncio.coroutine
    def run(self):
        result = yield from utils.exec_async(self)
        if result == Qt.QDialog.Accepted:
            return aioxmpp.structs.JID.fromstr(self.jid.text())
        return None
