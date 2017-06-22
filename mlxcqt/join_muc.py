import asyncio

import aioxmpp

from . import Qt, models, utils

from .ui import dlg_join_muc


class DisableSelectionOfIdentities(Qt.QIdentityProxyModel):
    def flags(self, index):
        flags = super().flags(index)
        if not index.parent().isValid():
            flags &= ~(Qt.Qt.ItemIsSelectable)
        return flags


class FilterDisabledItems(Qt.QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(
            source_row,
            models.AccountModel.COLUMN_ENABLED,
            source_parent
        )
        is_enabled = self.sourceModel().data(index, Qt.Qt.CheckStateRole)
        if is_enabled != Qt.Qt.Checked:
            return False
        return True


class JoinMuc(Qt.QDialog):
    def __init__(self, identities, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = dlg_join_muc.Ui_DlgJoinMUC()
        self.ui.setupUi(self)

        self.base_model = models.AccountModel(identities._tree, identities)
        self.disabled_model = DisableSelectionOfIdentities()
        self.disabled_model.setSourceModel(self.base_model)
        self.filtered_model = FilterDisabledItems()
        self.filtered_model.setSourceModel(self.disabled_model)

        self._jid_validator = utils.JIDValidator()

        self.ui.account.setModel(self.filtered_model)
        self.ui.account.view().header().hide()
        self.ui.account.view().setColumnHidden(
            models.AccountModel.COLUMN_ENABLED,
            True
        )
        self.ui.account.view().expandAll()
        self.ui.account.currentIndexChanged.connect(
            self._selected_account_changed
        )

        self.ui.mucjid.setValidator(self._jid_validator)
        self.ui.mucjid.editingFinished.connect(
            self._mucjid_edited
        )

        # find first selectable
        model = self.ui.account.model()
        for i in range(model.rowCount(Qt.QModelIndex())):
            identity_index = model.index(i, 0, Qt.QModelIndex())
            if model.rowCount(identity_index) > 0:
                account_index = model.index(
                    0, 0,
                    identity_index
                )
                break
        else:
            account_index = Qt.QModelIndex()

        self._account_index = None

        if account_index.isValid():
            self.ui.account.selectIndex(account_index)

    def _selected_account_changed(self, *args, **kwargs):
        new_index = self.ui.account.currentModelIndex()
        if not new_index.isValid():
            return
        self._account_index = new_index

    def _mucjid_edited(self):
        jid = aioxmpp.JID.fromstr(self.ui.mucjid.text())
        if jid.resource and not self.ui.nickname.text():
            self.ui.nickname.setText(jid.resource)
            self.ui.mucjid.setText(str(jid.bare()))

    def done(self, r):
        if r != Qt.QDialog.Accepted:
            return super().done(r)

        # TODO: produce proper error messages here
        if not self.ui.mucjid.hasAcceptableInput():
            return

        jid = aioxmpp.JID.fromstr(self.ui.mucjid.text())
        if not jid.is_bare:
            return

        if not self._account_index:
            return

        if not self.ui.nickname.text():
            return

        return super().done(r)

    @asyncio.coroutine
    def run(self):
        result = yield from utils.exec_async(self)
        if result != Qt.QDialog.Accepted:
            return None

        account = self.filtered_model.data(
            self._account_index,
            models.AccountModel.ROLE_OBJECT,
        )

        return (account,
                aioxmpp.JID.fromstr(self.ui.mucjid.text()),
                self.ui.nickname.text())
