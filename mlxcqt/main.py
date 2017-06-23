import asyncio
import functools
import random

import aioxmpp
import aioxmpp.im.p2p

import mlxc.conversation
import mlxc.main
import mlxc.utils
import mlxc.tasks

from . import (
    Qt, client, roster, utils,
    conversation, models, taskmanager,
)

from .dialogs import (
    account_manager,
    join_muc,
    roster_tags,
    add_contact,
)

from .ui.main import Ui_Main
from .ui.roster import Ui_RosterWidget


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

    on_tag_clicked = aioxmpp.callbacks.Signal()

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

    def _hits_tag(self, local_pos, option, item):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        tag_metrics = Qt.QFontMetrics(tag_font)

        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING+self.SPACING*2+avatar_size,
            self.PADDING
        )

        top_left += Qt.QPoint(
            0,
            name_metrics.ascent() + name_metrics.descent() + self.SPACING
        )

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

            tag_rect = Qt.QRectF(top_left, top_left + Qt.QPoint(
                width + 2*self.TAG_PADDING,
                tag_metrics.ascent() + tag_metrics.descent() +
                2*self.TAG_PADDING
            ))

            if tag_rect.contains(local_pos):
                return group

            top_left += Qt.QPoint(
                self.TAG_MARGIN + 2*self.TAG_PADDING + width,
                0
            )

        return None

    def paint(self, painter, option, index):
        item = index.data(roster.RosterModel.ITEM_ROLE)
        name_font, tag_font = self._get_fonts(option.font)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)

        cursor_pos = option.widget.mapFromGlobal(Qt.QCursor.pos())

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

            tag_rect = Qt.QRectF(top_left, top_left + Qt.QPoint(
                width + 2*self.TAG_PADDING,
                tag_metrics.ascent() + tag_metrics.descent() +
                2*self.TAG_PADDING
            ))

            if tag_rect.contains(cursor_pos):
                colour = colour.lighter(125)

            painter.setPen(Qt.QPen(Qt.Qt.NoPen))
            painter.setBrush(Qt.QBrush(colour))

            painter.drawRoundedRect(
                tag_rect,
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

    def updateEditorGeometry(self, editor, option, index):
        print("updating editor geometry", editor)
        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING+self.SPACING*2+avatar_size,
            self.PADDING
        )

        editor_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right()-self.PADDING,
                top_left.y() + editor.geometry().height()
            )
        )
        print(editor_rect)

        editor.setGeometry(editor_rect)

    def editorEvent(self, event, model, option, index):
        if (event.type() == Qt.QEvent.MouseButtonPress and
                event.button() == Qt.Qt.LeftButton):
            item = index.data(roster.RosterModel.ITEM_ROLE)
            tag_hit = self._hits_tag(event.pos(), option, item)
            if tag_hit is not None:
                self.on_tag_clicked(tag_hit, event.modifiers())
                return True
        elif event.type() == Qt.QEvent.MouseMove:
            option.widget.update(index)
        return super().editorEvent(event, model, option, index)


class RosterWidget(Qt.QWidget):
    def __init__(self, main, identity, parent=None):
        super().__init__(parent=parent)
        self.main = main
        self.roster_manager = roster.Roster()
        self.identity = identity
        self.ui = Ui_RosterWidget()
        self.ui.setupUi(self)

        self.ui.filter_widget.hide()
        self.ui.clear_filters.clicked.connect(
            self._clear_filters
        )

        self._filtered_for_tags = set()

        self._tokens = []
        self._tokens.append((
            self.main.client.on_client_prepare,
            self.main.client.on_client_prepare.connect(
                self._prepare_client
            )
        ))
        self._tokens.append((
            self.main.client.on_client_stopped,
            self.main.client.on_client_stopped.connect(
                self._stop_client
            )
        ))

        self.sorted_roster = Qt.QSortFilterProxyModel()
        self.sorted_roster.setSourceModel(self.roster_manager.model)
        self.sorted_roster.setSortRole(Qt.Qt.DisplayRole)
        self.sorted_roster.setSortLocaleAware(True)
        self.sorted_roster.setSortCaseSensitivity(False)
        self.sorted_roster.setDynamicSortFilter(True)
        self.sorted_roster.sort(0, Qt.Qt.AscendingOrder)

        delegate = RosterItemDelegate(self.ui.roster_view)
        delegate.on_tag_clicked.connect(self._tag_clicked)
        self.ui.roster_view.setItemDelegate(delegate)
        self.ui.roster_view.setModel(self.sorted_roster)
        self.ui.roster_view.setMouseTracking(True)

        self.ui.roster_view.activated.connect(
            self._roster_item_activated,
        )
        self.ui.roster_view.customContextMenuRequested.connect(
            self._roster_context_menu_requested,
        )
        self.ui.roster_view.selectionModel().selectionChanged.connect(
            self._selection_changed
        )

        self.ui.action_manage_tags.triggered.connect(
            self._manage_tags
        )

        self.ui.action_rename.triggered.connect(
            self._rename
        )

        self._menu = Qt.QMenu()
        self._menu.addAction(self.ui.action_add_contact)
        self._menu.addAction(self.ui.action_invite_contact)
        self._menu.addSeparator()
        self._menu.addAction(self.ui.action_rename)
        self._menu.addAction(self.ui.action_manage_tags)
        self._menu.addSeparator()
        self._menu.addAction(self.ui.action_subscribe)
        self._menu.addAction(self.ui.action_subscribe_peer)
        self._menu.addAction(self.ui.action_unsubscribe_peer)
        self._menu.addSeparator()
        self._filter_menu = self._menu.addMenu("Filter")
        self._menu.addSeparator()
        self._menu.addAction(self.ui.action_remove_contact)

        self.addActions(self._menu.actions())

        self._selection_changed(None, None)

        for action in self.actions():
            action.setShortcutContext(
                Qt.Qt.WidgetWithChildrenShortcut
            )

    def tear_down(self):
        for signal, token in self._tokens:
            signal.disconnect(token)

    def _clear_filters(self, *_):
        self._filtered_for_tags.clear()
        self._update_filters()

    def _prepare_client(self,
                        account: mlxc.identity.Account,
                        client):
        if account.identity is not self.identity:
            return
        self.roster_manager.connect_client(account, client)

    def _stop_client(self,
                     account: mlxc.identity.Account,
                     client):
        if account.identity is not self.identity:
            return
        self.roster_manager.disconnect_client(account, client)

    def _rename(self):
        index = self.ui.roster_view.currentIndex()
        self.ui.roster_view.edit(index)

    def _tag_clicked(self, tag, modifiers):
        if modifiers & Qt.Qt.ControlModifier:
            try:
                self._filtered_for_tags.remove(tag)
            except KeyError:
                self._filtered_for_tags.add(tag)
        else:
            if self._filtered_for_tags == {tag}:
                self._filtered_for_tags.discard(tag)
            else:
                self._filtered_for_tags = {tag}

        self._update_filters()

    def _update_filters(self):
        parts = [
            Qt.QRegExp.escape(tag+"\n")
            for tag in sorted(self._filtered_for_tags)
        ]
        regex = "(.*)".join(parts)

        self.sorted_roster.setFilterKeyColumn(0)
        self.sorted_roster.setFilterCaseSensitivity(True)
        self.sorted_roster.setFilterRole(roster.RosterModel.TAGS_ROLE)
        self.sorted_roster.setFilterRegExp(
            Qt.QRegExp(regex)
        )

        filter_text_parts = []
        if self._filtered_for_tags:
            filter_text_parts.append(
                ", ".join(
                    "<span style='background-color: rgba({}, 1);'>"
                    "{}</span>".format(
                        ", ".join(
                            str(int(channel*255))
                            for channel in mlxc.utils.text_to_colour(
                                    mlxc.utils.normalise_text_for_hash(tag)
                            )
                        ),
                        tag
                    )
                    for tag in sorted(
                            self._filtered_for_tags
                    )
                )
            )

        if filter_text_parts:
            self.ui.filter_widget.show()
            self.ui.filter_label.setText(
                "Filtering for {}".format(", ".join(filter_text_parts))
            )
        else:
            self.ui.filter_widget.hide()

    def _selection_changed(self, selected, deselected):
        selection_model = self.ui.roster_view.selectionModel()
        all_selected = selection_model.selectedIndexes()
        selected_count = len(all_selected)

        self.ui.action_rename.setEnabled(
            selected_count == 1 and selection_model.currentIndex().isValid()
        )
        self.ui.action_manage_tags.setEnabled(
            selected_count > 0
        )
        self.ui.action_subscribe.setEnabled(
            selected_count > 0
        )
        self.ui.action_subscribe_peer.setEnabled(
            selected_count > 0
        )
        self.ui.action_unsubscribe_peer.setEnabled(
            selected_count > 0
        )
        self.ui.action_remove_contact.setEnabled(
            selected_count > 0
        )

    @utils.asyncify
    @asyncio.coroutine
    def _roster_item_activated(self, index):
        item = self.roster_manager.model.item_wrapper_from_index(
            self.ui.roster_view.model().mapToSource(index)
        )
        client = self.main.client.client_by_account(item.account)
        p2p_convs = client.summon(aioxmpp.im.p2p.Service)
        print("starting conversation with", item.jid)
        yield from p2p_convs.get_conversation(item.jid)

    def _get_all_tags(self):
        all_groups = set()
        for account in self.identity.accounts:
            try:
                client = self.main.client.client_by_account(account)
            except KeyError:
                continue
            all_groups |= set(
                client.summon(aioxmpp.RosterClient).groups.keys()
            )
        return all_groups

    @utils.asyncify
    @asyncio.coroutine
    def _manage_tags(self, _):
        items = [
            self.roster_manager.model.item_wrapper_from_index(
                self.ui.roster_view.model().mapToSource(index)
            )
            for index in self.ui.roster_view.selectedIndexes()
        ]
        widget = roster_tags.RosterTagsPopup()
        pos = Qt.QCursor.pos()
        result = yield from widget.run(pos, self._get_all_tags(), items)
        if result is not None:
            to_add, to_remove = result
            print(to_add, to_remove)
            tasks = []
            for item in items:
                client = self.main.client.client_by_account(item.account)
                roster = client.summon(aioxmpp.RosterClient)
                task = asyncio.ensure_future(
                    roster.set_entry(
                        item.jid,
                        add_to_groups=to_add,
                        remove_from_groups=to_remove,
                    )
                )
                tasks.append(task)
            yield from asyncio.gather(*tasks)

    def _roster_context_menu_requested(self, pos):
        all_tags = list(self._get_all_tags())
        all_tags.sort(key=str.casefold)
        self._filter_menu.clear()

        action = self._filter_menu.addAction("Clear all filters")
        action.triggered.connect(self._clear_filters)

        self._filter_menu.addSection("Tags")

        def tag_action_triggered(tag, checked):
            if checked:
                self._filtered_for_tags.add(tag)
            else:
                self._filtered_for_tags.discard(tag)
            self._update_filters()

        for tag in all_tags:
            color = utils.text_to_qtcolor(
                mlxc.utils.normalise_text_for_hash(tag)
            )
            action = self._filter_menu.addAction(tag)
            icon = Qt.QPixmap(16, 16)
            icon.fill(color)
            icon = Qt.QIcon(icon)
            action.setCheckable(True)
            action.setChecked(tag in self._filtered_for_tags)
            action.setIcon(icon)
            action.triggered.connect(
                functools.partial(tag_action_triggered, tag)
            )

        self._menu.popup(self.ui.roster_view.mapToGlobal(pos))


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

        self.ui.statusbar.addPermanentWidget(
            taskmanager.TaskStatusWidget(self.ui.statusbar)
        )

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

        self.ui.action_add_contact.triggered.connect(
            self._add_contact,
        )

        self.__identitymap = {}

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

    def _setup_identity(self, identity):
        widget = RosterWidget(self.main, identity)

        self.ui.roster_tabs.addTab(
            widget,
            identity.name
        )

        return widget

    def _teardown_identity(self, info):
        info.tear_down()

    def _identity_added(self, identity):
        self.__identitymap[identity] = self._setup_identity(identity)
        self.convmanager.handle_identity_added(identity)
        self._set_conversations_view_root()
        self.ui.conversations_view.expandAll()

    def _identity_removed(self, identity):
        self._teardown_identity(self.__identitymap.pop(identity))
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
    def _join_muc(self, *args):
        dlg = join_muc.JoinMuc(self.main.identities)
        join_info = yield from dlg.run()
        if join_info is not None:
            account, mucjid, nick = join_info
            mlxc.tasks.manager.start(
                self.join_muc(first_account, mucjid, nick)
            )

    @utils.asyncify
    @asyncio.coroutine
    def _add_contact(self, *args):
        dlg = add_contact.DlgAddContact(self.main)
        result = yield from dlg.run()
        if result is None:
            return
        account, peer_jid, display_name, tags = result
        mlxc.tasks.manager.start(self.add_contact(
            account,
            peer_jid,
            display_name,
            tags,
        ))

    @asyncio.coroutine
    def add_contact(self, account, peer_jid, display_name, tags):
        try:
            client = self.main.client.client_by_account(account)
        except KeyError:
            raise RuntimeError(
                "account needed for the operation is connected"
            )

        roster = client.summon(aioxmpp.RosterClient)
        roster.subscribe(peer_jid)
        roster.approve(peer_jid)
        yield from roster.set_entry(
            peer_jid,
            name=display_name or None,
            add_to_groups=tags,
        )

    @asyncio.coroutine
    def join_muc(self, account, mucjid, nick):
        nick = nick or "test"
        mlxc.tasks.manager.update_text(
            "Joining group chat {} as {}".format(mucjid, nick)
        )
        client = self.main.client.client_by_account(account)
        muc = client.summon(aioxmpp.MUCClient)
        room, fut = muc.join(mucjid, nick)
        yield from fut

    def closeEvent(self, ev):
        result = super().closeEvent(ev)
        self.main.quit()
        return result


class QtMain(mlxc.main.Main):
    Client = client.Client

    def __init__(self, loop):
        super().__init__(loop)
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
