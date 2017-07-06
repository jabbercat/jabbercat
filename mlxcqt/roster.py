import asyncio
import functools
import html
import logging

import aioxmpp

import mlxc.instrumentable_list

from . import Qt, model_adaptor


logger = logging.getLogger(__name__)


class ItemWrapper:
    def __init__(self, roster_item, client, account, presence):
        super().__init__()
        self._item = roster_item
        self.client = client
        self.account = account
        self.presence = presence

    @property
    def jid(self):
        return self._item.jid

    @property
    def name(self):
        return self._item.name

    @property
    def groups(self):
        return self._item.groups

    @property
    def subscription(self):
        return self._item.subscription

    @property
    def ask(self):
        return self._item.ask

    @property
    def approved(self):
        return self._item.approved

    def __eq__(self, other):
        if isinstance(other, aioxmpp.roster.Item):
            return self._item == other
        return super().__eq__(other)

    def __ne__(self, other):
        return not (self == other)


class RosterModel(Qt.QAbstractListModel):
    ITEM_ROLE = Qt.Qt.UserRole + 1
    TAGS_ROLE = Qt.Qt.UserRole + 2

    on_set_name = aioxmpp.callbacks.Signal()

    def __init__(self, items):
        super().__init__()
        self.items = items
        self._adaptor = model_adaptor.ModelListAdaptor(
            self.items, self)

    def _raw_item_index(self, raw_item):
        for i, item in enumerate(self.items):
            if item._item is raw_item:
                return i
        raise ValueError("wrapper for {!r} is not in list".format(raw_item))

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.items)

    def item_wrapper_from_index(self, index):
        if not index.isValid():
            return None
        return self.items[index.row()]

    def raw_item_changed(self, raw_item):
        try:
            index = self._raw_item_index(raw_item)
        except ValueError:
            logger.warning("item not found for update in roster model")
            return
        qtindex = self.index(index, 0)
        self.dataChanged.emit(
            qtindex,
            qtindex,
        )

    def data(self, index, role):
        if not index.isValid():
            return None

        item = self.items[index.row()]
        if role == Qt.Qt.DisplayRole:
            return item.name or str(item.jid)
        elif role == Qt.Qt.ToolTipRole:
            rows = []
            if item.name:
                rows.append("<th>Name:</th><td>{}</td>".format(
                    html.escape(item.name)
                ))
            rows.append("<th>Your account:</th><td>{}</td>".format(
                html.escape(str(item.account.jid))
            ))
            rows.append("<th>Address:</th><td>{}</td>".format(
                html.escape(str(item.jid))
            ))
            if item.groups:
                rows.append("<th>Groups:</th><td>{}</td>".format(
                    html.escape(", ".join(sorted(item.groups,
                                                 key=str.casefold)))
                ))
            rows.append("<th>Status:</th><td>{}</td>".format(
                html.escape(str(
                    aioxmpp.PresenceState.from_stanza(item.presence)
                    if item.presence
                    else "unavailable"
                ))
            ))

            presence_note = {
                "none": "Online state is not shared.",
                "to": "The contact can see your online state.",
                "from": "You can see the contacts online state (but not vice versa).",
                "both": "You can see each others online state.",
            }[item.subscription]

            return "<h2>{}</h2><p>via <span style='background-color: #{}; color: #{}; padding: 2px'>{}</span></p><table><tr>{rows}</tr></table><p>{presence_note}</p>".format(
                html.escape(item.name or str(item.jid)),
                "".join(map("{:02x}".format, map(int, item.account.colour))),
                "000",
                html.escape(str(item.account.jid)),
                rows="</tr><tr>".join(rows),
                presence_note=presence_note,
            )
        elif role == Qt.Qt.EditRole:
            return item.name or ""
        elif role == self.ITEM_ROLE:
            return item
        elif role == self.TAGS_ROLE:
            return "".join(sorted(
                tag+"\n" for tag in item.groups
            ))

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        if role != Qt.Qt.EditRole:
            return False
        self.on_set_name(self.items[index.row()], value)
        return True

    def flags(self, index):
        flags = super().flags(index)
        flags |= Qt.Qt.ItemIsEditable
        return flags


class Roster:
    ROSTER_EVENT_LIST = ["on_entry_added",
                         "on_entry_removed",
                         "on_entry_added_to_group",
                         "on_entry_removed_from_group",
                         "on_entry_name_changed"]
    PRESENCE_EVENT_LIST = ["on_available",
                           "on_changed",
                           "on_unavailable"]

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(
            type(self).__module__ + "." +
            type(self).__qualname__
        )
        self.items = mlxc.instrumentable_list.ModelList()
        self.model = RosterModel(self.items)
        self.model.on_set_name.connect(
            self._on_set_name,
            self.model.on_set_name.SPAWN_WITH_LOOP(None)
        )
        self._clients = {}

    @asyncio.coroutine
    def _on_set_name(self, item_wrapper, new_name):
        _, roster, *_ = self._clients[item_wrapper.client]
        yield from roster.set_entry(
            item_wrapper.jid,
            name=new_name,
        )

    def connect_client(self, account, client):
        roster = client.summon(aioxmpp.RosterClient)
        presence = client.summon(aioxmpp.PresenceClient)
        roster_tokens = []
        for event in self.ROSTER_EVENT_LIST:
            roster_tokens.append(
                getattr(roster, event).connect(
                    functools.partial(
                        getattr(self, event),
                        client,
                    )
                )
            )

        presence_tokens = []
        for event in self.PRESENCE_EVENT_LIST:
            presence_tokens.append(
                getattr(presence, event).connect(
                    functools.partial(
                        getattr(self, event),
                        client,
                    )
                )
            )

        self._clients[client] = (account, roster, roster_tokens,
                                 presence, presence_tokens)

    def on_entry_added(self, client, item):
        logging.debug("on_entry_added(%r, %r)", client, item)
        account, _, _, presence, _ = self._clients[client]
        self.items.append(ItemWrapper(
            item,
            client,
            account,
            presence.get_most_available_stanza(
                item.jid.bare()
            )))

    def on_entry_removed(self, client, item):
        logging.debug("on_entry_removed(%r, %r)", client, item)
        self.items.remove(item)

    def on_entry_name_changed(self, client, item):
        logging.debug("on_entry_name_changed(%r, %r)", client, item)
        self.model.raw_item_changed(item)

    def on_entry_added_to_group(self, client, item, group_name):
        logging.debug("on_entry_added_to_group(%r, %r, %r)",
                      client, item, group_name)
        self.model.raw_item_changed(item)

    def on_entry_removed_from_group(self, client, item, group_name):
        logging.debug("on_entry_removed_from_group(%r, %r, %r)",
                      client, item, group_name)
        self.model.raw_item_changed(item)

    def _get_item_by_jid(self, bare_jid):
        for item in self.items:
            if item.jid == bare_jid:
                return item
        raise KeyError(bare_jid)

    def _presence_update(self, client, bare_jid):
        try:
            item = self._get_item_by_jid(bare_jid)
        except KeyError:
            logging.debug("presence update for JID not in roster")
            return

        item.presence = client.summon(
            aioxmpp.PresenceClient
        ).get_most_available_stanza(
            bare_jid
        )

    def on_available(self, client, full_jid, stanza):
        logging.debug("on_available(%r, %r, %r)",
                      client, full_jid, stanza)
        self._presence_update(client, full_jid.bare())

    def on_changed(self, client, full_jid, stanza):
        logging.debug("on_changed(%r, %r, %r)",
                      client, full_jid, stanza)
        self._presence_update(client, full_jid.bare())

    def on_unavailable(self, client, full_jid, stanza):
        logging.debug("on_unavailable(%r, %r, %r)",
                      client, full_jid, stanza)
        self._presence_update(client, full_jid.bare())

    def disconnect_client(self, account, client):
        _, roster, roster_tokens, presence, presence_tokens = \
            self._clients[client]

        for token, event in zip(roster_tokens, self.ROSTER_EVENT_LIST):
            getattr(roster, event).disconnect(token)

        for token, event in zip(presence_tokens, self.PRESENCE_EVENT_LIST):
            getattr(presence, event).disconnect(token)

        for i in reversed(range(len(self.items))):
            item = self.items[i]
            if item.account is account:
                del self.items[i]
