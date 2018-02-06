import abc
import asyncio
import functools
import logging
import typing
import unicodedata

import aioxmpp

import jclib.client
import jclib.identity
import jclib.storage
import jclib.utils

import jabbercat.utils

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


def render_dummy_avatar(font: Qt.QFont,
                        name: str,
                        size: float,
                        colour_text: str=None):
    colour = jabbercat.utils.text_to_qtcolor(
        jclib.utils.normalise_text_for_hash(colour_text or name)
    )
    grapheme = first_grapheme(name)
    picture = Qt.QPicture()
    painter = Qt.QPainter(picture)
    render_dummy_avatar_base(painter, colour, size)
    render_dummy_avatar_grapheme(painter, grapheme, font, size)
    return picture


def render_avatar_image(image: Qt.QImage, size: float):
    if image.isNull():
        return None

    picture = Qt.QPicture()
    painter = Qt.QPainter(picture)
    painter.drawImage(
        Qt.QRectF(0, 0, size, size),
        image,
    )
    painter.end()
    return picture


class XMPPAvatarProvider:
    """
    .. signal:: on_avatar_changed(address)

        Emits when the avatar of a peer has changed.

        The image needs to be fetched separately and explicitly.

    """

    on_avatar_changed = aioxmpp.callbacks.Signal()

    def __init__(self, account: jclib.identity.Account):
        super().__init__()
        self.__tokens = []
        self._account = account
        self._avatar_svc = None
        self._cache = aioxmpp.cache.LRUDict()
        self._cache.maxsize = 1024
        self.logger = logging.getLogger(".".join([
            __name__, type(self).__qualname__, str(account.jid)
        ]))

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
    def _get_image(self, address: aioxmpp.JID) -> typing.Optional[Qt.QImage]:
        try:
            metadata = yield from self._avatar_svc.get_avatar_metadata(address)
        except (aioxmpp.errors.XMPPError,
                aioxmpp.errors.ErroneousStanza) as exc:
            self.logger.warning("cannot fetch avatar from %s: %s",
                                address, exc)
            return

        for descriptor in metadata:
            try:
                data = yield from descriptor.get_image_bytes()
            except (NotImplementedError, RuntimeError,
                    aioxmpp.errors.XMPPCancelError):
                continue
            img = Qt.QImage.fromData(data)
            if not img.isNull():
                return img

    @asyncio.coroutine
    def fetch_avatar(self, address: aioxmpp.JID) \
            -> typing.Optional[Qt.QPicture]:
        """
        Fetch an avatar and wrap it in a QPicture.
        """
        img = yield from self._get_image(address)
        if img is None:
            self._cache[address] = None
            return None

        picture = render_avatar_image(img, BASE_SIZE)
        self._cache[address] = picture
        return picture

    def get_avatar(self, address: aioxmpp.JID) \
            -> typing.Optional[Qt.QPicture]:
        """
        Return an avatar from the cache.

        The result of :meth:`fetch_avatar` is stored in an LRU cache
        internally. If no cached result is found, :data:`None` is returned.

        .. note::

            The :meth:`on_avatar_changed` signal emits without the cache having
            been refreshed. Consumers of this signal should always call
            :meth:`fetch_avatar`.
        """
        return self._cache[address]


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
        return render_dummy_avatar(font, name, BASE_SIZE,
                                   str(address))

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
                 client: jclib.client.Client,
                 writeman: jclib.storage.WriteManager):
        super().__init__()
        self._queue = asyncio.Queue()
        self._enqueued = set()
        self._workers = [
            asyncio.ensure_future(self._worker())
            for i in range(10)
        ]
        self.logger = logging.getLogger(
            ".".join([__name__, type(self).__qualname__])
        )

        self.__accountmap = {}

        client.on_client_prepare.connect(self._prepare_client)
        client.on_client_stopped.connect(self._shutdown_client)

    def close(self):
        for worker in self._workers:
            worker.cancel()

    @asyncio.coroutine
    def _worker(self):
        while True:
            task = yield from self._queue.get()
            try:
                yield from task
            except Exception as exc:
                self.logger.warning("background job failed", exc_info=True)

    def get_avatar_font(self):
        return Qt.QFontDatabase.systemFont(
            Qt.QFontDatabase.GeneralFont
        )

    @asyncio.coroutine
    def _fetch_avatar_and_emit_signal(self, fetch_func, account, address):
        self.logger.debug("fetching avatar for %s", address)
        try:
            yield from asyncio.wait_for(fetch_func(address), timeout=10)
        except asyncio.TimeoutError:
            self.logger.info("failed to fetch avatar for %s (timeout)",
                             address)
            return
        finally:
            self._enqueued.discard((account, address))
        self.logger.debug("avatar for %s fetched", address)
        self.on_avatar_changed(account, address)

    def _fetch_in_background(self, account, provider, address):
        key = account, address
        if key in self._enqueued:
            return
        self._enqueued.add(key)
        self._queue.put_nowait(
            self._fetch_avatar_and_emit_signal(
                provider.fetch_avatar,
                account,
                address,
            )
        )

    def get_avatar(self,
                   account: jclib.identity.Account,
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
            _, generator, xmpp_avatar = self.__accountmap[account]
        except KeyError:
            font = self.get_avatar_font()
        else:
            try:
                result = xmpp_avatar.get_avatar(address)
            except KeyError:
                self._fetch_in_background(account, xmpp_avatar, address)
                result = None

            if result is not None:
                return result

            font = self.get_avatar_font()
            result = generator.get_avatar(address, font)
            if result is not None:
                return result

        return render_dummy_avatar(font,
                                   name_surrogate or str(address),
                                   BASE_SIZE)

    def _on_xmpp_avatar_changed(self,
                                account: jclib.identity.Account,
                                service: XMPPAvatarProvider,
                                address: aioxmpp.JID):
        # first check if the current avatar is in cache, otherwise don’t bother
        # to fetch it
        # if it is in cache, add a task to the queue to fetch it
        try:
            service.get_avatar(address)
        except KeyError:
            return

        self._fetch_in_background(account, service, address)

    def _on_backend_avatar_changed(self,
                                   account: jclib.identity.Account,
                                   address: aioxmpp.JID):
        self.on_avatar_changed(account, address)

    def _prepare_client(self,
                        account: jclib.identity.Account,
                        client: jclib.client.Client):
        xmpp_avatar = XMPPAvatarProvider(account)
        xmpp_avatar.prepare_client(client)

        generator = RosterNameAvatarProvider()
        generator.prepare_client(client)

        tokens = []
        _connect(tokens, generator.on_avatar_changed,
                 functools.partial(self._on_backend_avatar_changed, account))
        _connect(tokens, xmpp_avatar.on_avatar_changed,
                 functools.partial(self._on_xmpp_avatar_changed,
                                   account, xmpp_avatar))

        self.__accountmap[account] = tokens, generator, xmpp_avatar

    def _shutdown_client(self,
                         account: jclib.identity.Account,
                         client: jclib.client.Client):
        tokens, *_ = self.__accountmap.pop(account)
        _disconnect_all(tokens)
