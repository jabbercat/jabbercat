import asyncio
import logging
import unittest
import unittest.mock

import lxml.etree as etree

import aioxmpp

from aioxmpp.testutils import (
    run_coroutine,
)
from aioxmpp.xmltestutils import (
    XMLTestCase,
)

import jabbercat.Qt as Qt

import jabbercat.conversation as conversation


class TestMessageViewPage(XMLTestCase):
    def setUp(self):
        self.logger = unittest.mock.Mock(spec=logging.Logger)
        self.profile = Qt.QWebEngineProfile()
        self.account_jid = aioxmpp.JID.fromstr("juliet@capulet.lit")
        self.conversation_jid = aioxmpp.JID.fromstr("romeo@montague.lit")
        self.page = conversation.MessageViewPage(
            self.profile,
            logging.getLogger(
                ".".join([__name__, type(self).__qualname__])
            ),
            self.account_jid,
            self.conversation_jid,
        )
        run_coroutine(self.page.ready_event.wait())

    def tearDown(self):
        del self.profile
        del self.page

    @asyncio.coroutine
    def _obtain_html(self):
        html_str = yield from self.page.channel.request_html()
        return etree.fromstring(html_str)

    def test_basic_html(self):
        self.assertSubtreeEqual(
            run_coroutine(self._obtain_html(), timeout=20),
            etree.fromstring("""<div id="messages"/>"""),
            ignore_surplus_attr=True,
        )
