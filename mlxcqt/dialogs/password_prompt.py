import asyncio

from .. import Qt, utils
from ..ui.dlg_password_prompt import Ui_dlg_password_prompt


class DlgPasswordPrompt(Qt.QDialog, Ui_dlg_password_prompt):
    def __init__(self, jid, *, can_store=False, **kwargs):
        super().__init__(**kwargs)
        self.setupUi(self)

        self.label_info.setText(self.label_info.text().format(
            jid=str(jid)
        ))

        if can_store:
            self.acc_password_warning.hide()
            self.save_password.show()
        else:
            self.acc_password_warning.show()
            self.save_password.hide()

    @asyncio.coroutine
    def run(self):
        result = yield from utils.exec_async(self)
        if result == Qt.QDialog.Accepted:
            return (True,
                    self.password.text(),
                    self.save_password.checkState() == Qt.Qt.Checked)
        else:
            return False, None, False
