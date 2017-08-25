import asyncio

import PyQt5.Qt as Qt

import aioxmpp

import mlxc.client
import mlxc.config
import mlxc.identity

from .. import utils, models

from ..ui import dlg_add_account


class DlgAddAccount(Qt.QWizard):
    def __init__(self,
                 client: mlxc.client.Client,
                 accounts: mlxc.identity.Accounts, parent=None):
        super().__init__(parent)
        self._client = client
        self._accounts = accounts
        self.ui = dlg_add_account.Ui_DlgAddAccount()
        self.ui.setupUi(self)

        self.ui.page_credentials._wizard = self
        self.ui.page_connecting._wizard = self

    def _reset_ui_state(self):
        self.restart()
        self.ui.page_credentials.reset_ui_state()
        self.ui.page_connecting.reset_ui_state()

    @asyncio.coroutine
    def run(self):
        self._reset_ui_state()

        result = yield from utils.exec_async(self)
        if not result:
            return

        jid = aioxmpp.JID.fromstr(self.field("jid"))
        self._accounts.new_account(
            jid,
            tuple(round(x * 255) for x in mlxc.utils.text_to_colour(str(jid)))
        )

        try:
            yield from self._client.set_stored_password(
                jid,
                self.field("password"),
            )
        except mlxc.client.PasswordStoreIsUnsafe:
            pass

        mlxc.config.config_manager.writeback()
