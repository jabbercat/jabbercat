import asyncio

import aioxmpp.structs

import mlxc.client

from . import Qt, model_adaptor, check_certificate, password_prompt


class AccountsModel(Qt.QAbstractListModel):
    def __init__(self, accounts, parent=None):
        super().__init__(parent=parent)
        self._accounts = accounts
        self._adaptor = model_adaptor.ModelListAdaptor(
            accounts._jidlist,
            self)

        self._accounts.on_account_enabled.connect(
            self._account_enabled)
        self._accounts.on_account_disabled.connect(
            self._account_disabled)
        self._accounts.on_account_refresh.connect(
            self._account_refresh)

    def _account_enabled_changed(self, account):
        row = self._accounts.account_index(account)
        index = self.index(row, column=0, parent=Qt.QModelIndex())
        self.dataChanged.emit(index, index, [Qt.Qt.CheckStateRole])

    def _account_enabled(self, account):
        self._account_enabled_changed(account)

    def _account_disabled(self, account, reason=None):
        self._account_enabled_changed(account)

    def _account_refresh(self, account):
        row = self._accounts.account_index(account)
        index = self.index(row, column=0, parent=Qt.QModelIndex())
        self.dataChanged.emit(index, index)

    def rowCount(self, index=Qt.QModelIndex()):
        if index.isValid():
            return 0
        return len(self._accounts)

    def data(self, index, role=Qt.Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()

        try:
            account = self._accounts[row]
        except IndexError:
            return None

        if role == Qt.Qt.DisplayRole:
            return str(account.jid)
        elif role == Qt.Qt.CheckStateRole:
            return Qt.Qt.Checked if account.enabled else Qt.Qt.Unchecked

        return None

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        row = index.row()

        if role == Qt.Qt.CheckStateRole:
            if value == Qt.Qt.Checked:
                self._accounts.set_account_enabled(
                    self._accounts[row].jid,
                    True)
                return True
            elif value == Qt.Qt.Unchecked:
                self._accounts.set_account_enabled(
                    self._accounts[row].jid,
                    False)
                return True

        return False

    def headerData(self, section, orientation, role):
        if orientation != Qt.Qt.Horizontal:
            return None
        if section != 0:
            return None
        if role != Qt.Qt.DisplayRole:
            return None

        return Qt.translate("dlg_account_manager", "JID")

    def flags(self, index):
        flags = Qt.Qt.ItemIsEnabled | Qt.Qt.ItemIsSelectable
        flags |= Qt.Qt.ItemIsUserCheckable
        return flags


class CustomPresenceStateModel(Qt.QAbstractTableModel):
    def __init__(self, presence_states, parent=None):
        super().__init__(parent=parent)
        self._presence_states = presence_states
        self._adaptor = model_adaptor.ModelListAdaptor(
            presence_states,
            self)

    def rowCount(self, index=Qt.QModelIndex()):
        if index.isValid():
            return 0
        return len(self._presence_states)

    def columnCount(self, index=Qt.QModelIndex()):
        return 2

    def data(self, index, role=Qt.Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()

        state = self._presence_states[row]

        if column == 0:
            if role == Qt.Qt.DisplayRole:
                return state.name
            elif role == Qt.Qt.UserRole:
                return state
        elif column == 1:
            if role == Qt.Qt.DisplayRole:
                try:
                    return state.get_status_for_locale(
                        aioxmpp.structs.LanguageRange.fromstr(
                            Qt.QLocale.system().bcp47Name()
                        ),
                        try_none=True
                    ).text
                except KeyError:
                    pass

        return None

    def headerData(self, index, orientation, role):
        if role != Qt.Qt.DisplayRole or orientation != Qt.Qt.Horizontal:
            return super().headerData(index, orientation, role)

        try:
            return [
                "Name",
                "Default status message"
            ][index]
        except IndexError:
            return super().headerData(index, orientation, role)

    def get_presence_state(self, index):
        return self._presence_states[index]


class AccountManager(mlxc.client.AccountManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.qmodel = AccountsModel(self, None)

    @asyncio.coroutine
    def password_provider(self, jid, nattempt):
        if nattempt == 0:
            try:
                return (yield from super().password_provider(jid, nattempt))
            except KeyError:
                pass

        dlg = password_prompt.DlgPasswordPrompt(jid)
        cont, password, store = yield from dlg.run()
        return password


class Client(mlxc.client.Client):
    AccountManager = AccountManager

    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.presence_states_qmodel = CustomPresenceStateModel(
            self.presence_states)

    @asyncio.coroutine
    def _decide_on_certificate(self, account, verifier):
        dlg = check_certificate.DlgCheckCertificate(account, verifier)
        accept, store = yield from dlg.run()
        if accept and store:
            self.pin_store.pin(account.jid.domain, verifier.leaf_x509)
        return accept
