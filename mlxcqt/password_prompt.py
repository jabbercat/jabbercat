import asyncio

from . import Qt, utils
from .ui.dlg_password_prompt import Ui_dlg_password_prompt


class DlgPasswordPrompt(Qt.QDialog, Ui_dlg_password_prompt):
    def __init__(self, jid, **kwargs):
        super().__init__(**kwargs)
        self.setupUi(self)

        self.label_info.setText(self.label_info.text().format(
            jid=str(jid)
        ))

    @asyncio.coroutine
    def run(self):
        result = yield from utils.exec_async(self)
        if result == Qt.QDialog.Accepted:
            return (True,
                    self.password.text(),
                    self.save_password.checkState() == Qt.Qt.Checked)
        else:
            return False, None, False
