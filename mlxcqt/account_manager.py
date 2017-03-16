import asyncio

import PyQt5.Qt as Qt

import mlxc.instrumentable_list
import mlxc.identity

from .ui import dlg_account_manager

from . import add_account, utils, models


class DlgAccountManager(Qt.QDialog):
    def __init__(self, client, identities, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = dlg_account_manager.Ui_DlgAccountManager()
        self.ui.setupUi(self)
        self._add_account_dlg = add_account.DlgAddAccount(
            client,
            identities,
            parent=self
        )

        self.model = models.AccountModel(identities._tree)
        self.ui.accounts_view.setModel(self.model)
        self.ui.accounts_view.selectionModel().currentRowChanged.connect(
            self._item_selected
        )

        self.ui.accounts_view.header().setSectionResizeMode(
            0,
            Qt.QHeaderView.Stretch,
        )

        self.ui.accounts_view.header().resizeSection(
            1,
            64
        )
        self.ui.accounts_view.header().setSectionResizeMode(
            1,
            Qt.QHeaderView.Fixed,
        )

        self.ui.accounts_view.placeholder_text = "No accounts yet! ☹ Add one!"

        self.ui.account_add.clicked.connect(self._add_account)

        identities.on_identity_added.connect(
            self._expand_identity,
            identities.on_identity_added.ASYNC_WITH_LOOP(
                asyncio.get_event_loop()
            ),
        )
        for identity in identities.identities:
            self._expand_identity(identity)

        self._identities = identities
        self._identities.on_identity_added.connect(self._identity_added)
        self._identities.on_identity_removed.connect(self._identity_removed)
        self._update_root()
        self._update_buttons_for(None)

    def _update_root(self):
        if len(self._identities.identities) > 1:
            self.ui.accounts_view.setRootIndex(
                self.model.node_to_index(self._identities.identities)
            )
        elif len(self._identities.identities) == 1:
            self.ui.accounts_view.setRootIndex(
                self.model.node_to_index(self._identities.identities[0])
            )

    def _identity_added(self, identity):
        self._update_root()

    def _identity_removed(self, identity):
        self._update_root()

    def _expand_identity(self, identity):
        self.ui.accounts_view.setExpanded(
            self.model.node_to_index(identity._node),
            True,
        )

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
