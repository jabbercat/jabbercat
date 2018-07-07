import asyncio
import functools
import logging
import random

import aioxmpp
import aioxmpp.cache
import aioxmpp.im.p2p

import jclib.archive
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
    contact_requests,
)

from .widgets import (
    conversations_view,
    roster_view,
    tagsmenu,
    collapsible,
)

from .ui.main import Ui_Main


logger = logging.getLogger(__name__)


class MainWindow(Qt.QMainWindow):
    def __init__(self, main, parent=None):
        super().__init__(parent=parent)

        self._old_roster_size = None

        self.ui = Ui_Main()
        self.ui.setupUi(self)
        self.main = main
        self.account_manager = account_manager.DlgAccountManager(
            main.client,
            main.accounts,
        )

        watermark = Qt.QImage(":/img/jabbercat-contour-only.png")
        self.ui.watermark.watermark = watermark

        self._trayicon = Qt.QSystemTrayIcon()
        self._trayicon.setIcon(Qt.QApplication.windowIcon())
        self._trayicon.show()

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

        self.roster_model = models.RosterModel(main.roster, main.avatar,
                                               main.metadata)
        self.roster_model.on_label_edited.connect(
            self._roster_label_edited,
        )

        self.contact_requests = contact_requests.DlgContactRequests(
            main.roster,
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

        self._roster_item_delegate = roster_view.RosterItemDelegate(
            main.avatar
        )
        self._roster_item_delegate.on_tag_clicked.connect(
            self._roster_tag_activated
        )
        self.ui.roster_view.setItemDelegate(self._roster_item_delegate)
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

        self.ui.action_manage_contact_requests.triggered.connect(
            self.contact_requests.open,
        )

        self.__convmap = {}
        self.__pagemap = {}
        self.__conversation_model = models.ConversationsModel(
            self.main.conversations,
            self.main.avatar,
            self.main.metadata,
        )

        self.sorted_conversations = Qt.QSortFilterProxyModel()
        self.sorted_conversations.setSourceModel(self.__conversation_model)
        self.sorted_conversations.setSortRole(Qt.Qt.DisplayRole)
        self.sorted_conversations.setSortLocaleAware(True)
        self.sorted_conversations.setSortCaseSensitivity(False)
        self.sorted_conversations.setDynamicSortFilter(True)
        self.sorted_conversations.sort(0, Qt.Qt.AscendingOrder)

        self.ui.conversations_view.setModel(
            self.sorted_conversations
        )
        self._conversation_item_delegate = \
            conversations_view.ConversationItemDelegate(self.main.avatar)

        self.ui.conversations_view.setItemDelegate(
            self._conversation_item_delegate
        )
        self.ui.conversations_view.selectionModel().selectionChanged.connect(
            self._conversation_selected,
        )
        self.ui.conversations_view.activated.connect(
            self._conversation_item_activated,
        )
        self.ui.conversations_view.clicked.connect(
            self._conversation_item_clicked,
        )
        self.ui.conversations_view.selectionModel().currentChanged.connect(
            self._conversation_item_current_changed
        )
        self.ui.conversations_view.customContextMenuRequested.connect(
            self._conversations_view_context_menu_requested,
        )

        self._conversation_item_menu = Qt.QMenu()
        self._conversation_item_menu.addAction(
            self.ui.action_muc_join
        )
        self._conversation_item_menu.addSeparator()
        self._conversation_item_menu.addAction(
            self.ui.action_close_conversation
        )

        self.ui.conversation_pages.currentChanged.connect(
            self._current_conversation_page_changed
        )

        self.main.conversations.on_conversation_added.connect(
            self._conversation_added
        )
        self.main.conversations.on_conversation_removed.connect(
            self._conversation_removed
        )

        self.ui.action_muc_join.triggered.connect(
            self._join_muc,
        )

        self.ui.action_add_contact.triggered.connect(
            self._add_contact,
        )
        self.ui.action_remove_contact.triggered.connect(
            self._remove_contact,
        )

        self.ui.action_close_conversation.triggered.connect(
            self._close_conversation_triggered,
        )

        self.ui.action_join_support_muc.triggered.connect(
            self._join_support_muc,
        )

        self.ui.action_focus_search_bar.triggered.connect(
            self._select_magic_bar
        )
        self.ui.action_focus_search_bar.changed.connect(
            self._relabel_magic_bar
        )
        self.addAction(self.ui.action_focus_search_bar)

        self.ui.magic_bar.textChanged.connect(self._filter_text_changed)
        self.ui.magic_bar.tags_filter_model = self.checked_tags
        self.ui.magic_bar.installEventFilter(self)
        self._relabel_magic_bar()

        self.__identitymap = {}

        self.python_console = python_console.PythonConsole(self.main, self)
        self.ui.action_open_python_console.triggered.connect(
            self._open_python_console
        )
        self.ui.action_about_qt.triggered.connect(
            Qt.QApplication.aboutQt,
        )

        self.ui.conversations_view.placeholder_text = (
            "Start a conversation by double-clicking an item from the roster!"
        )

    def _relabel_magic_bar(self):
        self.ui.magic_bar.setPlaceholderText(
            self.tr("Search ({shortcut})...").format(
                shortcut=self.ui.action_focus_search_bar.shortcut().toString(
                    Qt.QKeySequence.NativeText
                )
            )
        )

    def _select_magic_bar(self):
        self.ui.magic_bar.selectAll()
        self.ui.magic_bar.setFocus()

    def eventFilter(self, obj: Qt.QObject, event: Qt.QEvent) -> bool:
        if obj is self.ui.magic_bar:
            if event.type() == Qt.QEvent.KeyPress:
                if event.key() == Qt.Qt.Key_Down:
                    self.ui.roster_view.setFocus()
                    return True
            elif event.type() == Qt.QEvent.FocusIn:
                if self.ui.roster_view_collapse.checkState() == Qt.Qt.Unchecked:
                    self.ui.roster_view_collapse.click()

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
        wrapper = self.main.conversations.adopt_conversation(account, conv)
        page = self.__convmap[wrapper]
        self.__pagemap[page] = wrapper

        # we need to clear first so that the roster is hidden
        if self.filtered_roster.rowCount() == 1:
            self.ui.magic_bar.clear()

        self._select_conversation(wrapper)

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
            self.main.avatar,
            self.main.metadata,
            self.main.web_profile,
        )
        self.__convmap[wrapper] = page
        self.__pagemap[page] = wrapper
        self.ui.conversation_pages.addWidget(page)
        if self.ui.conversation_pages.currentWidget() == self.ui.watermark:
            self.ui.conversation_pages.setCurrentWidget(page)

    def _conversation_removed(self, wrapper):
        page = self.__convmap.pop(wrapper)
        self.ui.conversation_pages.removeWidget(page)
        del self.__pagemap[page]

    def _activate_conversation_page(
            self, page,
            transfer_focus=True,
            force_focus=False):
        is_already_active = self.ui.conversation_pages.currentWidget() == page
        if not is_already_active:
            self.ui.conversation_pages.setCurrentWidget(page)
        if transfer_focus and (not is_already_active or force_focus):
            page.set_focus_to_message_input()

    def _select_conversation(self, conversation):
        index = self.main.conversations.index(conversation)
        self.ui.conversations_view.selectionModel().select(
            self.sorted_conversations.mapFromSource(
                self.__conversation_model.index(index, 0,
                                                Qt.QModelIndex())
            ),
            Qt.QItemSelectionModel.ClearAndSelect |
            Qt.QItemSelectionModel.Current
        )

    def _conversation_item_activated(self, index: Qt.QModelIndex):
        if not index.isValid():
            return

        mapped_index = self.sorted_conversations.mapToSource(index)
        conversation = self.main.conversations[mapped_index.row()]
        page = self.__convmap[conversation]
        self._activate_conversation_page(page, force_focus=True)
        self._select_conversation(conversation)

    def _conversation_item_clicked(self, index: Qt.QModelIndex):
        if not index.isValid():
            return

        mapped_index = self.sorted_conversations.mapToSource(index)
        conversation = self.main.conversations[mapped_index.row()]
        page = self.__convmap[conversation]
        self._activate_conversation_page(page, transfer_focus=False)
        self._select_conversation(conversation)

    def _conversation_selected(self,
                               selected: Qt.QItemSelection,
                               deselected: Qt.QItemSelection):
        if len(self.main.conversations) == 0:
            return

        indexes = self.ui.conversations_view.selectionModel().selectedIndexes()
        if not len(indexes):
            logger.warning(
                "congrats, you managed to deselect all conversations. are you"
                " happy now? IS THIS WHAT YOU WANTED?")
            return

        index = self.sorted_conversations.mapToSource(indexes[0])
        conversation = self.main.conversations[index.row()]
        page = self.__convmap[conversation]
        self._activate_conversation_page(page)

    def _current_conversation_page_changed(self, new_index: int):
        page = self.ui.conversation_pages.widget(new_index)
        if not page:
            logger.warning("page changed to nonexistant widget: %d",
                           new_index)
            return

        try:
            conversation = self.__pagemap[page]
        except KeyError:
            return
        conv_index = self.main.conversations.index(conversation)

        model_index = self.sorted_conversations.mapFromSource(
            self.__conversation_model.index(
                conv_index,
                0,
                Qt.QModelIndex()
            )
        )
        self.ui.conversations_view.selectionModel().select(
            model_index,
            Qt.QItemSelectionModel.ClearAndSelect |
            Qt.QItemSelectionModel.Current,
        )

    def _conversation_item_current_changed(self, current: Qt.QModelIndex):
        self.ui.action_close_conversation.setEnabled(
            current.isValid()
        )

    def _close_conversation_triggered(self, *args):
        index = self.ui.conversations_view.selectionModel().currentIndex()
        if not index.isValid():
            return

        mapped_index = self.sorted_conversations.mapToSource(index)

        conversation = self.main.conversations[mapped_index.row()]
        jclib.tasks.manager.start(self.main.conversations.close_conversation(
            conversation.account,
            conversation.conversation_address,
        ))

    def _conversations_view_context_menu_requested(self, pos):
        self._conversation_item_menu.popup(
            self.ui.conversations_view.mapToGlobal(pos)
        )

    @asyncio.coroutine
    def _join_muc_dialogue(self, muc_jid=None):
        dlg = join_muc.JoinMuc(self.main.accounts)
        join_info = yield from dlg.run(muc_jid)
        if join_info is not None:
            account, mucjid, nick = join_info
            self.main.conversations.open_muc_conversation(
                account,
                mucjid,
                nick,
            )

    @utils.asyncify
    @asyncio.coroutine
    def _join_muc(self, *args):
        yield from self._join_muc_dialogue()

    @utils.asyncify
    @asyncio.coroutine
    def _join_support_muc(self, *args):
        yield from self._join_muc_dialogue(
            muc_jid=aioxmpp.JID.fromstr("jabbercat@conference.zombofant.net")
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

    @utils.asyncify
    @asyncio.coroutine
    def _remove_contact(self, *args):
        item = self.roster_model.data(
            self.ui.roster_view.model().mapToSource(
                self.ui.roster_view.currentIndex()
            ),
            models.ROLE_OBJECT,
        )
        if item is None:
            return
        dlg = Qt.QMessageBox(
            Qt.QMessageBox.Warning,
            "Remove contact",
            "This will remove {} ({}) from your contact list. Re-adding will "
            "require approval. Do you want to continue?".format(
                item.address,
                item.label,
            ),
            Qt.QMessageBox.Yes | Qt.QMessageBox.No,
            self,
        )

        result = yield from utils.exec_async(dlg)
        if result != Qt.QMessageBox.Yes:
            return

        jclib.tasks.manager.start(self.remove_contact(item))

    @asyncio.coroutine
    def remove_contact(self, item):
        jclib.tasks.manager.update_text("removing {}".format(item.address))
        yield from item.owner.remove(item)

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
        self.avatar = jabbercat.avatar.AvatarManager(
            self.client,
            self.writeman,
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
