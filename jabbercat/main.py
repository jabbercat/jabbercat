import asyncio
import functools
import logging
import random

import aioxmpp
import aioxmpp.cache
import aioxmpp.im.p2p

import jclib.conversation
import jclib.main
import jclib.roster
import jclib.utils
import jclib.tasks

import jabbercat.avatar

from . import (
    Qt, client, utils,
    conversation, models, taskmanager,
    webintegration,
)

from .dialogs import (
    account_manager,
    join_muc,
    roster_tags,
    add_contact,
    python_console,
)

from .widgets import (
    roster_view,
    tagsmenu,
)

from .ui.main import Ui_Main


logger = logging.getLogger(__name__)


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

        self.tags_model = models.TagsModel(main.roster.tags)

        self.sorted_tags = Qt.QSortFilterProxyModel()
        self.sorted_tags.setSourceModel(self.tags_model)
        self.sorted_tags.setSortRole(Qt.Qt.DisplayRole)
        self.sorted_tags.setSortLocaleAware(True)
        self.sorted_tags.setSortCaseSensitivity(False)
        self.sorted_tags.setDynamicSortFilter(True)
        self.sorted_tags.sort(0, Qt.Qt.AscendingOrder)

        self.checked_tags = models.CheckModel()
        self.checked_tags.setSourceModel(self.sorted_tags)

        self._tags_menu = tagsmenu.TagsMenu()
        self._tags_menu.setTitle(self.tr("Filter"))
        self._tags_menu.source_model = self.checked_tags

        self.roster_model = models.RosterModel(main.roster, main.avatar)
        self.roster_model.on_label_edited.connect(
            self._roster_label_edited,
        )

        self.filtered_roster = models.RosterFilterModel()
        self.filtered_roster.setSourceModel(self.roster_model)
        self.filtered_roster.tags_filter_model = self.checked_tags

        self.sorted_roster = Qt.QSortFilterProxyModel()
        self.sorted_roster.setSourceModel(self.filtered_roster)
        self.sorted_roster.setSortRole(Qt.Qt.DisplayRole)
        self.sorted_roster.setSortLocaleAware(True)
        self.sorted_roster.setSortCaseSensitivity(False)
        self.sorted_roster.setDynamicSortFilter(True)
        self.sorted_roster.sort(0, Qt.Qt.AscendingOrder)

        self._delegate = roster_view.RosterItemDelegate(main.avatar)
        self._delegate.on_tag_clicked.connect(self._roster_tag_activated)
        self.ui.roster_view.setItemDelegate(self._delegate)
        self.ui.roster_view.setMouseTracking(True)
        self.ui.roster_view.setModel(self.sorted_roster)
        self.ui.roster_view.setContextMenuPolicy(Qt.Qt.CustomContextMenu)

        self.ui.roster_view.activated.connect(
            self._roster_item_activated,
        )
        self.ui.roster_view.customContextMenuRequested.connect(
            self._roster_context_menu_requested,
        )
        self.ui.roster_view.selectionModel().selectionChanged.connect(
            self._roster_selection_changed
        )

        self.ui.action_manage_tags.triggered.connect(
            self._roster_item_manage_tags
        )

        self.ui.action_rename.triggered.connect(
            self._roster_item_rename
        )

        self._roster_item_menu = Qt.QMenu()
        self._roster_item_menu.addAction(self.ui.action_add_contact)
        self._roster_item_menu.addAction(self.ui.action_invite_contact)
        self._roster_item_menu.addSeparator()
        self._roster_item_menu.addAction(self.ui.action_rename)
        self._roster_item_menu.addAction(self.ui.action_manage_tags)
        # self._roster_item_menu.addSeparator()
        # self._roster_item_menu.addAction(self.ui.action_subscribe)
        # self._roster_item_menu.addAction(self.ui.action_subscribe_peer)
        # self._roster_item_menu.addAction(self.ui.action_unsubscribe_peer)
        self._roster_item_menu.addSeparator()
        self._roster_item_menu.addMenu(self._tags_menu)
        self._roster_item_menu.addSeparator()
        self._roster_item_menu.addAction(self.ui.action_remove_contact)

        self._roster_selection_changed(None, None)

        self.ui.roster_view.addActions(self._roster_item_menu.actions())

        for action in self.ui.roster_view.actions():
            action.setShortcutContext(
                Qt.Qt.WidgetWithChildrenShortcut
            )

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

        self.ui.action_focus_search_bar.triggered.connect(
            self.ui.magic_bar.setFocus
        )
        self.addAction(self.ui.action_focus_search_bar)

        self.ui.magic_bar.textChanged.connect(self._filter_text_changed)
        self.ui.magic_bar.tags_filter_model = self.checked_tags
        self.ui.magic_bar.installEventFilter(self)

        self.__identitymap = {}

        self.python_console = python_console.PythonConsole(self.main, self)
        self.ui.action_open_python_console.triggered.connect(
            self._open_python_console
        )
        self.ui.action_about_qt.triggered.connect(
            Qt.QApplication.aboutQt,
        )

    def eventFilter(self, obj: Qt.QObject, event: Qt.QEvent) -> bool:
        if obj is self.ui.magic_bar:
            if event.type() == Qt.QEvent.KeyPress:
                if event.key() == Qt.Qt.Key_Down:
                    self.ui.roster_view.setFocus()
                    return True
        return super().eventFilter(obj, event)

    def _open_python_console(self):
        self.python_console.show()

    def _find_tag_index(self, tag):
        for i in range(self.checked_tags.rowCount()):
            index = self.checked_tags.index(i, 0)
            if self.checked_tags.data(index, Qt.Qt.DisplayRole) == tag:
                return index
        return Qt.QModelIndex()

    def _filter_text_changed(self, new_text):
        self.filtered_roster.filter_by_text = new_text

    def _clear_filters(self):
        self.checked_tags.clear_check_states()

    def _roster_tag_activated(self, tag, modifiers):
        index = self._find_tag_index(tag)
        if not index.isValid():
            return

        is_checked = (
            self.checked_tags.data(index, Qt.Qt.CheckStateRole) == Qt.Qt.Checked
        )

        if modifiers & Qt.Qt.ControlModifier:
            self.checked_tags.setData(
                index,
                Qt.Qt.Unchecked if is_checked else Qt.Qt.Checked,
                Qt.Qt.CheckStateRole
            )
        else:
            self.checked_tags.clear_check_states()
            if not is_checked:
                self.checked_tags.setData(index, Qt.Qt.Checked,
                                          Qt.Qt.CheckStateRole)

    def _roster_label_edited(self, item, new_label):
        new_label = new_label or None
        if item.label == new_label:
            logger.debug("not emitting a roster change for label edit: "
                         "label is unchanged (%r == %r)",
                         item.label, new_label)
            return

        jclib.tasks.manager.start(
            self._roster_set_label(item, new_label)
        )

    def _roster_selection_changed(self, selected, deselected):
        roster_model = self.ui.roster_view.model()
        selection_model = self.ui.roster_view.selectionModel()
        all_selected = selection_model.selectedIndexes()
        selected_count = len(all_selected)

        selected_items = [
            roster_model.data(index, models.ROLE_OBJECT)
            for index in all_selected
        ]

        self.ui.action_rename.setEnabled(
            any(item.can_set_label for item in selected_items)
        )
        self.ui.action_manage_tags.setEnabled(
            any(item.can_manage_tags for item in selected_items)
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
        unsorted_index = self.sorted_roster.mapToSource(index)
        unfiltered_index = self.filtered_roster.mapToSource(unsorted_index)

        item = self.roster_model.data(
            unfiltered_index,
            models.ROLE_OBJECT,
        )
        account = item.account
        try:
            client = self.main.client.client_by_account(account)
        except KeyError:
            # FIXME: show a user-visible error here
            return

        conv = item.create_conversation(client)
        self.main.conversations.adopt_conversation(account, conv)

    def _roster_context_menu_requested(self, pos):
        self._roster_item_menu.popup(self.ui.roster_view.mapToGlobal(pos))

    @asyncio.coroutine
    def _roster_set_label(self, item, new_label):
        jclib.tasks.manager.update_text(
            self.tr("Renaming contact {!r} to {!r}").format(
                item.label,
                new_label or "",
            )
        )
        yield from item.owner.set_label(
            item,
            new_label,
        )

    @utils.asyncify
    @asyncio.coroutine
    def _roster_item_manage_tags(self, _):
        items = [
            item for item in (
                self.roster_model.data(
                    self.ui.roster_view.model().mapToSource(index),
                    models.ROLE_OBJECT,
                )
                for index in self.ui.roster_view.selectedIndexes()
            )
            if item.can_manage_tags
        ]
        widget = roster_tags.RosterTagsPopup()
        pos = Qt.QCursor.pos()
        result = yield from widget.run(pos, self.main.roster.tags, items)
        if result is not None:
            to_add, to_remove = result
            jclib.tasks.manager.start(self._roster_apply_tags(
                items,
                to_add,
                to_remove,
            ))

    @asyncio.coroutine
    def _roster_apply_tags(self, items, to_add, to_remove):
        jclib.tasks.manager.update_text(
            "Changing tags of {} roster items".format(
                len(items)
            )
        )
        tasks = []
        for item in items:
            # first check whether an operation is needed
            item_tags = set(item.tags)
            if not (item_tags & to_remove or to_add - item_tags):
                continue
            task = asyncio.ensure_future(
                item.update_tags(to_add, to_remove)
            )
            tasks.append(task)
        yield from asyncio.gather(*tasks)

    def _roster_item_rename(self):
        index = self.ui.roster_view.currentIndex()
        self.ui.roster_view.edit(index)

    def _conversation_added(self, wrapper):
        page = conversation.ConversationView(
            wrapper,
            self.main.web_profile,
        )
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
        jclib.tasks.manager.start(self.add_contact(
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
                "account needed for the operation is not connected"
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
        jclib.tasks.manager.update_text(
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


class QtMain(jclib.main.Main):
    Client = client.Client

    def __init__(self, loop):
        super().__init__(loop)
        self.roster = jclib.roster.RosterManager(
            self.accounts,
            self.client,
            self.writeman,
        )
        self.avatar = jabbercat.avatar.AvatarManager(
            self.client,
            self.writeman,
        )
        self.conversations = jclib.conversation.ConversationManager(
            self.accounts,
            self.client,
        )
        self.avatar_urls = webintegration.AvatarURLSchemeHandler(
            self.accounts,
            self.avatar,
        )
        self.web_profile = Qt.QWebEngineProfile()
        self.web_profile.installUrlSchemeHandler(
            b"avatar",
            self.avatar_urls,
        )
        self.window = MainWindow(self)

    @asyncio.coroutine
    def run_core(self):
        self.window.show()
        yield from super().run_core()
        self.avatar.close()
        try:
            yield from asyncio.wait_for(self.client.shutdown(),
                                        timeout=5)
        except asyncio.TimeoutError:
            pass
