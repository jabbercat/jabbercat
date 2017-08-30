import abc
import asyncio
import functools
import typing
import unicodedata

import aioxmpp

import mlxc.client
import mlxc.identity
import mlxc.storage
import mlxc.utils

import mlxcqt.utils

from . import Qt


BASE_SIZE = 48


def _connect(tokens, signal, cb):
    tokens.append((signal, signal.connect(cb)))


def _disconnect_all(tokens):
    for signal, token in tokens:
        signal.disconnect(token)
    tokens.clear()


def first_grapheme(s):
    """
    Return the unicode codepoints resembling the first grapheme in `s`.
    """
    boundary_finder = Qt.QTextBoundaryFinder(
        Qt.QTextBoundaryFinder.Grapheme,
        s,
    )
    boundary = boundary_finder.toNextBoundary()
    return s[:boundary]


def render_dummy_avatar_base(painter: Qt.QPainter,
                             colour: Qt.QColor,
                             size: float):
    pen_colour = Qt.QColor(colour)
    pen_colour.setAlpha(127)
    painter.setPen(Qt.QPen(pen_colour))
    painter.setBrush(colour)
    painter.drawRect(
        Qt.QRectF(
            0, 0,
            size, size,
        )
    )


def render_dummy_avatar_grapheme(painter: Qt.QPainter,
                                 grapheme: str,
                                 base_font: Qt.QFont,
                                 size: float):
    PADDING = 2

    painter.setRenderHint(Qt.QPainter.Antialiasing, True)
    painter.setPen(Qt.QPen(Qt.QColor(255, 255, 255, 255)))
    painter.setBrush(Qt.QBrush())

    font = Qt.QFont(base_font)
    font.setPixelSize(size * 0.85 - 2 * PADDING)
    font.setWeight(Qt.QFont.Thin)

    painter.setFont(font)
    painter.drawText(
        Qt.QRectF(
            PADDING, PADDING,
            size - PADDING * 2,
            size - PADDING * 2,
        ),
        Qt.Qt.AlignHCenter | Qt.Qt.AlignVCenter | Qt.Qt.TextSingleLine,
        grapheme,
    )


def render_dummy_avatar(font: Qt.QFont, name: str, size: float):
    colour = mlxcqt.utils.text_to_qtcolor(
        mlxc.utils.normalise_text_for_hash(name)
    )
    grapheme = first_grapheme(name)
    picture = Qt.QPicture()
    painter = Qt.QPainter(picture)
    render_dummy_avatar_base(painter, colour, size)
    render_dummy_avatar_grapheme(painter, grapheme, font, size)
    return picture


class XMPPAvatarProvider:
    """
    .. signal:: on_avatar_changed(address)

        Emits when the avatar of a peer has changed.

        The image needs to be fetched separately and explicitly.

    """

    on_avatar_changed = aioxmpp.callbacks.Signal()

    def __init__(self, account: mlxc.identity.Account):
        super().__init__()
        self.__tokens = []
        self._account = account
        self._avatar_svc = None

    def __connect(self, signal, handler):
        _connect(self.__tokens, signal, handler)

    def __disconnect_all(self):
        _disconnect_all(self.__tokens)

    def prepare_client(self, client: aioxmpp.Client):
        svc = client.summon(aioxmpp.AvatarService)
        self.__connect(svc.on_metadata_changed, self._on_metadata_changed)
        self._avatar_svc = svc

    def shutdown_client(self, client: aioxmpp.Client):
        self.__disconnect_all()
        self._avatar_svc = None

    def _on_metadata_changed(self, jid, metadata):
        self.on_avatar_changed(jid)

    @asyncio.coroutine
    def _get_image_bytes(self, address: aioxmpp.JID) -> typing.Optional[bytes]:
        metadata = yield from self._avatar_svc.get_avatar_metadata(address)
        for descriptor in metadata:
            if not descriptor.has_image_data_in_pubsub:
                continue
            if descriptor.mime_type != "image/png":
                continue
            try:
                return (yield from descriptor.get_image_bytes())
            except (NotImplementedError, RuntimeError):
                pass

    @asyncio.coroutine
    def fetch_avatar(self, address: aioxmpp.JID) \
            -> typing.Optional[Qt.QPicture]:
        """
        Fetch an avatar and wrap it in a QPicture.
        """
        data = yield from self._get_image_bytes(address)
        if data is None:
            return None

        image = Qt.QImage.fromData(data, "PNG")
        picture = Qt.QPicture()
        painter = Qt.QPainter(picture)
        painter.drawImage(
            Qt.QRectF(0, 0, BASE_SIZE, BASE_SIZE),
            image,
        )
        painter.end()
        return picture


class RosterNameAvatarProvider:
    """
    Generate avatar images based on roster names or JIDs.
    """

    on_avatar_changed = aioxmpp.callbacks.Signal()

    def __init__(self):
        super().__init__()
        self.__tokens = []
        self._roster_svc = None

    def __connect(self, signal, handler):
        _connect(self.__tokens, signal, handler)

    def __disconnect_all(self):
        _disconnect_all(self.__tokens)

    def prepare_client(self, client: aioxmpp.Client):
        # summon roster service
        # connect to name change signal
        # connect to removed signal
        # connect to added signal
        self._roster_svc = client.summon(aioxmpp.RosterClient)
        self.__connect(self._roster_svc.on_entry_added, self._on_entry_updated)
        self.__connect(self._roster_svc.on_entry_name_changed,
                       self._on_entry_updated)
        self.__connect(self._roster_svc.on_entry_removed,
                       self._on_entry_updated)

    def shutdown_client(self, client: aioxmpp.Client):
        self.__disconnect_all()
        self._roster_svc = None

    def get_avatar(self, address: aioxmpp.JID,
                   font: Qt.QFont) \
            -> typing.Optional[Qt.QPicture]:
        """
        Generate an avatar for the given address based on its roster name.

        If no roster name is available, :data:`None` is returned.
        """
        if self._roster_svc is None:
            return
        try:
            name = self._roster_svc.items[address].name
        except KeyError:
            return
        if name is None:
            return
        return render_dummy_avatar(font, name, BASE_SIZE)

    def _on_entry_updated(self, item):
        self.on_avatar_changed(item.jid)


class AvatarManager:
    """
    .. signal:: on_avatar_changed(account, address)

        Emits when the avatar of a peer has changed.

        At the point the signal is emitted, :meth:`get_avatar` already returns
        the new avatar (it has already been obtained from the network, if
        needed).
    """

    on_avatar_changed = aioxmpp.callbacks.Signal()

    def __init__(self,
                 client: mlxc.client.Client,
                 writeman: mlxc.storage.WriteManager):
        super().__init__()
        self._workers = []
        self._queue = asyncio.Queue()

        self.__accountmap = {}

        client.on_client_prepare.connect(self._prepare_client)
        client.on_client_stopped.connect(self._shutdown_client)

    @asyncio.coroutine
    def _worker(self):
        while True:
            task = yield from self._queue.get()
            yield from task()

    def get_avatar_font(self):
        return Qt.QFontDatabase.systemFont(
            Qt.QFontDatabase.GeneralFont
        )

    @asyncio.coroutine
    def _fetch_avatar_and_emit_signal(self, fetch_func):
        pass

    def get_avatar(self,
                   account: mlxc.identity.Account,
                   address: aioxmpp.JID,
                   name_surrogate: typing.Optional[str]=None) -> Qt.QPicture:
        """
        Return an avatar for an entity.

        :param address: Jabber address of the entity to return an avatar for.
        :param name_surrogate: Optional name surrogate to use in case no human
            readable name for the entity is known.

        If no avatar is available in the cache, a null avatar or a generated
        one is returned instead and an attempt is made to obtain the avatar
        from the remote entity (if there is one available). Once the avatar
        has been fetched in the background, the usual :meth:`on_avatar_changed`
        signal will be emitted.

        If `name_surrogate` is given and no human-readable display name is
        known for the `address`, the `name_surrogate` is used instead of the
        local part of the `address`.
        """
        try:
            _, generator = self.__accountmap[account]
        except KeyError:
            font = self.get_avatar_font()
        else:
            font = self.get_avatar_font()
            result = generator.get_avatar(address, font)
            if result is not None:
                return result

        return render_dummy_avatar(font,
                                   name_surrogate or str(address),
                                   BASE_SIZE)

    def _on_backend_avatar_changed(self,
                                   account: mlxc.identity.Account,
                                   address: aioxmpp.JID):
        self.on_avatar_changed(account, address)

    def _prepare_client(self,
                        account: mlxc.identity.Account,
                        client: mlxc.client.Client):
        generator = RosterNameAvatarProvider()
        generator.prepare_client(client)

        tokens = []
        _connect(tokens, generator.on_avatar_changed,
                 functools.partial(self._on_backend_avatar_changed, account))

        self.__accountmap[account] = tokens, generator

    def _shutdown_client(self,
                         account: mlxc.identity.Account,
                         client: mlxc.client.Client):
        tokens, *_ = self.__accountmap.pop(account)
        _disconnect_all(tokens)
