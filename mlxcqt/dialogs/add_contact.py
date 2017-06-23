import asyncio

import aioxmpp

from .. import Qt, utils, models
from ..ui import dlg_add_contact


class DlgAddContact(Qt.QDialog):
    def __init__(self, main, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main = main

        self.ui = dlg_add_contact.Ui_DlgAddContact()
        self.ui.setupUi(self)

        self.ui.account.currentAccountChanged.connect(
            self._current_account_changed
        )

        self.base_model = models.AccountModel(main.identities._tree,
                                              main.identities)
        self._disabled_model = models.DisableSelectionOfIdentities()
        self._disabled_model.setSourceModel(self.base_model)
        self._filtered_model = models.FilterDisabledItems()
        self._filtered_model.setSourceModel(self._disabled_model)
        self.ui.account.setModel(self._filtered_model)

    def _current_account_changed(self):
        account = self.ui.account.currentAccount()
        if account is None:
            return
        all_tags = self._get_all_tags(account)
        self.ui.tags.setup(all_tags, [], clear=False)

    def _get_all_tags(self, account_context):
        identity = account_context.identity
        all_groups = set()
        for account in identity.accounts:
            try:
                client = self.main.client.client_by_account(account)
            except KeyError:
                continue
            all_groups |= set(
                client.summon(aioxmpp.RosterClient).groups.keys()
            )
        return all_groups

    def done(self, result):
        if result != Qt.QDialog.Accepted:
            return super().done(result)

        if not self.ui.account.currentAccount():
            return

        if not self.ui.peer_jid.hasAcceptableInput():
            return

        return super().done(result)

    @asyncio.coroutine
    def run(self):
        result = yield from utils.exec_async(self)
        if result != Qt.QDialog.Accepted:
            return

        account = self.ui.account.currentAccount()
        peer_jid = aioxmpp.JID.fromstr(self.ui.peer_jid.text())
        display_name = self.ui.display_name.text()
        tags = self.ui.tags.selected_tags

        return account, peer_jid, display_name, tags
