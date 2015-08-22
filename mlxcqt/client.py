import mlxc.client

from . import Qt, model_adaptor


class AccountsModel(Qt.QAbstractListModel):
    def __init__(self, accounts, parent=None):
        super().__init__(parent=parent)
        self._accounts = accounts
        self._adaptor = model_adaptor.ModelListAdaptor(
            accounts._jidlist,
            self)

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self._accounts)

    def data(self, index, role):
        if not index.isValid():
            return None

        row = index.row()

        if role == Qt.Qt.DisplayRole:
            try:
                account = self._accounts[row]
            except IndexError:
                return None
            return str(account.jid)

        return None

    def headerData(self, section, orientation, role):
        if orientation != Qt.Qt.Horizontal:
            return None
        if section != 0:
            return None
        if role != Qt.Qt.DisplayRole:
            return None

        return "JID"

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
