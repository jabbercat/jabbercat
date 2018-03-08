import asyncio
import logging
import unittest
import unittest.mock

from datetime import datetime

import lxml.html.html5parser
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
        return lxml.html.html5parser.fromstring(html_str)

    def test_basic_html(self):
        self.assertSubtreeEqual(
            run_coroutine(self._obtain_html(), timeout=20),
            etree.fromstring(
                """<div xmlns="http://www.w3.org/1999/xhtml" id="messages"/>"""
            ),
            ignore_surplus_attr=True,
        )

    def test_add_message(self):
        self.page.channel.on_message.emit(
            {
                "timestamp": datetime(2018, 3, 8, 11, 16, 10).isoformat() + "Z",
                "from_self": False,
                "from_jid": "romeo@montague.lit",
                "display_name": "Romeo Montague",
                "color_full": "#123456",
                "color_weak": "#123",
                "attachments": [],
                "body": "<em>test</em>",
                "message_uid": "message-1"
            }
        )
        self.assertSubtreeEqual(
            etree.fromstring(
                '<div xmlns="http://www.w3.org/1999/xhtml" id="messages">'
                '<div class="message-block">'
                '<div class="avatar"><img/></div>'
                '<div class="from">Romeo Montague</div>'
                '<div class="message-block-messages">'
                '<div class="message">'
                '<div class="timestamp">3/8/2018, 11:16:10 AM</div>'
                '<div class="body"><div><em>test</em></div></div>'
                '</div>'
                '</div>'
                '<div class="clearfix"></div>'
                '</div>'
                '</div>'
            ),
            run_coroutine(self._obtain_html(), timeout=20),
            ignore_surplus_attr=True,
        )

    def test_fancy_time_formatting_on_subsequent_messages(self):
        self.page.channel.on_message.emit(
            {
                "timestamp": datetime(2018, 3, 8, 11, 16, 10).isoformat() + "Z",
                "from_self": False,
                "from_jid": "romeo@montague.lit",
                "display_name": "Romeo Montague",
                "color_full": "#123456",
                "color_weak": "#123",
                "attachments": [],
                "body": "<em>foo</em>",
                "message_uid": "message-1"
            }
        )
        self.page.channel.on_message.emit(
            {
                "timestamp": datetime(2018, 3, 8, 11, 16, 15).isoformat() + "Z",
                "from_self": False,
                "from_jid": "romeo@montague.lit",
                "display_name": "Romeo Montague",
                "color_full": "#123456",
                "color_weak": "#123",
                "attachments": [],
                "body": "<em>bar</em>",
                "message_uid": "message-2"
            }
        )
        self.assertSubtreeEqual(
            etree.fromstring(
                '<div xmlns="http://www.w3.org/1999/xhtml" id="messages">'
                '<div class="message-block">'
                '<div class="avatar"><img/></div>'
                '<div class="from">Romeo Montague</div>'
                '<div class="message-block-messages">'
                '<div class="message">'
                '<div class="timestamp">3/8/2018, 11:16:10 AM</div>'
                '<div class="body"><div><em>foo</em></div></div>'
                '</div>'
                '<div class="message">'
                '<div class="timestamp">'
                '<span class="visual-hidden">11:16</span><span>:15</span>'
                '</div>'
                '<div class="body"><div><em>bar</em></div></div>'
                '</div>'
                '</div>'
                '<div class="clearfix"></div>'
                '</div>'
                '</div>'
            ),
            run_coroutine(self._obtain_html(), timeout=20),
            ignore_surplus_attr=True,
        )

    def test_new_block_on_from_jid_change(self):
        self.page.channel.on_message.emit(
            {
                "timestamp": datetime(2018, 3, 8, 11, 16, 10).isoformat() + "Z",
                "from_self": False,
                "from_jid": "romeo@montague.lit",
                "display_name": "Romeo Montague",
                "color_full": "#123456",
                "color_weak": "#123",
                "attachments": [],
                "body": "<em>foo</em>",
                "message_uid": "message-1"
            }
        )
        self.page.channel.on_message.emit(
            {
                "timestamp": datetime(2018, 3, 8, 11, 16, 15).isoformat() + "Z",
                "from_self": False,
                "from_jid": "romeo@montague.litX",
                "display_name": "Romeo Montague",
                "color_full": "#123456",
                "color_weak": "#123",
                "attachments": [],
                "body": "<em>bar</em>",
                "message_uid": "message-2"
            }
        )
        self.assertSubtreeEqual(
            etree.fromstring(
                '<div xmlns="http://www.w3.org/1999/xhtml" id="messages">'
                '<div class="message-block">'
                '<div class="avatar"><img/></div>'
                '<div class="from">Romeo Montague</div>'
                '<div class="message-block-messages">'
                '<div class="message">'
                '<div class="timestamp">3/8/2018, 11:16:10 AM</div>'
                '<div class="body"><div><em>foo</em></div></div>'
                '</div>'
                '</div>'
                '<div class="clearfix"></div>'
                '</div>'
                '<div class="message-block">'
                '<div class="avatar"><img/></div>'
                '<div class="from">Romeo Montague</div>'
                '<div class="message-block-messages">'
                '<div class="message">'
                '<div class="timestamp">'
                '<span class="visual-hidden"></span><span>11:16:15</span>'
                '</div>'
                '<div class="body"><div><em>bar</em></div></div>'
                '</div>'
                '</div>'
                '<div class="clearfix"></div>'
                '</div>'
                '</div>'
            ),
            run_coroutine(self._obtain_html(), timeout=20),
            ignore_surplus_attr=True,
        )
