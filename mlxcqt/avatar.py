import aioxmpp
import aioxmpp.service

import mlxc.config
import mlxc.utils

from . import Qt


class AvatarCacheStorage:
    def __init__(self, path_provider):
        self._path_provider = path_provider
        self._inmemory_cache = {}

    def _get_path(self, peer_jid):
        return (self._path_provider.cache_dir() /
                mlxc.utils.mlxc_uid /
                mlxc.utils.mlxc_avatars_uid /
                mlxc.config.escape_dirname(peer_jid))

    def get_avatar_image(self, peer_jid):
        path = self._get_path(peer_jid)
        image = Qt.QImage(str(path))
        if not image.isNull():
            return image
        return None

    def store_avatar_image(self, peer_jid, image):
        path = self._get_path(peer_jid)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path), 'PNG')


class AvatarCache(aioxmpp.service.Service):
    ORDER_AFTER = [
        aioxmpp.AvatarClient,
    ]

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self.__cache = None
        self.__avatar_client = self.dependencies[aioxmpp.AvatarClient]

    @asyncio.coroutine
    def _fetch_avatar_image(self, peer_jid):
        self._clie

    @asyncio.coroutine
    def get_avatar_image(self, peer_jid: aioxmpp.JID) -> Qt.QImage:
        """
        Retrieve an avatar image from the given peer.

        :param peer_jid: The peer to retrieve the avatar from.
        :type peer_jid: :class:`aioxmpp.JID`
        :return: The avatar image if available
        :rtype: :class:`Qt.QImage` or :data:`None`

        Retrieve the avatar from the peer or from a local cache. The local
        cache is automatically invalidated by subscribing to the peers avatar
        update events.
        """

