import asyncio

import aioxmpp

import jclib.client
import jclib.identity

from .. import Qt, utils, models
from ..ui import dlg_add_contact


class DlgAddContact(Qt.QDialog):
    def __init__(self,
                 client: jclib.client.Client,
                 accounts: jclib.identity.Accounts,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._accounts = accounts
        self._client = client

        self.ui = dlg_add_contact.Ui_DlgAddContact()
        self.ui.setupUi(self)

        self.ui.account.currentIndexChanged.connect(
           self._current_index_changed
        )

        validator = utils.JIDValidator(self.ui.peer_jid)
        self.ui.peer_jid.setValidator(validator)

        self.base_model = models.AccountsModel(accounts)
        filtered = models.FilterDisabledItems(self.ui.account)
        filtered.setSourceModel(self.base_model)
        self.ui.account.setModel(filtered)

        print("configured")

    def _current_index_changed(self, index):
        all_tags = self._get_all_tags()
        self.ui.tags.setup(all_tags, [], clear=False)

    def _get_all_tags(self):
        all_groups = set()
        for account in self._accounts:
            try:
                client = self._client.client_by_account(account)
            except KeyError:
                continue
            all_groups |= set(
                client.summon(aioxmpp.RosterClient).groups.keys()
            )
        return all_groups

    def done(self, result):
        if result != Qt.QDialog.Accepted:
            return super().done(result)

        index = self.ui.account.currentIndex()
        if index < 0:
            return

        if not self.ui.peer_jid.hasAcceptableInput():
            return

        return super().done(result)

    @asyncio.coroutine
    def run(self):
        print("run")
        result = yield from utils.exec_async(self)
        if result != Qt.QDialog.Accepted:
            return

        account_index = self.ui.account.currentIndex()
        account = self.ui.account.model().data(
            self.ui.account.model().index(account_index, 0),
            models.ROLE_OBJECT,
        )
        peer_jid = aioxmpp.JID.fromstr(self.ui.peer_jid.text())
        display_name = self.ui.display_name.text()
        tags = self.ui.tags.selected_tags

        return account, peer_jid, display_name, tags
