import asyncio

import jclib.client
import jclib.identity

from .dialogs import password_prompt


class Client(jclib.client.Client):
    @asyncio.coroutine
    def _invoke_password_dialog(self, jid):
        dlg = password_prompt.DlgPasswordPrompt(
            jid,
            can_store=self.keyring_is_safe
        )
        cont, password, store = yield from dlg.run()

        if store:
            try:
                yield from self.set_stored_password(jid, password)
            except jclib.client.PasswordStoreIsUnsafe:
                pass

        return password

    @asyncio.coroutine
    def get_password(self, jid, nattempt):
        result = yield from super().get_password(jid, nattempt)
        if result is None:
            return (yield from self._invoke_password_dialog(jid))
        return result

    # @asyncio.coroutine
    # def _decide_on_certificate(self, account, verifier):
    #     dlg = check_certificate.DlgCheckCertificate(account, verifier)
    #     accept, store = yield from dlg.run()
    #     if accept and store:
    #         self.pin_store.pin(account.jid.domain, verifier.leaf_x509)
    #     return accept
