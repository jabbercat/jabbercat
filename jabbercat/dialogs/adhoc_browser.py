import asyncio
import functools
import html
import logging

import aioxmpp
import aioxmpp.adhoc

import jclib.client
import jclib.identity

from .. import Qt, utils, models

from ..ui import dlg_adhoc_browser, dlg_adhoc_execute
from ..widgets import misc, forms


logger = logging.getLogger(__name__)


class AdHocCommandFlow(Qt.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = dlg_adhoc_execute.Ui_DlgAdhocExecute()
        self.ui.setupUi(self)

        self.ui.buttons.addButton(self.ui.btnPrev,
                                  Qt.QDialogButtonBox.AcceptRole)
        self.ui.buttons.addButton(self.ui.btnNext,
                                  Qt.QDialogButtonBox.AcceptRole)

        self.action_buttons = {
            aioxmpp.adhoc.ActionType.NEXT: self.ui.btnNext,
            aioxmpp.adhoc.ActionType.PREV: self.ui.btnPrev,
            aioxmpp.adhoc.ActionType.COMPLETE:
                self.ui.buttons.button(Qt.QDialogButtonBox.Ok),
        }

        for action, btn in self.action_buttons.items():
            btn.clicked.connect(functools.partial(
                self._action,
                action,
            ))

        self.action_buttons[aioxmpp.adhoc.ActionType.CANCEL] = \
            self.ui.buttons.button(Qt.QDialogButtonBox.Cancel)

        self.action_buttons[aioxmpp.adhoc.ActionType.CANCEL].clicked.connect(
            self._cancel,
        )
        self.btn_close = self.ui.buttons.button(Qt.QDialogButtonBox.Close)
        self.btn_close.clicked.connect(self._close)

    @utils.asyncify_blocking
    async def _action(self, action, *_):
        self.ui.form.form_area.apply()
        await self.session.proceed(action=action)
        self.response_received()

    def _cancel(self, *_):
        self.close()

    def _close(self, *_):
        self.close()

    def _update_buttons(self):
        status = self.session.status
        if status != aioxmpp.adhoc.CommandStatus.EXECUTING:
            for btn in self.action_buttons.values():
                btn.hide()

            self.btn_close.show()
        else:
            self.btn_close.hide()
            allowed_actions = self.session.allowed_actions
            for action, btn in self.action_buttons.items():
                if action in allowed_actions:
                    btn.show()
                else:
                    btn.hide()

    def _update_notes(self):
        notes = self.session.response.notes
        if not notes:
            self.ui.notes_area.hide()
            return

        self.ui.notes_area.show()
        source_parts = []
        for note in notes:
            print(note.type_, note.body)
            source_parts.append("<p><b>{}: </b>{}</p>".format(
                html.escape(note.type_.value),
                "</p><p>".join(html.escape(note.body or "").split("\n"))
            ))

        self.ui.notes_area.setText("\n".join(source_parts))

    @utils.asyncify_blocking
    async def start(self,
                    adhoc_client: aioxmpp.AdHocClient,
                    target_address: aioxmpp.JID,
                    target_node: str):
        self.show()
        try:
            self.session = await adhoc_client.execute(
                target_address,
                target_node,
            )
        except aioxmpp.errors.XMPPError as exc:
            self.fail(str(exc))
            return

        self.response_received()

    def response_received(self):
        self._update_buttons()
        self._update_notes()

        payload = self.session.first_payload
        if not isinstance(payload, aioxmpp.forms.Data):
            self.ui.form.hide()
            return

        self.ui.form.show()
        self.ui.form.setup(payload)
        self.ui.form.form_area.form = payload

    def fail(self, message):
        Qt.QMessageBox.critical(
            self.parent(),
            "Error",
            message,
        )
        self.close()


class DlgAdhocBrowser(Qt.QDialog):
    def __init__(self,
                 accounts: jclib.identity.Accounts,
                 client: jclib.client.Client,
                 parent):
        super().__init__(parent)

        self.ui = dlg_adhoc_browser.Ui_DlgAdhocBrowser()
        self.ui.setupUi(self)

        self._accounts = accounts
        self._client = client
        self._current_account_address = None
        self._current_client = None
        self._scan_task = None
        self._commands = models.DiscoItemsModel()
        self._services = models.DiscoItemsModel()

        self._sorted_commands = Qt.QSortFilterProxyModel()
        self._sorted_commands.setSourceModel(self._commands)
        self._sorted_commands.setSortRole(Qt.Qt.DisplayRole)
        self._sorted_commands.setDynamicSortFilter(True)
        self._sorted_commands.sort(models.DiscoItemsModel.COLUMN_NAME)

        self._sorted_services = Qt.QSortFilterProxyModel()
        self._sorted_services.setSourceModel(self._services)
        self._sorted_services.setSortRole(Qt.Qt.DisplayRole)
        self._sorted_services.setDynamicSortFilter(True)
        self._sorted_services.sort(models.DiscoItemsModel.COLUMN_NAME)

        self.ui.account.currentIndexChanged.connect(
            self._current_index_changed
        )

        validator = utils.JIDValidator(self.ui.address)
        self.ui.address.setValidator(validator)

        self.base_model = models.AccountsModel(self._accounts)
        filtered = models.FilterDisabledItems(self.ui.account)
        filtered.setSourceModel(self.base_model)
        self.ui.account.setModel(filtered)

        self.ui.commands.setModel(self._sorted_commands)
        self.ui.commands.setModelColumn(models.DiscoItemsModel.COLUMN_NAME)
        self.ui.commands.activated.connect(self._command_activated)

        self.ui.services.setModel(self._sorted_services)
        self.ui.services.setColumnHidden(models.DiscoItemsModel.COLUMN_NODE,
                                         True)

        self.ui.services.activated.connect(self._service_activated)

        self.ui.btnScan.clicked.connect(self._scan_clicked)

    def showEvent(self, ev: Qt.QShowEvent):
        self._current_index_changed(self.ui.account.currentIndex())
        self._scan_clicked()
        super().showEvent(ev)

    def _set_current_address(self, new_address):
        old_address = self._current_account_address
        self._current_account_address = new_address
        print(old_address, new_address)

        if (old_address is None or
                (old_address.domain != self.ui.address.text() and
                 self.ui.address.text())):
            return

        if new_address is None:
            return

        self.ui.address.setText(new_address.domain)

    def _current_index_changed(self, new_index):
        enabled = new_index >= 0
        self.ui.address.setEnabled(enabled)
        self.ui.btnScan.setEnabled(enabled)
        self.ui.commands.setEnabled(enabled)
        self.ui.services.setEnabled(enabled)

        if enabled:
            model = self.ui.account.model()
            account = model.data(
                model.index(new_index, 0),
                models.ROLE_OBJECT,
            )
            self._set_current_address(account.jid)
            self._current_client = account.client
        else:
            self._set_current_address(None)
            self._current_client = None

    async def _execute_scan(self,
                            client: aioxmpp.Client,
                            target_address: aioxmpp.JID):
        jclib.tasks.manager.update_text("Scanning {}".format(target_address))
        disco_client = client.summon(aioxmpp.DiscoClient)
        adhoc_client = client.summon(aioxmpp.AdHocClient)

        try:
            services = (await disco_client.query_items(target_address)).items
        except aioxmpp.XMPPCancelError as exc:
            logger.debug("failed to fetch services of %s: %s",
                         target_address,
                         exc)
            services = []

        try:
            commands = await adhoc_client.get_commands(target_address)
        except aioxmpp.XMPPCancelError as exc:
            if exc.condition != aioxmpp.ErrorCondition.ITEM_NOT_FOUND:
                raise
            commands = []

        self._services.replace(services)
        self._commands.replace(commands)

    def _scan_clicked(self, *_):
        if self._current_client is None:
            return

        address = aioxmpp.JID.fromstr(self.ui.address.text())

        if self._scan_task is not None and not self._scan_task.done():
            self._scan_task.cancel()
            self._scan_task = None

        self._scan_task = jclib.tasks.manager.start(self._execute_scan(
            self._current_client,
            address,
        )).asyncio_task

    def _service_activated(self, index: Qt.QModelIndex):
        if not index.isValid():
            return

        address = index.sibling(
            index.row(),
            models.DiscoItemsModel.COLUMN_JID,
        ).data(Qt.Qt.DisplayRole)

        self.ui.address.setText(address)
        self._scan_clicked()

    def _command_activated(self, index: Qt.QModelIndex):
        if self._current_client is None:
            return

        if not index.isValid():
            return

        address = index.sibling(
            index.row(),
            models.DiscoItemsModel.COLUMN_JID,
        ).data(Qt.Qt.DisplayRole)

        node = index.sibling(
            index.row(),
            models.DiscoItemsModel.COLUMN_NODE,
        ).data(Qt.Qt.DisplayRole)

        executor_dlg = AdHocCommandFlow(self)
        executor_dlg.start(self._current_client.summon(aioxmpp.AdHocClient),
                           aioxmpp.JID.fromstr(address),
                           node)
