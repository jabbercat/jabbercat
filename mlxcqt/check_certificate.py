import asyncio
import hashlib

import aioxmpp.security_layer

from . import Qt, utils
from .ui.dlg_check_certificate import Ui_dlg_check_certificate


def format_hash(hashbytes):
    return ":".join("{:02x}".format(byte) for byte in hashbytes)


class DlgCheckCertificate(Qt.QDialog, Ui_dlg_check_certificate):
    def __init__(self, account, verifier, **kwargs):
        super().__init__(**kwargs)
        self.setupUi(self)

        self.label_info.setText(
            Qt.translate(
                "dlg_check_certificate",
                "While connecting the account {account_jid}, the certificate of"
                " the server {peer_hostname} could not be verified. Below is the"
                " information MLXC is sure about:").format(
                    account_jid=account.jid,
                    peer_hostname="foobar"
                )
        )

        self.btn_continue.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.trust_always.setEnabled(False)

        self.cert_info_table.setRowCount(2)
        self.cert_info_table.setHorizontalHeaderLabels([
            Qt.translate("dlg_check_certificate", "Information"),
            Qt.translate("dlg_check_certificate", "Value"),
        ])

        blob = aioxmpp.security_layer.extract_blob(verifier.leaf_x509)

        for i, hashfun in enumerate(["sha1", "sha256"]):
            hashimpl = hashlib.new(hashfun)
            hashimpl.update(blob)
            self.cert_info_table.setItem(
                i, 0,
                Qt.QTableWidgetItem(Qt.translate(
                    "dlg_check_certificate",
                    "{hashfun} Fingerprint"
                ).format(
                    hashfun=hashfun
                ))
            )
            self.cert_info_table.setItem(
                i, 1,
                Qt.QTableWidgetItem(format_hash(hashimpl.digest()))
            )
        del hashimpl


    @asyncio.coroutine
    def _delayed_activation(self):
        yield from asyncio.sleep(3)
        self.btn_continue.setEnabled(True)
        self.btn_abort.setEnabled(True)
        self.trust_always.setEnabled(True)

    @asyncio.coroutine
    def run(self):
        delayed_activation = utils.asyncify(self._delayed_activation)()
        result = yield from utils.exec_async(self)
        if result == Qt.QDialog.Accepted:
            return True, self.trust_always.checkState() == Qt.Qt.Checked
        else:
            return False, False
