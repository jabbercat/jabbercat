import functools
import logging
import urllib.parse

import jclib.identity

import aioxmpp

from . import Qt, avatar, utils


logger = logging.getLogger(__name__)


class AvatarURLSchemeHandler(Qt.QWebEngineUrlSchemeHandler):
    def __init__(self,
                 accounts: jclib.identity.Accounts,
                 avatar_manager: avatar.AvatarManager,
                 parent: Qt.QObject = None) -> None:
        super().__init__(parent)
        self._accounts = accounts
        self._avatar_manager = avatar_manager
        self._buffers = set()

    def buffer_closing(self, buf):
        self._buffers.discard(buf)
        buf.deleteLater()

    @utils.asyncify
    async def requestStarted(self, request: Qt.QWebEngineUrlRequestJob):
        url = request.requestUrl()
        logger.debug("avatar request for %s: host=%r, path=%r",
                     url,
                     url.host(),
                     url.path())

        if url.path() != "/" or url.host() != "":
            logger.debug("invalid host or path")
            request.fail(Qt.QWebEngineUrlRequestJob.UrlNotFound)
            return

        args = urllib.parse.parse_qs(url.query())
        if "account" not in args or "peer" not in args:
            request.fail(Qt.QWebEngineUrlRequestJob.UrlInvalid)
            return

        try:
            account_s, = args["account"]
            account_address = aioxmpp.JID.fromstr(account_s)
            peer_s, = args["peer"]
            peer = aioxmpp.JID.fromstr(peer_s)
        except ValueError:
            request.fail(Qt.QWebEngineUrlRequestJob.UrlInvalid)
            return

        try:
            nickname, = args["nick"]
        except (KeyError, ValueError):
            nickname = None

        try:
            account = self._accounts.lookup_jid(account_address)
        except KeyError:
            logger.debug("could not find account: %r", account_address)
            request.fail(Qt.QWebEngineUrlRequestJob.UrlNotFound)
            return

        picture = self._avatar_manager.get_avatar(account, peer, nickname)
        canvas = Qt.QImage(48, 48, Qt.QImage.Format_ARGB32_Premultiplied)
        canvas.fill(0)
        painter = Qt.QPainter(canvas)
        painter.drawPicture(0, 0, picture)
        painter.end()

        buffer_ = Qt.QBuffer()
        buffer_.open(Qt.QIODevice.WriteOnly)
        assert buffer_.isOpen()
        assert buffer_.isWritable()
        canvas.save(buffer_, "PNG")
        buffer_.close()

        buffer_.open(Qt.QIODevice.ReadOnly)
        assert buffer_.isOpen()
        assert buffer_.isReadable()
        logger.debug("replying with %d bytes of PNG for %s via account %s",
                     buffer_.size(),
                     peer,
                     account_address)

        request.reply(b"image/png", buffer_)

        buffer_.aboutToClose.connect(
            functools.partial(
                self.buffer_closing,
                buffer_,
            )
        )

        self._buffers.add(buffer_)
