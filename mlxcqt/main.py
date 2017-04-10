import asyncio
import random

import aioxmpp
import aioxmpp.im.p2p

import mlxc.conversation
import mlxc.main
import mlxc.utils

from . import (
    Qt, client, roster, utils, account_manager,
    conversation, models,
)

from .ui.main import Ui_Main


_PEPPER = random.SystemRandom().getrandbits(64).to_bytes(64//8, "little")


class RosterItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    LEFT_PADDING = PADDING + 6
    TAG_MARGIN = 2
    TAG_PADDING = 2
    TAG_FONT_SIZE = 0.9
    NAME_FONT_SIZE = 1.1

    MAX_AVATAR_SIZE = 48

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def _get_fonts(self, base_font):
        name_font = Qt.QFont(base_font)
        name_font.setWeight(Qt.QFont.Bold)
        name_font.setPointSizeF(name_font.pointSizeF()*self.NAME_FONT_SIZE)

        tag_font = Qt.QFont(base_font)
        tag_font.setPointSizeF(tag_font.pointSizeF()*self.TAG_FONT_SIZE)
        return name_font, tag_font

    def sizeHint(self, option, index):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        name_height = name_metrics.ascent() + name_metrics.descent()

        tag_metrics = Qt.QFontMetrics(tag_font)
        tag_text_height = tag_metrics.ascent() + tag_metrics.descent()

        total_height = (self.PADDING*2 +
                        name_height +
                        self.SPACING +
                        tag_text_height +
                        self.SPACING +
                        tag_text_height +
                        self.TAG_PADDING*2 +
                        self.TAG_MARGIN*2)

        return Qt.QSize(0, total_height)

    def paint(self, painter, option, index):
        item = index.data(roster.RosterModel.ITEM_ROLE)
        name_font, tag_font = self._get_fonts(option.font)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        if option.state & Qt.QStyle.State_Selected:
            painter.setBrush(Qt.QBrush(option.palette.highlight()))
        else:
            painter.setBrush(Qt.QBrush(option.backgroundBrush))
        painter.drawRect(option.rect)

        name = index.data()

        colour = utils.text_to_qtcolor(
            name,
        )

        # painter.drawRect(
        #     Qt.QRect(
        #         option.rect.topLeft(),
        #         option.rect.topLeft() + Qt.QPoint(
        #             self.LEFT_PADDING - self.PADDING,
        #             option.rect.height()-1,
        #         )
        #     )
        # )

        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        avatar_origin = option.rect.topLeft()
        avatar_origin = avatar_origin + Qt.QPoint(
            self.PADDING+self.SPACING,
            option.rect.height()/2 - avatar_size/2
        )

        pic = utils.make_avatar_picture(name, avatar_size)
        painter.drawPicture(avatar_origin, pic)

        # pen_colour = Qt.QColor(colour)
        # pen_colour.setAlpha(127)
        # painter.setPen(Qt.QPen(pen_colour))
        # painter.setBrush(colour)

        # avatar_rect = Qt.QRectF(
        #     avatar_origin,
        #     avatar_origin + Qt.QPoint(avatar_size, avatar_size)
        # )

        # # painter.drawRoundedRect(
        # #     avatar_rect,
        # #     avatar_size / 24, avatar_size / 24,
        # # )

        # painter.drawRect(
        #     avatar_rect,
        # )

        # painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        # painter.setPen(Qt.QPen(Qt.QColor(255, 255, 255, 255)))
        # painter.setBrush(Qt.QBrush())
        # avatar_font = Qt.QFont(name_font)
        # avatar_font.setPixelSize(avatar_size*0.85-2*self.PADDING)
        # avatar_font.setWeight(Qt.QFont.Thin)
        # painter.setFont(avatar_font)
        # painter.drawText(
        #     Qt.QRectF(
        #         avatar_origin + Qt.QPoint(self.PADDING, self.PADDING),
        #         avatar_origin + Qt.QPoint(avatar_size-self.PADDING*2,
        #                                   avatar_size-self.PADDING*2),
        #     ),
        #     Qt.Qt.AlignHCenter | Qt.Qt.AlignVCenter | Qt.Qt.TextSingleLine,
        #     name[0].upper(),
        # )

        if option.state & Qt.QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        name_font.setWeight(Qt.QFont.Bold)
        name_metrics = Qt.QFontMetrics(name_font)
        painter.setFont(name_font)

        tag_metrics = Qt.QFontMetrics(tag_font)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING+self.SPACING*2+avatar_size,
            self.PADDING
        )

        name_rect = Qt.QRect(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING*2,
                name_metrics.ascent() + name_metrics.descent(),
            )
        )

        # import hashlib
        # hash_ = hashlib.sha1()
        # hash_.update(name.encode("utf-8") + _PEPPER)
        # name = hash_.hexdigest()

        name = name_metrics.elidedText(
            name,
            Qt.Qt.ElideRight,
            name_rect.width()
        )

        painter.drawText(name_rect, Qt.Qt.TextSingleLine, name)

        painter.setFont(tag_font)

        top_left += Qt.QPoint(
            0,
            name_metrics.ascent() + name_metrics.descent() + self.SPACING
        )

        jid_rect = Qt.QRect(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING*2,
                tag_metrics.ascent() + tag_metrics.descent(),
            )
        )

        jid = str(item.jid)

        # hash_ = hashlib.sha1()
        # hash_.update(jid.encode("utf-8") + _PEPPER)
        # jid = hash_.hexdigest()

        jid = name_metrics.elidedText(
            jid,
            Qt.Qt.ElideLeft,
            jid_rect.width()
        )
        painter.drawText(jid_rect, Qt.Qt.TextSingleLine, jid)

        top_left += Qt.QPoint(
            self.TAG_MARGIN,
            tag_metrics.ascent() + tag_metrics.descent() + self.SPACING
        )

        groups = sorted(
            ((group_full,
              mlxc.utils.normalise_text_for_hash(group_full))
             for group_full in item.groups),
            key=lambda x: x[1]
        )
        for group, group_norm in groups:
            width = tag_metrics.width(group)

            colour = utils.text_to_qtcolor(
                group_norm,
            )

            painter.setPen(Qt.QPen(Qt.Qt.NoPen))
            painter.setBrush(Qt.QBrush(colour))

            painter.drawRoundedRect(
                Qt.QRectF(top_left, top_left + Qt.QPoint(
                    width + 2*self.TAG_PADDING,
                    tag_metrics.ascent() + tag_metrics.descent() +
                    2*self.TAG_PADDING
                )),
                2.0, 2.0,
            )

            painter.setPen(option.palette.text().color())
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_metrics.ascent() + self.TAG_PADDING,
                group,
            )

            top_left += Qt.QPoint(
                self.TAG_MARGIN + 2*self.TAG_PADDING + width,
                0
            )

        if not item.groups:
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_metrics.ascent() + self.TAG_PADDING,
                "no tags"
            )


class MainWindow(Qt.QMainWindow):
    def __init__(self, main, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Main()
        self.ui.setupUi(self)
        self.main = main
        self.account_manager = account_manager.DlgAccountManager(
            main.client,
            main.identities,
        )

        sorted_roster = Qt.QSortFilterProxyModel(self.ui.roster_view)
        sorted_roster.setSourceModel(self.main.roster.model)
        sorted_roster.setSortRole(Qt.Qt.DisplayRole)
        sorted_roster.setSortLocaleAware(True)
        sorted_roster.setSortCaseSensitivity(False)
        sorted_roster.setDynamicSortFilter(True)
        sorted_roster.sort(0, Qt.Qt.AscendingOrder)
        self.ui.roster_view.setModel(sorted_roster)
        delegate = RosterItemDelegate(self.ui.roster_view)
        self.ui.roster_view.setItemDelegate(delegate)
        self.ui.roster_view.activated.connect(self._roster_item_activated)

        self.ui.action_manage_accounts.triggered.connect(
            self.account_manager.open
        )

        self.convmanager = mlxc.conversation.ConversationManager()
        self.main.identities.on_identity_added.connect(
            self._identity_added
        )
        self.main.identities.on_identity_removed.connect(
            self._identity_removed
        )

        self.main.client.on_client_prepare.connect(
            self.convmanager.handle_client_prepare,
        )
        self.main.client.on_client_stopped.connect(
            self.convmanager.handle_client_stopped,
        )

        self.__convmap = {}
        self.__conversation_model = models.ConversationsModel(
            self.convmanager.tree
        )
        self.ui.conversations_view.setModel(
            self.__conversation_model
        )
        self.ui.conversations_view.activated.connect(
            self._conversation_item_activated
        )

        self.convmanager.on_conversation_added.connect(
            self._conversation_added
        )

        self.ui.action_muc_join.triggered.connect(
            self._join_muc,
        )

    def _conversation_added(self, wrapper):
        conv = wrapper.conversation
        page = conversation.ConversationView(conv)
        self.__convmap[wrapper.conversation] = page
        self.ui.conversation_pages.addWidget(page)
        self.ui.conversation_pages.setCurrentWidget(page)

    def _set_conversations_view_root(self):
        if len(self.main.identities.identities) == 1:
            self.ui.conversations_view.setRootIndex(
                self.__conversation_model.node_to_index(
                    self.convmanager.get_identity_wrapper(
                        self.main.identities.identities[0]
                    )
                )
            )
        else:
            self.ui.conversations_view.setRootIndex(Qt.QModelIndex())

    def _identity_added(self, identity):
        self.convmanager.handle_identity_added(identity)
        self._set_conversations_view_root()
        self.ui.conversations_view.expandAll()

    def _identity_removed(self, identity):
        self.convmanager.handle_identity_removed(identity)
        self._set_conversations_view_root()
        self.ui.conversations_view.expandAll()

    def _conversation_item_activated(self, index):
        node = index.internalPointer()
        if isinstance(node.object_, mlxc.conversation.ConversationNode):
            conv = node.object_.conversation
            page = self.__convmap[conv]
            self.ui.conversation_pages.setCurrentWidget(page)

    @utils.asyncify
    @asyncio.coroutine
    def _roster_item_activated(self, index):
        item = self.main.roster.model.item_wrapper_from_index(
            self.ui.roster_view.model().mapToSource(index)
        )
        client = self.main.client.client_by_account(item.account)
        p2p_convs = client.summon(aioxmpp.im.p2p.Service)
        print("starting conversation with", item.jid)
        conv = yield from p2p_convs.get_conversation(item.jid)
        page = self.__convmap[conv]
        self.ui.conversation_pages.setCurrentWidget(page)

    def _join_muc(self, *args):
        first_account = self.main.identities.identities[0].accounts[0]
        print(first_account)
        client = self.main.client.client_by_account(first_account)
        print(client)
        jid, *_ = Qt.QInputDialog.getText(self, "Input MUC JID", "MUC JID")
        jid = aioxmpp.JID.fromstr(jid).bare()
        muc = client.summon(aioxmpp.MUCClient)
        muc.join(jid, "MLXC Test")

    def closeEvent(self, ev):
        result = super().closeEvent(ev)
        self.main.quit()
        return result


class QtMain(mlxc.main.Main):
    Client = client.Client

    def __init__(self, loop):
        super().__init__(loop)
        self.roster = roster.Roster()
        self.client.on_client_prepare.connect(self.roster.connect_client)
        self.client.on_client_stopped.connect(self.roster.disconnect_client)

        self.window = MainWindow(self)

    @asyncio.coroutine
    def run_core(self):
        self.window.show()
        yield from super().run_core()
        try:
            yield from asyncio.wait_for(self.client.shutdown(),
                                        timeout=5)
        except asyncio.TimeoutError:
            pass
