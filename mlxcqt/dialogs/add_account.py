import asyncio
import logging
import uuid

import PyQt5.Qt as Qt

import aioxmpp

import mlxc.client
import mlxc.config

from ..ui import (
    dlg_add_account_page_credentials,
    dlg_add_account_page_connecting,
)

from .. import utils, models


class AddAccountWizardPage(Qt.QWizardPage):
    _wizard = None


class PageCredentials(AddAccountWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = dlg_add_account_page_credentials.Ui_WizardPage()
        self.ui.setupUi(self)
        self.ui.expert_options.hide()
        self.ui.expert_options_switch.stateChanged.connect(
            self._expert_options_switch_changed
        )

        self.ui.jid.setValidator(
            utils.JIDValidator(self.ui.jid),
        )

        self.ui.password.setInputMethodHints(
            Qt.Qt.ImhHiddenText |
            Qt.Qt.ImhSensitiveData |
            Qt.Qt.ImhNoAutoUppercase |
            Qt.Qt.ImhNoPredictiveText
        )
        self.ui.password.setEchoMode(Qt.QLineEdit.Password)

        self.registerField(
            "jid*",
            self.ui.jid,
        )

        self.registerField(
            "password*",
            self.ui.password,
        )

        self.registerField(
            "server_host",
            self.ui.server_host,
        )

        self.registerField(
            "server_port",
            self.ui.server_port,
        )

        self.registerField(
            "identity",
            self.ui.identity,
        )

    def _expert_options_switch_changed(self, new_state):
        if new_state == Qt.Qt.Checked:
            self.ui.expert_options.show()
        else:
            self.ui.expert_options.hide()

    def _remove_identity_widgets_from_layout(self, layout):
        index = layout.indexOf(
            self.ui.identity_group
        )
        if index > 0:
            layout.takeAt(index)

        index = layout.indexOf(
            self.ui.identity_label
        )
        if index > 0:
            layout.takeAt(index)

    def reset_ui_state(self):
        self.ui.expert_options_switch.setCheckState(
            Qt.Qt.Unchecked
        )
        if len(self._wizard._identities.identities) > 1:
            self._remove_identity_widgets_from_layout(
                self.ui.expert_options.layout()
            )
            self.ui.main_layout.addRow(
                self.ui.identity_label,
                self.ui.identity_group,
            )
        else:
            self._remove_identity_widgets_from_layout(
                self.ui.main_layout
            )
            self.ui.expert_options.layout().addRow(
                self.ui.identity_label,
                self.ui.identity_group,
            )

        self.ui.identity.setModel(self._wizard.identities_model)
        self.ui.identity.setModelColumn(
            self._wizard.identities_model.COLUMN_NAME
        )


class TextViewHandler(logging.Handler):
    prefix = None

    def __init__(self, textview):
        super().__init__()
        self.textview = textview

    def set_prefix(self, prefix):
        self.prefix = prefix

    def emit(self, record):
        logger_name = record.name
        if logger_name.startswith(self.prefix):
            # strip the dot, too
            logger_name = "log" + logger_name[len(self.prefix):]

        msg = "{:<4s}  {}  {}\n".format(
            record.levelname[:4],
            logger_name,
            record.msg % record.args,
        )

        cursor = Qt.QTextCursor(self.textview.document())
        cursor.movePosition(Qt.QTextCursor.End)
        cursor.insertText(msg)


class PageConnecting(AddAccountWizardPage):
    _complete = False

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = dlg_add_account_page_connecting.Ui_WizardPage()
        self.ui.setupUi(self)

        self.ui.user_log.setFont(Qt.QFontDatabase.systemFont(
            Qt.QFontDatabase.FixedFont
        ))

        self.ui.expert_log.setFont(Qt.QFontDatabase.systemFont(
            Qt.QFontDatabase.FixedFont
        ))

        self.ui.expert_log.hide()
        self.ui.expert_switch.stateChanged.connect(
            self._expert_switch_changed,
        )

        self.user_handler = TextViewHandler(self.ui.user_log)
        self.expert_handler = TextViewHandler(self.ui.expert_log)

        self.optional_steps = [
            self._step_server_info,
            self._step_avatar,
        ]

    def _expert_switch_changed(self, new_state):
        if new_state == Qt.Qt.Checked:
            self.ui.expert_log.show()
        else:
            self.ui.expert_log.hide()

    def reset_ui_state(self):
        self.ui.expert_switch.setCheckState(Qt.Qt.Unchecked)

    def initializePage(self):
        super().initializePage()
        self.ui.user_log.clear()
        self.ui.expert_log.clear()

        prefix = ".".join([__name__, "test", str(uuid.uuid4())])
        self.logger = logging.getLogger(
            prefix
        )
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.expert_handler)
        self.user_logger = self.logger.getChild("status")
        self.user_logger.addHandler(self.user_handler)
        self.expert_handler.set_prefix(prefix)
        self.user_handler.set_prefix(prefix + ".status")

        self.ui.progress.setRange(0, 0)

        self.logger.info("testing connectivity")

        self.task = asyncio.ensure_future(self.run())
        self.task.add_done_callback(self.task_done)

    def task_done(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.logger.exception("Set up task failed")
            self.user_logger.error(
                "Set up failed! (%s) Please go back and check your settings.",
                exc,
            )
        else:
            self.wizard().next()
            return
        self.ui.progress.setRange(0, 1)
        self.ui.progress.setValue(0)
        del self.client

    async def _step_server_info(self, i):
        self.user_logger.info("Discovering features ...")
        info = await self.client.summon(aioxmpp.DiscoClient).query_info(
            self.client.local_jid.replace(localpart=None, resource=None),
        )
        self.logger.info("features = %r", info)

    async def _step_avatar(self, i):
        pass

    async def run(self):
        jid = aioxmpp.JID.fromstr(self.wizard().field("jid"))

        self.client = aioxmpp.Client(
            jid,
            aioxmpp.make_security_layer(
                self.wizard().field("password"),
            ),
            logger=self.logger,
        )
        self.client.summon(aioxmpp.DiscoClient)

        self.user_logger.info("Trying to connect as %s", jid)

        async with self.client.connected():
            self.user_logger.info("Successfully connected!")

            self.ui.progress.setRange(
                0, len(self.optional_steps)*100
            )
            self.ui.progress.setValue(0)
            for i, step in enumerate(self.optional_steps):
                await step(i)
                self.ui.progress.setValue((i+1)*100)

            self.user_logger.info("Settings checked, done!")

        self._complete = True
        self.completeChanged.emit()

    def cleanupPage(self):
        super().cleanupPage()
        self._common_cleanup()

    def _common_cleanup(self):
        self.task.cancel()

    def validatePage(self):
        super().validatePage()
        self._common_cleanup()
        return True

    def isComplete(self):
        return self._complete


class DlgAddAccount(Qt.QWizard):
    def __init__(self, client, identities, parent=None):
        from ..ui import dlg_add_account
        super().__init__(parent)
        self._client = client
        self._identities = identities
        self.ui = dlg_add_account.Ui_DlgAddAccount()
        self.ui.setupUi(self)
        self.identities_model = models.AccountModel(
            self._identities._tree
        )

        self.ui.page_credentials._wizard = self
        self.ui.page_connecting._wizard = self

    def _reset_ui_state(self):
        self.restart()
        self.ui.page_credentials.reset_ui_state()
        self.ui.page_connecting.reset_ui_state()

    @asyncio.coroutine
    def run(self, default_identity=None):
        self._reset_ui_state()

        self.ui.page_credentials.ui.identity.clearEditText()
        if default_identity is not None:
            self.ui.page_credentials.ui.identity.setCurrentIndex(
                self.identities_model.node_to_index(
                    default_identity._node
                ).row()
            )
        else:
            if len(self._identities.identities) > 0:
                self.ui.page_credentials.ui.identity.setCurrentIndex(0)
            else:
                self.ui.page_credentials.ui.identity.setCurrentText("Default")

        result = yield from utils.exec_async(self)
        if not result:
            return

        selected_identity = self.ui.page_credentials.ui.identity.currentIndex()
        identity_name = self.ui.page_credentials.ui.identity.currentText()
        if selected_identity >= 0:
            identity = self._identities.identities[selected_identity]
            if identity.name != identity_name:
                selected_identity = -1

        if selected_identity < 0:
            # create new
            identity = self._identities.new_identity(
                identity_name,
            )

        jid = aioxmpp.JID.fromstr(self.field("jid"))
        self._identities.new_account(
            identity,
            jid,
            (0, 0, 0),
        )

        try:
            yield from self._client.set_stored_password(
                jid,
                self.field("password"),
            )
        except mlxc.client.PasswordStoreIsUnsafe:
            pass

        mlxc.config.config_manager.writeback()
