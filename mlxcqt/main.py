import asyncio

import aioxmpp.structs

import mlxc.client
import mlxc.main

import mlxcqt.model_adaptor as model_adaptor

from . import Qt, utils, client
from .ui.dlg_account_manager import Ui_dlg_account_manager
from .ui.dlg_account_editor import Ui_dlg_account_editor
from .ui.roster import Ui_roster_window


class DlgAccountEditor(Qt.QDialog, Ui_dlg_account_editor):
    def __init__(self, dlg_account_manager, account):
        super().__init__(parent=dlg_account_manager)
        self.mlxc = dlg_account_manager.mlxc
        self.accounts = dlg_account_manager.accounts
        self.account = account

        self.setupUi(self)

        self.acc_password_warning.setVisible(
            not self.accounts.keyring_is_safe
        )

        self._modified = False
        utils.asyncify(utils.block_widget_for_coro)(self, self._reset())

    @asyncio.coroutine
    def _reset(self):
        try:
            password = yield from self.accounts.get_stored_password(
                self.account.jid
            )
            self.acc_password.setText(password or "")
            self.acc_save_password.setChecked(bool(password))
        except mlxc.client.PasswordStoreIsUnsafe:
            self.acc_save_password.setChecked(False)
            self.acc_save_password.setEnabled(False)

        self.acc_require_encryption.setChecked(
            not self.account.allow_unencrypted
        )

        if self.account.override_peer:
            self.acc_override_host.setText(
                self.account.override_peer.host or ""
            )
            self.acc_override_port.setValue(
                self.account.override_peer.port or 5222
            )
        else:
            self.acc_override_host.setText("")
            self.acc_override_port.setValue(5222)

        self.acc_jid.setText(str(self.account.jid))
        self.acc_resource.setText(self.account.resource)

    @asyncio.coroutine
    def _save(self):
        if     (self.acc_save_password.checkState() == Qt.Qt.Checked and
                self.acc_password.text()):
            try:
                yield from self.accounts.set_stored_password(
                    self.account.jid,
                    self.acc_password.text(),
                )
            except mlxc.client.PasswordStoreIsUnsafe:
                pass

        self.account.allow_unencrypted = (
            self.acc_require_encryption.checkState() != Qt.Qt.Checked
        )

        self.account.resource = self.acc_resource.text() or None

        if self.acc_override_host.text():
            self.account.override_peer = mlxc.client.ConnectionOverride()
            self.account.override_peer.host = self.acc_override_host.text()
            self.account.override_peer.port = self.acc_override_port.value()
        else:
            self.account.override_peer = None

    @utils.asyncify_blocking
    @asyncio.coroutine
    def accept(self):
        yield from self._save()
        super().accept()


class DlgAccountManager(Qt.QDialog, Ui_dlg_account_manager):
    def __init__(self, main_window):
        super().__init__()
        self.mlxc = main_window.mlxc
        self.accounts = self.mlxc.client.accounts

        self.setupUi(self)
        self.setModal(False)

        model_wrapper = Qt.QSortFilterProxyModel(self)
        model_wrapper.setSourceModel(self.accounts.qmodel)
        model_wrapper.setSortLocaleAware(True)
        model_wrapper.setSortCaseSensitivity(False)
        model_wrapper.setSortRole(Qt.Qt.DisplayRole)
        model_wrapper.setDynamicSortFilter(True)

        self.account_list.setModel(model_wrapper)
        self.account_list.setSelectionBehavior(Qt.QTableView.SelectRows);
        self.account_list.setSelectionMode(Qt.QTableView.SingleSelection);
        self.account_list.setSortingEnabled(True)
        self.account_list.sortByColumn(0, Qt.Qt.AscendingOrder)

        self.account_list.activated.connect(self._account_list_activated)

        self._modified = False

    @utils.asyncify
    @asyncio.coroutine
    def _account_list_activated(self, index):
        if not index.isValid():
            return

        account = self.mlxc.client.accounts[index.row()]

        dlg = DlgAccountEditor(self, account)
        yield from utils.exec_async(dlg)

    @asyncio.coroutine
    def _change_account_to(self, account):
        if self._current_account is account:
            return

        self.tabs.setCurrentIndex(0)
        self._current_account = account
        yield from self._reset_current()


class RosterWindow(Qt.QMainWindow, Ui_roster_window):
    def __init__(self, mlxc):
        super().__init__()

        self.mlxc = mlxc
        self.account_manager = DlgAccountManager(self)

        self.setupUi(self)

        self.action_quit.triggered.connect(
            self._on_quit)
        self.action_account_manager.triggered.connect(
            self._on_account_manager)

        self.online_selector.stateChanged.connect(
            self._on_online_state_changed)

    def _on_quit(self):
        self.mlxc.main.quit()

    def _on_account_manager(self):
        self.account_manager.show()

    def _on_online_state_changed(self, state):
        if state == Qt.Qt.Checked:
            self.mlxc.client.set_global_presence(
                aioxmpp.structs.PresenceState(available=True)
            )
        else:
            self.mlxc.client.set_global_presence(
                aioxmpp.structs.PresenceState(available=False)
            )

    def closeEvent(self, event):
        result = super().closeEvent(event)
        self.mlxc.main.quit()
        return result


class MLXCQt:
    def __init__(self, main, event_loop):
        self.main = main
        self.loop = event_loop
        self.client = client.Client()
        self.roster = RosterWindow(self)

    @asyncio.coroutine
    def run(self, main_future):
        self.client.load_state()
        self.roster.show()
        yield from main_future
        self.client.save_state()


class QtMain(mlxc.main.Main):
    @asyncio.coroutine
    def run_core(self):
        mlxc = MLXCQt(self, self.loop)
        yield from mlxc.run(self.main_future)
        del mlxc
