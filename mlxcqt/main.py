import asyncio
import functools
import random

import aioxmpp
import aioxmpp.cache
import aioxmpp.im.p2p

import mlxc.conversation
import mlxc.main
import mlxc.roster
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


_PEPPER = random.SystemRandom().getrandbits(64).to_bytes(64 // 8, "little")


class RosterItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    LEFT_PADDING = PADDING + 6
    TAG_MARGIN = 2
    TAG_PADDING = 2
    TAG_FONT_SIZE = 0.9
    MIN_TAG_WIDTH = 16
    NAME_FONT_SIZE = 1.1

    MAX_AVATAR_SIZE = 48

    on_tag_clicked = aioxmpp.callbacks.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._cache = aioxmpp.cache.LRUDict()
        self._cache.maxsize = 128

    def _get_fonts(self, base_font):
        name_font = Qt.QFont(base_font)
        name_font.setWeight(Qt.QFont.Bold)
        name_font.setPointSizeF(name_font.pointSizeF() * self.NAME_FONT_SIZE)

        tag_font = Qt.QFont(base_font)
        tag_font.setPointSizeF(tag_font.pointSizeF() * self.TAG_FONT_SIZE)
        return name_font, tag_font

    def flush_caches(self):
        self._cache.clear()

    def layout_tags(self, font_metrics: Qt.QFontMetrics, tags, width):
        tags = tuple(sorted(
            ((tag_full,
              mlxc.utils.normalise_text_for_hash(tag_full))
             for tag_full in tags),
            key=lambda x: x[1]
        ))

        cache_key = tags, width

        try:
            return self._cache[cache_key]
        except KeyError:
            pass

        text_widths = [
            max(font_metrics.width(tag), self.MIN_TAG_WIDTH)
            for tag, _ in tags
        ]

        text_colours = [
            utils.text_to_qtcolor(normalized_tag)
            for _, normalized_tag in tags
        ]

        tag_widths = [
            max(text_width, self.MIN_TAG_WIDTH) +
            self.TAG_PADDING * 2
            for text_width in text_widths
        ]

        margin_width = max(
            (len(tags) - 1) * self.TAG_MARGIN,
            0,
        )

        total_width = sum(tag_widths) + margin_width
        min_tag_width_full = self.MIN_TAG_WIDTH + self.TAG_PADDING * 2

        if total_width > width:
            min_width = len(tags) * min_tag_width_full + margin_width
            if width <= min_width:
                scale = 0
            else:
                variable_width = total_width - min_width
                if variable_width == 0:
                    scale = 1
                else:
                    scale = (width - min_width) / variable_width
        else:
            scale = 1

        if scale < 1:
            tag_widths = [
                round(
                    (tag_width - min_tag_width_full) * scale
                ) + min_tag_width_full
                for tag_width in tag_widths
            ]

            texts = [
                font_metrics.elidedText(
                    text,
                    Qt.Qt.ElideMiddle,
                    tag_width - self.TAG_PADDING * 2,
                )
                for (text, _), tag_width in zip(tags, tag_widths)
            ]
        else:
            texts = [text for text, _ in tags]

        item = {
            "tags": tags,
            "texts": texts,
            "width": total_width,
            "text_widths": text_widths,
            "text_colours": text_colours,
            "tag_widths": tag_widths,
            "scale": scale,
        }

        self._cache[cache_key] = item

        return item

    def sizeHint(self, option, index):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        name_height = name_metrics.ascent() + name_metrics.descent()

        tag_metrics = Qt.QFontMetrics(tag_font)
        tag_text_height = tag_metrics.ascent() + tag_metrics.descent()

        total_height = (self.PADDING * 2 +
                        name_height +
                        self.SPACING +
                        tag_text_height +
                        self.SPACING +
                        tag_text_height +
                        self.TAG_PADDING * 2 +
                        self.TAG_MARGIN * 2)

        item = index.data(models.ROLE_OBJECT)
        ntags = len(item.tags)

        min_width = (self.LEFT_PADDING +
                     self.MAX_AVATAR_SIZE +
                     self.SPACING +
                     ntags * (
                         self.MIN_TAG_WIDTH +
                         self.TAG_PADDING * 2 +
                         self.TAG_MARGIN + 2) +
                     self.PADDING)

        return Qt.QSize(min_width, total_height)

    def _tag_rects(self, font_metrics, top_left, layout):
        tag_text_height = font_metrics.ascent() + font_metrics.descent()

        for tag_width in layout["tag_widths"]:
            tag_rect = Qt.QRectF(
                top_left,
                top_left + Qt.QPoint(
                    tag_width,
                    tag_text_height + 2 * self.TAG_PADDING,
                )
            )
            yield tag_rect

            top_left += Qt.QPoint(
                tag_width + self.TAG_MARGIN,
                0
            )

    def _hits_tag(self, local_pos, option, item):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        tag_metrics = Qt.QFontMetrics(tag_font)

        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
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

        layout = self.layout_tags(
            tag_metrics,
            item.tags,
            option.rect.width() - (
                top_left.x() - option.rect.x()
            ) - self.PADDING
        )

        for (tag, _), tag_rect in zip(
                layout["tags"],
                self._tag_rects(tag_metrics, top_left, layout)):

            if tag_rect.contains(local_pos):
                return tag

        return None

    def paint(self, painter, option, index):
        item = index.data(models.ROLE_OBJECT)
        name_font, tag_font = self._get_fonts(option.font)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)

        cursor_pos = option.widget.mapFromGlobal(Qt.QCursor.pos())

        name = item.label

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
            self.PADDING + self.SPACING,
            option.rect.height() / 2 - avatar_size / 2
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
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
            self.PADDING
        )

        name_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right() - self.PADDING,
                top_left.y() + name_metrics.ascent() + name_metrics.descent(),
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
                option.rect.width() - self.PADDING * 2,
                tag_metrics.ascent() + tag_metrics.descent(),
            )
        )

        jid = str(item.address)

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

        tags_layout = self.layout_tags(
            tag_metrics,
            item.tags,
            option.rect.width() - (
                top_left.x() - option.rect.x()
            ) - self.PADDING,
        )

        tag_text_ascent = tag_metrics.ascent()

        for text, tag_rect, colour in zip(
                tags_layout["texts"],
                self._tag_rects(tag_metrics, top_left, tags_layout),
                tags_layout["text_colours"]):
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
                top_left.y() + tag_text_ascent + self.TAG_PADDING,
                text,
            )

        if not item.tags:
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
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
            self.PADDING
        )

        editor_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right() - self.PADDING,
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
    def __init__(self,
                 client: mlxc.client.Client,
                 accounts: mlxc.identity.Accounts,
                 roster_manager: mlxc.roster.RosterManager,
                 conversations: mlxc.conversation.ConversationManager,
                 parent=None):
        super().__init__(parent=parent)
        self.accounts = accounts
        self.client = client
        self.conversations = conversations
        self.roster_manager = roster_manager
        self.ui = Ui_RosterWidget()
        self.ui.setupUi(self)
        self.ui.filter_widget.on_tags_changed.connect(self._update_filters)


        self.roster_model = models.RosterModel(roster_manager.items)

        self.sorted_roster = Qt.QSortFilterProxyModel()
        self.sorted_roster.setSourceModel(self.roster_model)
        self.sorted_roster.setSortRole(Qt.Qt.DisplayRole)
        self.sorted_roster.setSortLocaleAware(True)
        self.sorted_roster.setSortCaseSensitivity(False)
        self.sorted_roster.setDynamicSortFilter(True)
        self.sorted_roster.sort(0, Qt.Qt.AscendingOrder)

        self.roster_view_delegate = RosterItemDelegate()
        self.roster_view_delegate.on_tag_clicked.connect(self._tag_clicked)
        self.ui.roster_view.setItemDelegate(self.roster_view_delegate)
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

    def event(self, e: Qt.QEvent):
        if e.type() == Qt.QEvent.FontChange:
            self.roster_view_delegate.flush_caches()
        return super().event(e)

    def _rename(self):
        index = self.ui.roster_view.currentIndex()
        self.ui.roster_view.edit(index)

    def _toggle_tag_filter(self, tag):
        if self.ui.filter_widget.has_tag(tag):
            self.ui.filter_widget.remove_tag(tag)
        else:
            self.ui.filter_widget.add_tag(tag)

    def _clear_tag_filters(self):
        self.ui.filter_widget.clear_tags()

    def _add_tag_filter(self, tag):
        self.ui.filter_widget.add_tag(tag)

    def _remove_tag_filter(self, tag):
        self.ui.filter_widget.remove_tag(tag)

    def _tag_clicked(self, tag, modifiers):
        if modifiers & Qt.Qt.ControlModifier:
            self._toggle_tag_filter(tag)
        else:
            re_add = {tag} != set(self.ui.filter_widget.tags)
            self._clear_tag_filters()
            if re_add:
                self._add_tag_filter(tag)

        self._update_filters()

    def _clear_filters(self):
        self._clear_tag_filters()

    def _update_filters(self):
        parts = [
            Qt.QRegExp.escape(tag + "\n")
            for tag in sorted(self.ui.filter_widget.tags)
        ]
        regex = "(.*)".join(parts)

        self.sorted_roster.setFilterKeyColumn(0)
        self.sorted_roster.setFilterCaseSensitivity(True)
        self.sorted_roster.setFilterRole(roster.RosterModel.TAGS_ROLE)
        self.sorted_roster.setFilterRegExp(
            Qt.QRegExp(regex)
        )

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

    def _roster_item_activated(self, index):
        item = self.roster_model.data(
            self.ui.roster_view.model().mapToSource(index),
            models.ROLE_OBJECT,
        )
        account = item.account
        try:
            client = self.client.client_by_account(account)
        except KeyError:
            # FIXME: show a user-visible error here
            return

        conv = item.create_conversation(client)
        self.conversations.adopt_conversation(account, conv)

    def _get_all_tags(self):
        all_groups = set()
        for account in self.accounts:
            try:
                client = self.client.client_by_account(account)
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
            self.roster_model.data(
                self.ui.roster_view.model().mapToSource(index),
                models.ROLE_OBJECT,
            )
            for index in self.ui.roster_view.selectedIndexes()
        ]
        widget = roster_tags.RosterTagsPopup()
        pos = Qt.QCursor.pos()
        result = yield from widget.run(pos, self._get_all_tags(), items)
        if result is not None:
            to_add, to_remove = result
            tasks = []
            for item in items:
                client = self.main.client.client_by_account(item.account)
                roster = client.summon(aioxmpp.RosterClient)
                task = asyncio.ensure_future(
                    roster.set_entry(
                        item.address,
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
                self._add_tag_filter(tag)
            else:
                self._remove_tag_filter(tag)
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
            action.setChecked(self.ui.filter_widget.has_tag(tag))
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
            main.accounts,
        )
        self.roster = RosterWidget(main.client, main.accounts,
                                   main.roster,
                                   main.conversations)
        self.ui.splitter.insertWidget(0, self.roster)

        self.ui.statusbar.addPermanentWidget(
            taskmanager.TaskStatusWidget(self.ui.statusbar)
        )

        self.ui.action_manage_accounts.triggered.connect(
            self.account_manager.open
        )

        self.__convmap = {}
        self.__conversation_model = models.ConversationsModel(
            self.main.conversations
        )
        self.ui.conversations_view.setModel(
            self.__conversation_model
        )
        self.ui.conversations_view.activated.connect(
            self._conversation_item_activated
        )

        self.main.conversations.on_conversation_added.connect(
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
        page = conversation.ConversationView(wrapper)
        self.__convmap[wrapper] = page
        self.ui.conversation_pages.addWidget(page)
        self.ui.conversation_pages.setCurrentWidget(page)

    def _conversation_item_activated(self, index):
        conversation = self.main.conversations[index.row()]
        page = self.__convmap[conversation]
        self.main.conversations.start_soon(conversation)
        self.ui.conversation_pages.setCurrentWidget(page)

    @utils.asyncify
    @asyncio.coroutine
    def _join_muc(self, *args):
        dlg = join_muc.JoinMuc(self.main.accounts)
        join_info = yield from dlg.run()
        if join_info is not None:
            account, mucjid, nick = join_info
            self.main.conversations.open_muc_conversation(
                account,
                mucjid,
                nick,
            )

    @utils.asyncify
    @asyncio.coroutine
    def _add_contact(self, *args):
        dlg = add_contact.DlgAddContact(self.main.client,
                                        self.main.accounts)
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
        self.roster = mlxc.roster.RosterManager(
            self.accounts,
            self.client,
            self.writeman,
        )
        self.conversations = mlxc.conversation.ConversationManager(
            self.accounts,
            self.client,
        )
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
