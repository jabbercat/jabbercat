import asyncio
import functools
import html
import logging
import re

from datetime import datetime

import aioxmpp.im.conversation
import aioxmpp.im.p2p
import aioxmpp.im.service
import aioxmpp.structs

import jclib.conversation
import jclib.utils

from . import Qt, utils, models, avatar

from .ui import p2p_conversation


logger = logging.getLogger(__name__)


def _connect_and_store_token(tokens, signal, handler):
    tokens.append(
        (signal, signal.connect(handler))
    )


class MessageInfo(Qt.QTextBlockUserData):
    from_ = None


class MessageViewPageChannelObject(Qt.QObject):
    def __init__(self, logger, account_jid, parent=None):
        super().__init__(parent)
        self.logger = logger
        self._font_family = ""
        self._font_size = ""
        self._account_jid = str(account_jid)

    on_ready = Qt.pyqtSignal([])
    on_message = Qt.pyqtSignal(['QVariantMap'])
    on_font_family_changed = Qt.pyqtSignal([str])

    @Qt.pyqtProperty(str, notify=on_font_family_changed)
    def font_family(self):
        return self._font_family

    @font_family.setter
    def font_family(self, value):
        self._font_family = value
        self.on_font_family_changed.emit(value)

    on_font_size_changed = Qt.pyqtSignal([str])

    @Qt.pyqtProperty(str, notify=on_font_size_changed)
    def font_size(self):
        return self._font_size

    @font_size.setter
    def font_size(self, value):
        self._font_size = value
        self.on_font_size_changed.emit(value)

    on_account_jid_changed = Qt.pyqtSignal([str])

    @Qt.pyqtProperty(str, notify=on_account_jid_changed)
    def account_jid(self):
        return self._account_jid

    @account_jid.setter
    def account_jid(self, value):
        self._account_jid = value
        self.on_account_jid_changed.emit(value)

    @Qt.pyqtSlot()
    def ready(self):
        self.logger.debug("web page called in ready!")
        self.on_ready.emit()


class MessageViewPage(Qt.QWebEnginePage):
    URL = Qt.QUrl("qrc:/html/conversation-template.html")

    def __init__(self, web_profile, logger, account_jid, parent=None):
        super().__init__(web_profile, parent)
        self.logger = logger
        self.channel = MessageViewPageChannelObject(self.logger, account_jid)
        self._web_channel = Qt.QWebChannel()
        self._web_channel.registerObject("channel", self.channel)
        self.setWebChannel(self._web_channel,
                           Qt.QWebEngineScript.ApplicationWorld)
        self.setUrl(self.URL)
        self.loadFinished.connect(self._load_finished)
        self.fullScreenRequested.connect(self._full_screen_requested)
        self.logger.debug("page initialised")

    def acceptNavigationRequest(
            self,
            url: Qt.QUrl,
            type: Qt.QWebEnginePage.NavigationType,
            isMainFrame: bool) -> bool:
        if url == self.URL:
            return True
        if not isMainFrame:
            return True  # allow embedding things in frames
        Qt.QDesktopServices.openUrl(url)
        return False

    def _load_script(self, path: str):
        f = Qt.QFile(path)
        f.open(Qt.QFile.ReadOnly)
        assert f.isOpen()
        data = bytes(f.readAll()).decode("utf-8")
        self.runJavaScript(
            data,
            Qt.QWebEngineScript.ApplicationWorld
        )
        f.close()

    def _load_finished(self, ok: bool):
        # self._load_script(":/js/jquery.min.js")
        self._load_script(":/qtwebchannel/qwebchannel.js")
        self._load_script(":/js/jabbercat-api.js")

    def _full_screen_requested(self, request: Qt.QWebEngineFullScreenRequest):
        request.reject()

    def font_changed(self, font: Qt.QFont):
        self.channel.font_family = font.family()
        self.channel.font_size = "{}pt".format(font.pointSizeF())


class MessageView(Qt.QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.loadFinished.connect(self._load_finished)

    def _propagate_fonts(self):
        page = self.page()
        if isinstance(page, MessageViewPage):
            page.font_changed(self.font())

    def event(self, event: Qt.QEvent):
        if event.type() == Qt.QEvent.FontChange:
            self._propagate_fonts()
        return super().event(event)

    def _load_finished(self, ok):
        self._propagate_fonts()


class ConversationView(Qt.QWidget):
    URL_RE = re.compile(
        r"([<\(\[\{{](?P<url_paren>{url})[>\)\]\}}]|(\W)(?P<url_nonword>{url})\3|(?P<url_name>{url}))".format(
            url=r"https?://\S+|xmpp:\S+",
        ),
        re.I,
    )

    def __init__(self,
                 conversation_node,
                 web_profile: Qt.QWebEngineProfile,
                 parent=None):
        super().__init__(parent=parent)
        self.ui = p2p_conversation.Ui_P2PView()
        self.ui.setupUi(self)

        self.ui.title_label.setText(conversation_node.label)

        frame_layout = Qt.QHBoxLayout()
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.history_frame.setLayout(frame_layout)

        self.history_view = MessageView(self.ui.history_frame)
        self.history = MessageViewPage(web_profile,
                                       logging.getLogger(__name__),
                                       conversation_node.account.jid,
                                       self.history_view)
        self._update_zoom_factor()
        self.history_view.setPage(self.history)
        self.history_view.setContextMenuPolicy(Qt.Qt.NoContextMenu)
        frame_layout.addWidget(self.history_view)

        self.ui.message_input.installEventFilter(self)

        # self.ui.history.setMaximumBlockCount(100)

        self.__node = conversation_node
        self.__node_tokens = []
        _connect_and_store_token(
            self.__node_tokens,
            self.__node.on_ready,
            self._ready,
        )
        _connect_and_store_token(
            self.__node_tokens,
            self.__node.on_stale,
            self._stale,
        )
        self.__conv_tokens = []
        self.__msgidmap = {}

        if self.__node.conversation is not None:
            self._ready()

    def _update_zoom_factor(self):
        self.history.setZoomFactor(1./self.devicePixelRatioF())

    def showEvent(self, event: Qt.QShowEvent):
        self._update_zoom_factor()
        return super().showEvent(event)

    def _screen_changed(self):
        self._update_zoom_factor()

    def _ready(self):
        self.__conversation = self.__node.conversation
        _connect_and_store_token(
            self.__conv_tokens,
            self.__conversation.on_message,
            functools.partial(self.add_message),
        )

    def _stale(self):
        for signal, token in self.__conv_tokens:
            signal.disconnect(token)
        self.__conv_tokens.clear()
        self.__conversation = None

    def eventFilter(self, obj, ev):
        if obj is not self.ui.message_input:
            return False
        if ev.type() != Qt.QEvent.KeyPress:
            return False

        if ev.key() == Qt.Qt.Key_Return:
            if ev.modifiers() == Qt.Qt.NoModifier:
                if not self.ui.message_input.document().isEmpty():
                    self._send_message()
                return True

        return False

    @utils.asyncify
    @asyncio.coroutine
    def _send_message(self):
        body = self.ui.message_input.toPlainText()
        msg = aioxmpp.Message(type_="chat")
        msg.body[None] = body
        self.ui.message_input.clear()
        if (aioxmpp.im.conversation.ConversationFeature.SEND_MESSAGE_TRACKED
                in self.__conversation.features):
            print("using tracker")
            _, tracker = self.__conversation.send_message_tracked(msg)
            tracker.set_timeout(60)
            print("used tracker")
        else:
            print("tracking not supported")
            yield from self.__conversation.send_message(msg)

    def _message_frame_format(self):
        fmt = Qt.QTextFrameFormat()
        return fmt

    def add_message(self, message, member, source, tracker=None, **kwargs):
        if not message.body:
            return

        from_jid = None
        is_self = False

        if member is not None:
            from_jid = member.conversation_jid
            color_input = str(
                (member.direct_jid or member.conversation_jid).bare()
            )
            if member is self.__conversation.me:
                from_ = "me"
                is_self = True
            else:
                from_ = str(
                    (member.direct_jid or member.conversation_jid).bare()
                )

            if hasattr(member, "nick"):
                from_ = member.nick
                color_input = member.nick

        else:
            from_jid = None
            from_ = str(message.from_)
            color_input = None

        if color_input is not None:
            qtcolor = utils.text_to_qtcolor(
                jclib.utils.normalise_text_for_hash(color_input)
            )
            color_full = "rgba({:d}, {:d}, {:d}, 1.0)".format(
                round(qtcolor.red() * 0.8),
                round(qtcolor.green() * 0.8),
                round(qtcolor.blue() * 0.8),
            )
            light_factor = 0.1
            inv_light_factor = 1 - light_factor
            color_weak = "linear-gradient(135deg, rgba({:d}, {:d}, {:d}, {}), transparent 10em)".format(
                # round(qtcolor.red() * light_factor + 255 * inv_light_factor),
                # round(qtcolor.green() * light_factor + 255 * inv_light_factor),
                # round(qtcolor.blue() * light_factor + 255 * inv_light_factor),
                round(qtcolor.red()),
                round(qtcolor.green()),
                round(qtcolor.blue()),
                light_factor,
            )
        else:
            color_full = "inherit"
            color_weak = color_full

        body = message.body.lookup([
            aioxmpp.structs.LanguageRange.fromstr("*")
        ])

        parts = []
        last = 0
        for match in self.URL_RE.finditer(body):
            prev = body[last:match.start()]
            if prev:
                parts.append(html.escape(prev))

            info = match.groupdict()
            match_s = match.group(0)
            inner_prefix, prefix, inner_suffix, suffix = "", "", "", ""
            url = None
            if info["url_paren"]:
                inner_prefix = match_s[0]
                inner_suffix = match_s[-1]
                url = match_s[1:-1]
            elif info["url_nonword"]:
                prefix = match_s[0]
                suffix = match_s[-1]
                url = match_s[1:-1]
            elif info["url_name"]:
                url = match_s
            if prefix:
                parts.append(html.escape(prefix))
            parts.append("<a href='{0}'>{1}</a>".format(
                html.escape(url),
                html.escape(inner_prefix + url + inner_suffix),
            ))
            if suffix:
                parts.append(html.escape(suffix))
            last = match.end()

        parts.append(html.escape(body[last:]))

        body = "<br/>".join("".join(parts).split("\n"))

        self.history.channel.on_message.emit(
            {
                "timestamp": str(
                    datetime.utcnow().isoformat() + "Z"
                ),
                "from_self": is_self,
                "from_jid": str(from_jid or ""),
                "display_name": from_,
                "body": body,
                "color_full": color_full,
                "color_weak": color_weak,
            }
        )


# class ConversationsController(jclib.conversation.Conversations):
#     def __init__(self, identities, client):
#         super().__init__(identities, client)
#         self._conversation_views = {}
#         self.__view = None
#         self.__pages = None
#         self.model = models.ConversationsModel(self.tree)
#         self.on_conversation_node_created.connect(self._new_conversation)

#     @property
#     def pages(self):
#         return self.__pages

#     @pages.setter
#     def pages(self, widget):
#         self.__pages = widget

#     @property
#     def view(self):
#         return self.__view

#     @view.setter
#     def view(self, widget):
#         self.__view = widget
#         self.__view.setModel(self.model)
#         for identity_wrapper in self.tree.root:
#             self.__view.expand(
#                 self.model.node_to_index(
#                     identity_wrapper._node
#                 )
#             )

#     def _identity_added(self, identity):
#         super()._identity_added(identity)
#         if self.__view is not None:
#             self.__view.expand(
#                 self.model.node_to_index(
#                     self.tree.root[-1]._node
#                 )
#             )

#     def _new_conversation(self, wrapper):
#         conversation = wrapper.conversation
#         view = ConversationView(conversation)
#         self._conversation_views[conversation] = view
#         self.__pages.addWidget(view)
