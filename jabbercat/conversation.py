import asyncio
import functools
import html
import logging
import re
import urllib.parse

from datetime import datetime, timedelta

import aioxmpp.im.conversation
import aioxmpp.im.p2p
import aioxmpp.im.service
import aioxmpp.structs
import aioxmpp.xso

import jclib.archive
import jclib.conversation
import jclib.identity
import jclib.utils

from . import Qt, utils, models, avatar, emoji

from .ui import p2p_conversation


logger = logging.getLogger(__name__)


def _connect_and_store_token(tokens, signal, handler):
    tokens.append(
        (signal, signal.connect(handler))
    )


class MessageInfo(Qt.QTextBlockUserData):
    from_ = None


class MessageViewPageChannelObject(Qt.QObject):
    def __init__(self, logger, account_jid, conversation_jid, parent=None):
        super().__init__(parent)
        self.logger = logger
        self._font_family = ""
        self._font_size = ""
        self._account_jid = str(account_jid)
        self._conversation_jid = str(conversation_jid)
        self._html_fut = None

    on_ready = Qt.pyqtSignal([])
    on_message = Qt.pyqtSignal(['QVariantMap'])
    on_font_family_changed = Qt.pyqtSignal([str])
    on_avatar_changed = Qt.pyqtSignal(['QVariantMap'])
    on_marker = Qt.pyqtSignal(['QVariantMap'])
    on_request_html = Qt.pyqtSignal([])

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

    on_conversation_jid_changed = Qt.pyqtSignal([str])

    @Qt.pyqtProperty(str, notify=on_conversation_jid_changed)
    def conversation_jid(self):
        return self._conversation_jid

    @conversation_jid.setter
    def conversation_jid(self, value):
        self._conversation_jid = value
        self.on_conversation_jid_changed.emit(value)

    @Qt.pyqtSlot()
    def ready(self):
        self.logger.debug("web page called in ready!")
        self.on_ready.emit()

    @Qt.pyqtSlot(str)
    def push_html(self, html_str: str):
        self.logger.debug("push_html received")
        fut = self._html_fut
        if fut is None:
            self.logger.debug("unsolicited html push")
            return

        if fut.done():
            self.logger.debug("future already done")
            self._html_fut = None
            return

        fut.set_result(html_str)

    @asyncio.coroutine
    def request_html(self) -> str:
        if self._html_fut is not None:
            raise RuntimeError(
                "only one html request may be running at any time"
            )
        fut = asyncio.Future()
        self._html_fut = fut
        self.logger.debug("emitting HTML request")
        self.on_request_html.emit()
        try:
            return (yield from fut)
        except asyncio.CancelledError:
            if not fut.done():
                fut.cancel()
            raise


class MessageViewPage(Qt.QWebEnginePage):
    URL = Qt.QUrl("qrc:/html/conversation-template.html")

    def __init__(self, web_profile, logger, account_jid,
                 conversation_jid, parent=None):
        super().__init__(web_profile, parent)
        self._loaded = False
        self.logger = logger
        self.channel = MessageViewPageChannelObject(
            self.logger,
            account_jid,
            conversation_jid,
        )
        self._web_channel = Qt.QWebChannel()
        self._web_channel.registerObject("channel", self.channel)
        self.setWebChannel(self._web_channel,
                           Qt.QWebEngineScript.ApplicationWorld)
        self.setUrl(self.URL)
        self.loadFinished.connect(self._load_finished)
        self.fullScreenRequested.connect(self._full_screen_requested)
        self.logger.debug("page initialised")
        self.ready_event = asyncio.Event()
        self.channel.on_ready.connect(self.ready_event.set)

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
        if self._loaded:
            if ok:
                self.logger.warning(
                    "it appears the page has navigated away."
                    " this is highly suspicious!"
                )
            return
        self._loaded = True
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


YOUTUBE_FULL_RE = re.compile(
    r"https?://(www\.)?youtube(-nocookie)?\.com/watch\?"
    r"(?P<query>[^#]+)(#(?P<frag>.+))?",
    re.I
)

YOUTUBE_EMBED_RE = re.compile(
    r"https?://(www\.)?youtube(-nocookie)?\.com/embed/(?P<video_id>[^?#]+)"
    r"(\?(?P<query>[^#]+))?(#(?P<frag>.+))?",
    re.I
)

YOUTU_BE_RE = re.compile(
    r"https?://(www\.)?youtu\.be/(?P<video_id>[^?#]+)",
    re.I
)


def youtube_attachment(url):
    match = YOUTUBE_FULL_RE.match(url)
    if match is not None:
        data = match.groupdict()
        query_info = urllib.parse.parse_qs(data.get("query") or "")
        try:
            video_id = query_info.get("v", [])[0]
        except IndexError:
            return
    else:
        match = \
            YOUTUBE_EMBED_RE.match(url) or \
            YOUTU_BE_RE.match(url)
        if match is None:
            return

        data = match.groupdict()
        video_id = data["video_id"]

    return {
        "type": "frame",
        "frame": {
            "url": (
                "https://www.youtube-nocookie.com/"
                "embed/{video_id}".format(
                    video_id=video_id,
                )
            )
        }
    }


def url_to_attachment(url):
    return youtube_attachment(url) or None


def urls_to_attachments(urls):
    for url in urls:
        attachment = url_to_attachment(url)
        if attachment is not None:
            yield attachment


class ConversationView(Qt.QWidget):
    URL_RE = re.compile(
        r"([<\(\[\{{](?P<url_paren>{url})[>\)\]\}}]|(\W)(?P<url_nonword>{url})\3|\b(?P<url_name>{url})\b)".format(
            url=r"https?://\S+|xmpp:\S+",
        ),
        re.I,
    )

    def __init__(self,
                 conversation_node,
                 avatars: avatar.AvatarManager,
                 web_profile: Qt.QWebEngineProfile,
                 parent=None):
        super().__init__(parent=parent)
        self.logger = logging.getLogger(
            ".".join([__name__, type(self).__name__])
        )
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
                                       conversation_node.conversation_address,
                                       self.history_view)
        self._update_zoom_factor()
        self.history_view.setPage(self.history)
        self.history_view.setContextMenuPolicy(Qt.Qt.NoContextMenu)
        frame_layout.addWidget(self.history_view)

        self.ui.message_input.installEventFilter(self)

        # self.ui.history.setMaximumBlockCount(100)

        self.history.channel.on_ready.connect(
            self.handle_page_ready,
        )
        self._page_ready = False

        self.__most_recent_message_ts = None
        self.__most_recent_message_uid = None

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
        _connect_and_store_token(
            self.__node_tokens,
            self.__node.on_message,
            self.handle_live_message,
        )
        _connect_and_store_token(
            self.__node_tokens,
            self.__node.on_marker,
            self.handle_live_marker,
        )
        _connect_and_store_token(
            self.__node_tokens,
            avatars.on_avatar_changed,
            self.handle_avatar_change,
        )
        self.__conv_tokens = []
        self.__msgidmap = {}

        if self.__node.conversation is not None:
            self._ready()

    def _update_zoom_factor(self):
        self.history.setZoomFactor(1./self.devicePixelRatioF())

    def handle_page_ready(self):
        self._page_ready = True
        self.logger.debug("page called in ready, loading logs")
        start_at = datetime.utcnow() - timedelta(hours=2)
        max_count = 100
        for argv in self.__node.get_last_messages(max_count=max_count,
                                                  max_age=start_at):
            print(argv)
            self.handle_live_message(*argv)

    def showEvent(self, event: Qt.QShowEvent):
        self._update_zoom_factor()
        return super().showEvent(event)

    def _screen_changed(self):
        self._update_zoom_factor()

    def _ready(self):
        self.__conversation = self.__node.conversation

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

    def set_focus_to_message_input(self):
        self.ui.message_input.setFocus()

    @utils.asyncify
    @asyncio.coroutine
    def _send_message(self):
        body = self.ui.message_input.toPlainText()
        msg = aioxmpp.Message(type_="chat")
        msg.body[None] = body
        msg.xep0333_markable = True
        print(msg.xep0333_markable)
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

    def htmlify_body(self, body, display_name):
        out_lines = []
        lines = body.split("\n")
        urls = []
        for i, line in enumerate(lines):
            if (i == len(lines)-1 and
                    emoji.DATABASE.emoji_or_space_multi_re.fullmatch(line)):
                out_lines.append("<span class='emoji-hugify'>{}</span>".format(
                    line
                ))
                continue

            parts = []
            if line.startswith("/me "):
                parts.append("<span class='action'>* {}</span> ".format(
                    html.escape(display_name)
                ))
                line = line[3:]

            last = 0
            for match in self.URL_RE.finditer(line):
                prev = line[last:match.start()]
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
                urls.append(url)
                if suffix:
                    parts.append(html.escape(suffix))
                last = match.end()

            parts.append(html.escape(line[last:]))
            out_lines.append("".join(parts))

        return "<br/>".join(out_lines), (urls,)

    def make_css_colors(self, color_input):
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
            color_weak = (
                "linear-gradient(135deg, "
                "rgba({:d}, {:d}, {:d}, {}), "
                "transparent 10em)".format(
                    round(qtcolor.red()),
                    round(qtcolor.green()),
                    round(qtcolor.blue()),
                    light_factor,
                )
            )
        else:
            color_full = "inherit"
            color_weak = color_full

        return color_full, color_weak

    def handle_live_marker(self, timestamp, is_self, from_jid,
                           display_name, color_input, marked_message_uid):
        if not self._page_ready:
            self.logger.debug("dropping marker since page isn’t ready")
            return

        color_full, color_weak = self.make_css_colors(color_input)

        self.history.channel.on_marker.emit({
            "timestamp": str(
                timestamp.isoformat() + "Z"
            ),
            "from_self": is_self,
            "from_jid": str(from_jid or ""),
            "display_name": display_name,
            "marked_message_uid": str(marked_message_uid),
            "color_full": color_full,
            "color_weak": color_weak,
        })

    def handle_live_message(self, timestamp, message_uid, is_self, from_jid,
                            from_, color_input, message):
        if not self._page_ready:
            self.logger.debug("dropping message since page isn’t ready")
            return

        body_html, (urls,) = self.htmlify_body(message.body.any(),
                                               from_)
        color_full, color_weak = self.make_css_colors(color_input)

        attachments = []

        if message.xep0066_oob and message.xep0066_oob.url:
            oob_url = message.xep0066_oob.url
            if any(oob_url.endswith(x) for x in [".png", ".jpeg", ".jpg"]):
                attachments.append(
                    {
                        "type": "image",
                        "image": {"url": oob_url},
                    }
                )

        attachments.extend(urls_to_attachments(urls))

        data = {
            "timestamp": str(
                timestamp.isoformat() + "Z"
            ),
            "from_self": is_self,
            "from_jid": str(from_jid or ""),
            "display_name": from_,
            "body": body_html,
            "color_full": color_full,
            "color_weak": color_weak,
            "attachments": attachments,
            "message_uid": str(message_uid),
        }

        self.logger.debug("detected URLs: %s", urls)
        self.logger.debug("sending data to JS: %r", data)

        self.history.channel.on_message.emit(data)

        if (self.__most_recent_message_ts is None or
                timestamp >= self.__most_recent_message_ts):
            self.__most_recent_message_uid = message_uid
            self.__most_recent_message_ts = timestamp

            if self.isVisible() and self.window().isActiveWindow():
                self.__node.set_read_up_to(self.__most_recent_message_uid)
            Qt.QApplication.alert(self.window())

    def showEvent(self, event: Qt.QShowEvent):
        self.__node.set_read_up_to(self.__most_recent_message_uid)
        return super().showEvent(event)

    def event(self, event: Qt.QEvent):
        if event.type() == Qt.QEvent.WindowActivate:
            self.__node.set_read_up_to(self.__most_recent_message_uid)
        return super().event(event)

    def handle_avatar_change(self,
                             account: jclib.identity.Account,
                             address: aioxmpp.JID):
        if self.__node.account != account:
            return

        self.history.channel.on_avatar_changed.emit(
            {
                "address": str(address),
            }
        )
