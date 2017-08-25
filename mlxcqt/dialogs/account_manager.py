import asyncio

import PyQt5.Qt as Qt

import mlxc.instrumentable_list
import mlxc.identity

from .. import utils, models
from ..ui import dlg_account_manager

from . import add_account


class DlgAccountManager(Qt.QDialog):
    def __init__(self, client,
                 accounts: mlxc.identity.Accounts,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = dlg_account_manager.Ui_DlgAccountManager()
        self.ui.setupUi(self)
        self._add_account_dlg = add_account.DlgAddAccount(
            client,
            accounts,
            parent=self
        )

        self.model = models.AccountsModel(accounts)
        self.ui.accounts_view.setModel(self.model)
        self.ui.accounts_view.selectionModel().currentRowChanged.connect(
            self._item_selected
        )

        self.ui.accounts_view.horizontalHeader().setSectionResizeMode(
            0,
            Qt.QHeaderView.Stretch,
        )

        self.ui.accounts_view.horizontalHeader().resizeSection(
            1,
            64
        )
        self.ui.accounts_view.horizontalHeader().setSectionResizeMode(
            1,
            Qt.QHeaderView.Fixed,
        )

        self.ui.accounts_view.placeholder_text = "No accounts yet! ☹ Add one!"

        self.ui.account_add.clicked.connect(self._add_account)

        self._update_buttons_for(None)

    def _item_selected(self, index):
        if not index.isValid():
            object_ = None
        else:
            object_ = index.internalPointer()
        self._update_buttons_for(object_)

    def _update_buttons_for(self, object_):
        # is_identity = isinstance(object_, mlxc.identity.Identity)
        is_account = isinstance(object_, mlxc.identity.Account)

        self.ui.account_edit.setEnabled(is_account)
        self.ui.account_remove.setEnabled(is_account)

    @utils.asyncify
    def _add_account(self, *args):
        yield from self._add_account_dlg.run()
