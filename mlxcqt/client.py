import mlxc.client

from . import Qt, model_adaptor


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

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self._accounts)

    def data(self, index, role):
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


class AccountManager(mlxc.client.AccountManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.qmodel = AccountsModel(self, None)


class Client(mlxc.client.Client):
    AccountManager = AccountManager
