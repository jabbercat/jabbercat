import asyncio
import functools
import html
import logging
import re
import pathlib
import urllib.parse

from datetime import datetime, timedelta

import lxml.builder
import lxml.etree

import aioxmpp
import aioxmpp.forms
import aioxmpp.im.conversation
import aioxmpp.im.p2p
import aioxmpp.im.service
import aioxmpp.misc
import aioxmpp.structs
import aioxmpp.xso

import jclib.archive
import jclib.conversation
import jclib.httpupload
import jclib.identity
import jclib.instrumentable_list
import jclib.metadata
import jclib.roster
import jclib.utils

import jabbercat.avatar

from . import Qt, utils, models, avatar, emoji, model_adaptor
from .widgets import messageinput, member_list, forms

from .ui import p2p_conversation


logger = logging.getLogger(__name__)

# TODO move this somewhere
def contains_word(haystack: str, needle: str):
    return re.search(r"\b{}\b".format(re.escape(needle)), haystack, re.I)

def _connect_and_store_token(tokens, signal, handler, mode=None):
    tokens.append(
        (signal, signal.connect(handler, mode or signal.WEAK))
    )


class MemberList(jclib.instrumentable_list.ModelListView):
    def __init__(self):
        self._backend = jclib.instrumentable_list.ModelList()
        super().__init__(self._backend)
        self._conversation = None
        self._tokens = []

    def _connect(self):
        self._backend[:] = self._conversation.members
        if self._conversation.me is None:
            _connect_and_store_token(
                self._tokens,
                self._conversation.on_enter,
                self._on_enter,
            )
        else:
            _connect_and_store_token(
                self._tokens,
                self._conversation.on_join,
                self._on_join,
            )

        _connect_and_store_token(
            self._tokens,
            self._conversation.on_leave,
            self._on_leave,
        )

    def _disconnect(self):
        for signal, token in self._tokens:
            signal.disconnect(token)
        self._backend.clear()

    def _on_enter(self, **kwargs):
        self._backend[:] = self._conversation.members
        _connect_and_store_token(
            self._tokens,
            self._conversation.on_join,
            self._on_join,
        )

    def _on_join(self, member, **kwargs):
        self._backend.append(member)

    def _on_leave(self, member, **kwargs):
        self._backend.remove(member)

    def _on_nick_changed(self, member, old_nick, new_nickm, **kwargs):
        member_index = self._backend.index(member)
        self._backend.refresh_data(slice(member_index, member_index+1))

    @property
    def conversation(self):
        return self._conversation

    @conversation.setter
    def conversation(self, value):
        if self._conversation:
            self._disconnect()
        self._conversation = value
        if self._conversation:
            self._connect()


class MemberModel(Qt.QAbstractListModel):
    def __init__(self,
                 members: MemberList,
                 account: jclib.identity.Account,
                 metadata: jclib.metadata.MetadataFrontend,
                 avatar_manager: jabbercat.avatar.AvatarManager):
        super().__init__()
        self.__members = members
        self.__account = account
        self.__metadata = metadata
        self.__avatar_manager = avatar_manager
        self.__adaptor = model_adaptor.ModelListAdaptor(self.__members, self)

    def _display_name(self, member):
        if hasattr(member, "nick"):
            label = member.nick
        else:
            label = self.__metadata.get(
                jclib.roster.RosterMetadata.NAME,
                self.__account,
                member.direct_jid or member.conversation_jid,
            )
        return label

    def _format_tooltip(self, member):
        picture = self.__avatar_manager.get_avatar(
            self.__account,
            member.direct_jid or member.conversation_jid,
            getattr(member, "nick", None)
        )

        picture_base64 = jabbercat.utils.qtpicture_to_data_uri(picture)

        label = self._display_name(member)

        H = lxml.builder.ElementMaker()

        avatar = H.img(width="48", height="48", src=picture_base64)

        parts = []
        parts.append(H.h3(label))

        dl_parts = []
        if member.conversation_jid:
            dl_parts.append(H.dt(
                Qt.translate("conversation.MemberModel.Tooltip",
                             "Conversation JID")
            ))
            dl_parts.append(H.dd(
                str(member.conversation_jid)
            ))

        if member.direct_jid:
            dl_parts.append(H.dt(
                Qt.translate("conversation.MemberModel.Tooltip",
                             "Direct JID")
            ))
            dl_parts.append(H.dd(
                str(member.direct_jid)
            ))

        if member.affiliation is not None:
            dl_parts.append(H.dt(
                Qt.translate("conversation.MemberModel.Tooltip",
                             "Affiliation")
            ))
            dl_parts.append(H.dd(
                str(member.affiliation)
            ))

        parts.append(H.dl(*dl_parts))
        res = H.table(H.tr(H.td(avatar), H.td(*parts)))

        return lxml.etree.tounicode(res, method="html")

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self.__members)

    def data(self,
             index: Qt.QModelIndex,
             role: Qt.Qt.ItemDataRole=Qt.Qt.DisplayRole):
        if not index.isValid():
            return

        member = self.__members[index.row()]

        if role == Qt.Qt.DisplayRole:
            return self._display_name(member)
        elif role == Qt.Qt.ToolTipRole:
            return self._format_tooltip(member)
        elif role == models.ROLE_OBJECT:
            return member


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
    on_join = Qt.pyqtSignal(['QVariantMap'])
    on_part = Qt.pyqtSignal(['QVariantMap'])
    on_flag = Qt.pyqtSignal(['QVariantMap'])
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
    r"https?://((www|m)\.)?youtube(-nocookie)?\.com/watch\?"
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


class MUCConfigurationDialog(forms.FormDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowModality(Qt.Qt.NonModal)
        self.buttons.addButton(Qt.QDialogButtonBox.Save)
        self.buttons.addButton(Qt.QDialogButtonBox.Cancel)

    async def _fetch_room_config(self, muc_client, address):
        jclib.tasks.manager.update_text(
            "Fetching configuration of {}".format(address)
        )
        return (await muc_client.get_room_config(address))

    async def _set_room_config(self, muc_client, address, config):
        jclib.tasks.manager.update_text(
            "Setting configuration of {}".format(address)
        )
        await muc_client.set_room_config(address, config)

    @utils.asyncify_blocking
    async def done(self, r: int):
        if r != Qt.QDialog.Accepted:
            return super().done(r)

        self._config.type_ = aioxmpp.forms.DataType.SUBMIT
        try:
            await jclib.tasks.manager.start(self._set_room_config(
                self._muc_client,
                self._address,
                self._config
            )).asyncio_task
        except aioxmpp.errors.XMPPError as exc:
            box = Qt.QMessageBox(
                Qt.QMessageBox.Critical,
                "Error",
                str(exc),
                Qt.QMessageBox.Ok,
                self,

            )
            box.setWindowModality(Qt.Qt.WindowModal)
            box.setAttribute(Qt.Qt.WA_DeleteOnClose)
            box.show()
        else:
            return super().done(r)

    async def run(self, muc_client, address: aioxmpp.JID):
        self._muc_client = muc_client
        self._address = address
        self._config = await jclib.tasks.manager.start(self._fetch_room_config(
            self._muc_client,
            self._address,
        )).asyncio_task

        return (await super().run(self._config))


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
                 metadata: jclib.metadata.MetadataFrontend,
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
        self.__web_profile = web_profile

        self.ui.message_input.activated.connect(self._message_input_activated)

        self.__metadata = metadata

        self.__member_list = MemberList()
        self.__member_model = MemberModel(
            self.__member_list,
            conversation_node.account,
            metadata,
            avatars,
        )

        self.__sorted_member_model = Qt.QSortFilterProxyModel()
        self.__sorted_member_model.setSortRole(Qt.Qt.DisplayRole)
        self.__sorted_member_model.setSortCaseSensitivity(Qt.Qt.CaseInsensitive)
        self.__sorted_member_model.setSourceModel(self.__member_model)
        self.__sorted_member_model.sort(0, Qt.Qt.AscendingOrder)

        self.ui.member_view.setModel(self.__sorted_member_model)

        self._ui_initialised = False

        if isinstance(conversation_node,
                      jclib.conversation.P2PConversationNode):
            # this is a single-user thing
            self.ui.member_view.hide()
        else:
            # this is a multi-user thing
            completer = messageinput.MemberCompleter()
            completer.setModel(self.__sorted_member_model)
            completer.setCompletionRole(Qt.Qt.DisplayRole)
            completer.setCompletionColumn(0)
            self.ui.message_input.completer = completer

            item_delegate_wide = member_list.MemberItemDelegate(
                avatars,
                conversation_node.account,
                metadata,
                completer,
                compact=False,
            )
            completer.popup().setItemDelegate(item_delegate_wide)

            item_delegate_compact = member_list.MemberItemDelegate(
                avatars,
                conversation_node.account,
                metadata,
                self.ui.member_view,
                compact=True,
            )
            self.ui.member_view.setItemDelegate(item_delegate_compact)

            self.ui.splitter.setCollapsible(0, False)
            self.ui.splitter.setCollapsible(1, True)

            self.addAction(self.ui.action_configure_room)
            self.ui.action_configure_room.triggered.connect(
                self._configure_room
            )

        # self.ui.history.setMaximumBlockCount(100)

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

        self.ui.btnSendFile.setDefaultAction(self.ui.action_send_file)
        self.ui.action_send_file.triggered.connect(
            self._send_file_triggered,
        )

        self.create_view()
        if self.__node.conversation is not None:
            self._ready()

        metadata.changed_signal(
            jclib.metadata.ServiceMetadata.HTTP_UPLOAD_ADDRESS
        ).connect(
            self._http_upload_address_changed,
            aioxmpp.callbacks.AdHocSignal.WEAK
        )
        self._http_upload_address_changed(
            None, self.__node.account, None,
            metadata.get(
                jclib.metadata.ServiceMetadata.HTTP_UPLOAD_ADDRESS,
                self.__node.account,
                None,
            )
        )

    def _http_upload_address_changed(self, key, account, peer, address):
        if account is not self.__node.account:
            return

        self.ui.action_send_file.setEnabled(
            address is not None and self.__conversation is not None
        )

    def _send_file_triggered(self, *args):
        file_names, _ = Qt.QFileDialog.getOpenFileNames(
            self
        )

        http_upload_address = self.__metadata.get(
            jclib.metadata.ServiceMetadata.HTTP_UPLOAD_ADDRESS,
            self.__node.account,
            None)

        if http_upload_address is None:
            # TODO: show proper error here
            return

        for name in file_names:
            jclib.tasks.manager.start(self._upload_and_send(
                http_upload_address,
                pathlib.Path(name),
            ))

    async def _upload_and_send(self,
                               service: aioxmpp.JID,
                               path: pathlib.Path):
        jclib.tasks.manager.update_text("Analysing {}".format(path.name))
        content_type = await jclib.httpupload.guess_mime_type(path)
        content_type = content_type or "application/octet-stream"

        jclib.tasks.manager.update_text("Uploading {}".format(path.name))
        # TODO: determine proper MIME type
        get_url = await jclib.httpupload.upload_file(
            self.__node.account.client,
            service,
            path,
            content_type=content_type,
        )
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.CHAT
        )
        msg.body[None] = get_url
        msg.xep0066_oob = aioxmpp.misc.OOBExtension()
        msg.xep0066_oob.url = get_url

        await self._send_message_stanza(msg)

    @utils.asyncify
    async def _configure_room(self, _):
        muc_client = self.__conversation.service

        dialog = MUCConfigurationDialog(self)
        await dialog.run(muc_client, self.__conversation.jid)
        dialog.deleteLater()
        del dialog

    def create_view(self):
        self.history_view = MessageView(self.ui.history_frame)
        self.history = MessageViewPage(self.__web_profile,
                                       logging.getLogger(__name__),
                                       self.__node.account.jid,
                                       self.__node.conversation_address,
                                       self.history_view)
        self.history.channel.on_ready.connect(
            self.handle_page_ready,
        )
        self._update_zoom_factor()
        self.history_view.setPage(self.history)
        self.history_view.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self.history_view.customContextMenuRequested.connect(
            self._history_view_context_menu
        )
        self.ui.history_frame.layout().addWidget(self.history_view)

    def _history_view_context_menu(self, pos):
        cmd = self.history.contextMenuData()
        media_type = cmd.mediaType()

        menu = Qt.QMenu(self.history_view)
        menu.addAction(
            self.history_view.pageAction(Qt.QWebEnginePage.SelectAll)
        )

        if cmd.selectedText():
            menu.addAction(
                self.history_view.pageAction(Qt.QWebEnginePage.Copy)
            )
            menu.addAction(
                self.history_view.pageAction(Qt.QWebEnginePage.Unselect)
            )

        if not cmd.linkUrl().isEmpty():
            menu.addAction(self.history_view.pageAction(
                Qt.QWebEnginePage.CopyLinkToClipboard
            ))

        if media_type == Qt.QWebEngineContextMenuData.MediaTypeImage:
            menu.addAction(self.history_view.pageAction(
                Qt.QWebEnginePage.CopyImageUrlToClipboard
            ))

        if media_type in (Qt.QWebEngineContextMenuData.MediaTypeVideo,
                          Qt.QWebEngineContextMenuData.MediaTypeAudio):
            menu.addAction(self.history_view.pageAction(
                Qt.QWebEnginePage.ToggleMediaPlayPause
            ))
            menu.addAction(self.history_view.pageAction(
                Qt.QWebEnginePage.ToggleMediaControls
            ))
            menu.addAction(self.history_view.pageAction(
                Qt.QWebEnginePage.ToggleMediaMute
            ))

        menu.popup(self.history_view.mapToGlobal(pos))
        menu.aboutToHide.connect(menu.deleteLater)

    def _update_zoom_factor(self):
        self.history.setZoomFactor(1./self.devicePixelRatioF())

    def handle_page_ready(self):
        self._page_ready = True
        self.logger.debug("page called in ready, loading logs")
        start_at = datetime.utcnow() - timedelta(hours=2)
        max_count = 100
        for argv in self.__node.get_last_messages(max_count=max_count,
                                                  max_age=start_at):
            self.handle_live_message(*argv)

    def showEvent(self, event: Qt.QShowEvent):
        self._update_zoom_factor()
        super().showEvent(event)

    def resizeEvent(self, event: Qt.QResizeEvent):
        super().resizeEvent(event)
        if not self._ui_initialised:
            width = self.width()
            if width < 200:
                return
            self._ui_initialised = True
            if self.ui.member_view.isVisibleTo(self):
                self.logger.debug("setting sizes!")
                sizes = self.ui.splitter.sizes()
                sizes[0] = self.width() - 150
                sizes[1] = 150
                self.ui.splitter.setSizes(sizes)

    def _screen_changed(self):
        self._update_zoom_factor()

    def _ready(self):
        self.__conversation = self.__node.conversation
        self.__member_list.conversation = self.__conversation
        _connect_and_store_token(
            self.__conv_tokens,
            self.__conversation.on_join,
            self._conv_join,
        )
        _connect_and_store_token(
            self.__conv_tokens,
            self.__conversation.on_leave,
            self._conv_leave,
        )
        http_upload_address = self.__metadata.get(
            jclib.metadata.ServiceMetadata.HTTP_UPLOAD_ADDRESS,
            self.__node.account,
            None)
        self.ui.action_send_file.setEnabled(http_upload_address is not None)
        self.ui.action_configure_room.setEnabled(True)

    def _stale(self):
        for signal, token in self.__conv_tokens:
            signal.disconnect(token)
        self.__conv_tokens.clear()
        self.__conversation = None
        self.__member_list.conversation = None
        self.ui.action_send_file.setEnabled(False)
        self.ui.action_configure_room.setEnabled(False)

    def _member_to_event(self, member, **kwargs):
        color_full, color_weak = self.make_css_colors(
            jclib.archive.get_member_colour_input(member),
        )
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "from_self": member.is_self,
            "from_jid": str(jclib.archive.get_member_from_jid(member)),
            "display_name": jclib.archive.get_member_display_name(member),
            "color_full": color_full,
            "color_weak": color_weak,
        }

    def _conv_join(self, member, **kwargs):
        state = getattr(
            self.__conversation,
            "muc_state",
            aioxmpp.muc.RoomState.ACTIVE
        )
        if state == aioxmpp.muc.RoomState.JOIN_PRESENCE:
            # we don’t show join presence in the message view
            return
        self.history.channel.on_join.emit(
            self._member_to_event(member)
        )

    def _conv_leave(self, member, **kwargs):
        self.history.channel.on_part.emit(
            self._member_to_event(member)
        )

    def _message_input_activated(self):
        if not self.ui.message_input.document().isEmpty():
            self._send_message()

    def set_focus_to_message_input(self):
        self.ui.message_input.setFocus()

    @asyncio.coroutine
    def _send_message_stanza(self, st):
        if (aioxmpp.im.conversation.ConversationFeature.SEND_MESSAGE_TRACKED
                in self.__conversation.features):
            _, tracker = self.__conversation.send_message_tracked(st)
            tracker.set_timeout(60)
        else:
            yield from self.__conversation.send_message(st)

    @utils.asyncify
    @asyncio.coroutine
    def _send_message(self):
        body = self.ui.message_input.toPlainText()
        msg = aioxmpp.Message(type_=aioxmpp.MessageType.CHAT)
        msg.body[None] = body
        msg.xep0333_markable = True
        url_match = self.URL_RE.match(body)
        if url_match is not None:
            info = url_match.groupdict()
            url = info.get(
                "url_name",
                info.get(
                    "url_nonword",
                    info.get("url_paren")
                )
            )
            if url:
                msg.xep0066_oob = aioxmpp.misc.OOBExtension()
                msg.xep0066_oob.url = url

        self.ui.message_input.clear()
        yield from self._send_message_stanza(msg)

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
                            from_, color_input, message, tracker=None):
        if (self.__most_recent_message_ts is None or
                timestamp >= self.__most_recent_message_ts):
            self.__most_recent_message_uid = message_uid
            self.__most_recent_message_ts = timestamp

            if (self.isVisible() and
                    self.window().isActiveWindow() and
                    self._page_ready) or is_self:
                self.__node.set_read_up_to(self.__most_recent_message_uid)

            nickname = self.__conversation.me.nick
            if not is_self and contains_word(message.body.any(), nickname):
                Qt.QApplication.alert(self.window())

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

        if tracker is not None:
            self._emit_tracker_event(message_uid, tracker.state)
            if not tracker.closed:
                tracker.on_state_changed.connect(
                    functools.partial(
                        self._on_tracker_state_changed,
                        message_uid,
                    )
                )

    def _on_tracker_state_changed(self, message_uid, new_state, response):
        if not self._page_ready:
            return

        self._emit_tracker_event(message_uid, new_state, response=response)

    def _emit_tracker_event(self, message_uid, new_state, response=None):
        try:
            state_name = {
                aioxmpp.tracking.MessageState.DELIVERED_TO_SERVER:
                    "DELIVERED_TO_SERVER",
                aioxmpp.tracking.MessageState.DELIVERED_TO_RECIPIENT:
                    "DELIVERED_TO_RECIPIENT",
                aioxmpp.tracking.MessageState.ERROR:
                    "ERROR",
            }[new_state]
        except KeyError:
            self.logger.debug("unhandled tracker state: %s", new_state)
            return

        if (new_state == aioxmpp.tracking.MessageState.ERROR and
                response is not None):
            # FIXME: use more human-readable names instead of RFC 6120 tags
            if response.error.text is not None:
                message = "{}: {}".format(
                    response.error.condition[1],
                    response.text
                )
            else:
                message = response.error.condition[1]
        else:
            message = None

        self.logger.debug("forwarding flag to view: message_uid=%r, flag=%s",
                          message_uid,
                          state_name)
        self.history.channel.on_flag.emit(
            {
                "flagged_message_uid": str(message_uid),
                "flag": state_name,
                "message": message,
            }
        )

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
