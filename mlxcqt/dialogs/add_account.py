import asyncio

import PyQt5.Qt as Qt

import aioxmpp

import mlxc.client
import mlxc.config

from .. import utils, models

from ..ui import dlg_add_account


class DlgAddAccount(Qt.QWizard):
    def __init__(self, client, identities, parent=None):
        super().__init__(parent)
        self._client = client
        self._identities = identities
        self.ui = dlg_add_account.Ui_DlgAddAccount()
        self.ui.setupUi(self)
        self.identities_model = models.AccountModel(
            self._identities._tree
        )

        self.ui.page_credentials._wizard = self
        self.ui.page_connecting._wizard = self

    def _reset_ui_state(self):
        self.restart()
        self.ui.page_credentials.reset_ui_state()
        self.ui.page_connecting.reset_ui_state()

    @asyncio.coroutine
    def run(self, default_identity=None):
        self._reset_ui_state()

        self.ui.page_credentials.ui.identity.clearEditText()
        if default_identity is not None:
            self.ui.page_credentials.ui.identity.setCurrentIndex(
                self.identities_model.node_to_index(
                    default_identity._node
                ).row()
            )
        else:
            if len(self._identities.identities) > 0:
                self.ui.page_credentials.ui.identity.setCurrentIndex(0)
            else:
                self.ui.page_credentials.ui.identity.setCurrentText("Default")

        result = yield from utils.exec_async(self)
        if not result:
            return

        selected_identity = self.ui.page_credentials.ui.identity.currentIndex()
        identity_name = self.ui.page_credentials.ui.identity.currentText()
        if selected_identity >= 0:
            identity = self._identities.identities[selected_identity]
            if identity.name != identity_name:
                selected_identity = -1

        if selected_identity < 0:
            # create new
            identity = self._identities.new_identity(
                identity_name,
            )

        jid = aioxmpp.JID.fromstr(self.field("jid"))
        self._identities.new_account(
            identity,
            jid,
            (0, 0, 0),
        )

        try:
            yield from self._client.set_stored_password(
                jid,
                self.field("password"),
            )
        except mlxc.client.PasswordStoreIsUnsafe:
            pass

        mlxc.config.config_manager.writeback()
