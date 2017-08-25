import asyncio
import logging
import uuid

import aioxmpp

from .. import Qt, utils

from ..ui import (
    dlg_add_account_page_credentials,
    dlg_add_account_page_connecting,
)


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

    def _expert_options_switch_changed(self, new_state):
        if new_state == Qt.Qt.Checked:
            self.ui.expert_options.show()
        else:
            self.ui.expert_options.hide()

    def reset_ui_state(self):
        self.ui.expert_options_switch.setCheckState(
            Qt.Qt.Unchecked
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
