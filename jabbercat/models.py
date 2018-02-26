import bisect
import collections.abc
import enum
import typing
import unicodedata

import aioxmpp.callbacks

import jclib.conversation
import jclib.identity
import jclib.instrumentable_list
import jclib.roster
import jclib.utils

import jabbercat.avatar

from . import Qt, model_adaptor, utils


ROLE_OBJECT = Qt.Qt.UserRole + 1
ROLE_TAGS = Qt.Qt.UserRole + 2
ROLE_FILTER_SCORE = Qt.Qt.UserRole + 3


class AccountsModel(Qt.QAbstractTableModel):
    COLUMN_ADDRESS = 0
    COLUMN_ENABLED = 1
    COLUMN_COUNT = 2

    def __init__(self, accounts: jclib.identity.Accounts):
        super().__init__()
        self.__accounts = accounts
        self.__adaptor = model_adaptor.ModelListAdaptor(
            self.__accounts, self
        )

        self.__accounts.data_changed.connect(self._data_changed)

    def _data_changed(self, _, index1, index2, column1, column2, roles):
        return self.dataChanged.emit(
            self.index(index1, column1 or 0),
            self.index(index2, column2 or self.COLUMN_COUNT - 1),
            roles or [],
        )

    def columnCount(self, index=Qt.QModelIndex()):
        return self.COLUMN_COUNT

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self.__accounts)

    def flags(self, index):
        result = super().flags(index)
        if index.column() == self.COLUMN_ENABLED:
            result |= Qt.Qt.ItemIsUserCheckable
        return result

    def data(self,
             index: Qt.QModelIndex,
             role: Qt.Qt.ItemDataRole=Qt.Qt.DisplayRole):
        if not index.isValid():
            return

        account = self.__accounts[index.row()]
        column = index.column()

        if role == Qt.Qt.DisplayRole:
            if column == self.COLUMN_ADDRESS:
                return str(account.jid)
        elif role == Qt.Qt.CheckStateRole:
            if column == self.COLUMN_ENABLED:
                if account.enabled:
                    return Qt.Qt.Checked
                else:
                    return Qt.Qt.Unchecked
        elif role == ROLE_OBJECT:
            return account

    def setData(self,
                index: Qt.QModelIndex,
                value,
                role: Qt.Qt.ItemDataRole=Qt.Qt.EditRole):
        if not index.isValid():
            return False

        account = self.__accounts[index.row()]
        column = index.column()

        if column == self.COLUMN_ENABLED:
            if role == Qt.Qt.CheckStateRole:
                new_enabled = value == Qt.Qt.Checked
                self.__accounts.set_account_enabled(
                    account,
                    new_enabled,
                )
                return True

        return False

    def headerData(self,
                   section: int,
                   orientation: Qt.Qt.Orientation,
                   role: Qt.Qt.ItemDataRole=Qt.Qt.DisplayRole):
        if orientation != Qt.Qt.Horizontal:
            return None

        if role != Qt.Qt.DisplayRole:
            return None

        if section == self.COLUMN_ADDRESS:
            return self.tr("Address")
        elif section == self.COLUMN_ENABLED:
            return self.tr("Enabled")


class ConversationsModel(Qt.QAbstractTableModel):
    COLUMN_LABEL = 0
    COLUMN_COUNT = 1

    def __init__(self,
                 conversations: jclib.conversation.ConversationManager):
        super().__init__()
        self.__conversations = conversations
        self.__conversations.on_unread_count_changed.connect(
            self._handle_unread_count_changed,
            self.__conversations.on_unread_count_changed.WEAK,
        )
        self.__adaptor = model_adaptor.ModelListAdaptor(
            self.__conversations, self
        )

    def columnCount(self, index):
        return self.COLUMN_COUNT

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self.__conversations)

    def _handle_unread_count_changed(
            self,
            conversation_node: jclib.conversation.ConversationNode,
            new_counter: int):
        index = self.index(self.__conversations.index(conversation_node),
                           0,
                           Qt.QModelIndex())
        self.dataChanged.emit(index, index, [])  # Qt.Qt.DisplayRole

    def data(self,
             index: Qt.QModelIndex,
             role: Qt.Qt.ItemDataRole=Qt.Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.Qt.DisplayRole:
            return self.__conversations[index.row()].label
        elif role == ROLE_OBJECT:
            return self.__conversations[index.row()]


class RosterTagsModel(Qt.QAbstractListModel):
    COLUMN_NAME = 0
    COLUMN_COUNT = 1

    def __init__(self, model_list, parent=None):
        super().__init__(parent=parent)
        self._model_list = model_list
        self.__adaptor = model_adaptor.ModelListAdaptor(model_list, self)

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self._model_list)

    def data(self, index, role):
        if not index.isValid():
            return

        row = index.row()
        if role == Qt.Qt.DisplayRole:
            return self._model_list[row]


class RosterTagsSelectionModel(RosterTagsModel):
    def __init__(self, model_list, parent=None):
        super().__init__(model_list, parent=parent)
        self._to_add = set()
        self._to_remove = set()
        self._original = {}

    @property
    def to_add(self):
        return frozenset(self._to_add)

    @property
    def to_remove(self):
        return frozenset(self._to_remove)

    @property
    def selected(self):
        return frozenset(set(self._original.keys()) -
                         self._to_remove) | self._to_add

    def select_groups(self, groups):
        for group in groups:
            self.select_group(group)

    def select_group(self, group):
        try:
            index = self._model_list.index(group)
        except ValueError:
            return

        self._to_add.add(group)
        qtindex = self.index(index, 0)
        self.dataChanged.emit(
            qtindex,
            qtindex,
            [Qt.Qt.CheckStateRole]
        )

    def setup(self, item_groups):
        self._to_add.clear()
        self._to_remove.clear()
        if not item_groups:
            self._original = {}
            return
        common = set(item_groups[0])
        all = set(item_groups[0])
        for groups in item_groups[1:]:
            groups = set(groups)
            common &= groups
            all |= groups

        self._original = {
            group: (Qt.Qt.Checked
                    if group in common
                    else Qt.Qt.PartiallyChecked)
            for group in all
        }

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._model_list) - 1, 0),
            [Qt.Qt.CheckStateRole]
        )

    def data(self, index, role):
        if not index.isValid():
            return super().data(index, role)

        row = index.row()
        if role == Qt.Qt.CheckStateRole:
            group = self._model_list[row]
            if group in self._to_add:
                return Qt.Qt.Checked
            elif group in self._to_remove:
                return Qt.Qt.Unchecked
            return self._original.get(group, Qt.Qt.Unchecked)

        return super().data(index, role)

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        if role != Qt.Qt.CheckStateRole:
            return False

        group = self._model_list[index.row()]
        if value == Qt.Qt.Checked:
            self._to_add.add(group)
            self._to_remove.discard(group)
            return True
        elif value == Qt.Qt.Unchecked:
            self._to_remove.add(group)
            self._to_add.discard(group)
            return True
        elif value == Qt.Qt.PartiallyChecked:
            self._to_add.discard(group)
            self._to_remove.discard(group)
            return True

        return False

    def flags(self, index):
        group = self._model_list[index.row()]
        flags = super().flags(index)
        flags |= Qt.Qt.ItemIsUserCheckable
        if self._original.get(group, Qt.Qt.Unchecked) == Qt.Qt.PartiallyChecked:
            flags |= Qt.Qt.ItemIsTristate | Qt.Qt.ItemIsUserTristate
        return flags


class DisableSelectionOfIdentities(Qt.QIdentityProxyModel):
    def flags(self, index):
        flags = super().flags(index)
        if not index.parent().isValid():
            flags = (flags & ~(Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled))
        return flags


class FilterDisabledItems(Qt.QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(
            source_row,
            AccountsModel.COLUMN_ENABLED,
            source_parent
        )
        is_enabled = self.sourceModel().data(index, Qt.Qt.CheckStateRole)
        if is_enabled != Qt.Qt.Checked:
            return False
        return True


class FlattenModelToSeparators(Qt.QAbstractProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._breaks = []
        self._connections = []

    def setSourceModel(self, new_model):
        self.beginResetModel()
        self._breaks.clear()
        for conn in self._connections:
            conn.disconnect()
        super().setSourceModel(new_model)

        model = self.sourceModel()
        self._breaks.clear()
        i_absolute = 0
        for i in range(model.rowCount()):
            idx = model.index(i, 0, Qt.QModelIndex())
            nchildren = model.rowCount(idx)
            self._breaks.append(
                i_absolute
            )
            i_absolute += nchildren + 1

        self._connections.append(
            model.rowsInserted.connect(self._source_rowsInserted)
        )

        self._connections.append(
            model.rowsRemoved.connect(self._source_rowsRemoved)
        )

        self._connections.append(
            model.rowsAboutToBeRemoved.connect(
                self._source_rowsAboutToBeRemoved
            )
        )

        self.endResetModel()

    def _source_rowsInserted(self, parent, start, end):
        # check if the parent maps to our root
        if self.mapFromSource(parent).parent().isValid():
            # drop
            return

        if parent.isValid():
            # adding inlined children
            # map start index
            mapped_parent = self.mapFromSource(parent)
            offset = mapped_parent.row() + 1
            start_mapped = start + offset
            end_mapped = end + offset
            new_children = (end - start) + 1
            self.beginInsertRows(Qt.QModelIndex(), start_mapped, end_mapped)
            for i, old_break in enumerate(
                    self._breaks[parent.row() + 1:],
                    parent.row() + 1):  # update breaks *after* the parent
                self._breaks[i] += new_children
            self.endInsertRows()
        else:
            # adding new root
            # find break for start index
            if start >= len(self._breaks):
                offset = self._len() - start
            else:
                offset = self._breaks[start + 1] - start

            start_mapped = start + offset
            end_mapped = end + offset
            new_children = (end - start) + 1

            self.beginInsertRows(Qt.QModelIndex(), start_mapped, end_mapped)
            for i, old_break in enumerate(
                    self._breaks[start + 1:],
                    start + 1):  # update breaks *after* the newly inserted ones
                self._breaks[i] += new_children

            # insert new breaks
            self._breaks[start + 1:start + 1] = range(
                start_mapped,
                end_mapped + 1
            )
            self.endInsertRows()

            source = self.sourceModel()
            for new_i in range(start, end + 1):
                new_idx = source.index(new_i, 0, Qt.QModelIndex())
                nchildren = source.rowCount(new_idx)
                if nchildren == 0:
                    continue

                self._source_rowsInserted(new_idx, 0, nchildren - 1)

    def _source_rowsAboutToBeRemoved(self, parent, start, end):
        if self.mapFromSource(parent).parent().isValid():
            return

        if parent.isValid():
            mapped_parent = self.mapFromSource(parent)
            offset = mapped_parent.row() + 1
            start_mapped = start + offset
            end_mapped = end + offset
            new_children = (end - start) + 1
            self.beginRemoveRows(Qt.QModelIndex(), start_mapped, end_mapped)
            for i, old_break in enumerate(
                    self._breaks[start + 1:],
                    start + 1):  # update breaks *after* the newly inserted ones
                self._breaks[i] -= new_children
        else:
            # remove root item
            # find break for start index
            if start >= len(self._breaks):
                offset = self._len() - start
            else:
                offset = self._breaks[start] - start

            start_mapped = start + offset
            end_mapped = end + offset

            end_mapped_inlined = end_mapped
            source = self.sourceModel()
            for source_row in range(start, end + 1):
                source_idx = source.index(source_row, 0, parent)
                end_mapped_inlined += source.rowCount(source_idx)
            to_remove = (end_mapped_inlined - start_mapped) + 1

            self.beginRemoveRows(Qt.QModelIndex(), start_mapped,
                                 end_mapped_inlined)

            del self._breaks[start:end + 1]

            for i, old_break in enumerate(
                    self._breaks[start:],
                    start):  # update breaks *after* the newly inserted ones
                self._breaks[i] -= to_remove

    def _source_rowsRemoved(self, parent, start, end):
        if self.mapFromSource(parent).parent().isValid():
            return

        self.endRemoveRows()

    def _len(self):
        if not self._breaks:
            return 0
        return self._breaks[-1] + self.sourceModel().rowCount(
            self.sourceModel().index(
                len(self._breaks) - 1,
                0,
                Qt.QModelIndex()
            )
        ) + 1

    def rowCount(self, parent):
        if parent.isValid():
            return 0

        return self._len()

    def columnCount(self, parent):
        if not self.sourceModel():
            return 0
        return self.sourceModel().columnCount(self.mapToSource(parent))

    def index(self, row, column, parent):
        if parent.isValid():
            return Qt.QModelIndex()
        if not (0 <= row < self.rowCount(parent)):
            return Qt.QModelIndex()
        if not (0 <= column < self.columnCount(parent)):
            return Qt.QModelIndex()
        return super().createIndex(row, column, parent)

    def parent(self, index):
        return Qt.QModelIndex()

    def _map_firstlevel_to_source(self, proxyIndex):
        row = proxyIndex.row()
        # find the row in the breaks list
        mapping = bisect.bisect(self._breaks, row) - 1
        if self._breaks[mapping] == row:
            # first level in source
            return self.sourceModel().index(
                mapping,
                proxyIndex.column(),
            )
        else:
            # second level in source
            # find parent
            parent_idx = self.sourceModel().index(
                mapping,
                0,
            )
            child_row = (row - self._breaks[mapping]) - 1
            return self.sourceModel().index(
                child_row,
                0,
                parent_idx,
            )

    def mapFromSource(self, sourceIndex):
        parent = sourceIndex.parent()
        if not parent.isValid():  # root
            return self.index(
                self._breaks[sourceIndex.row()],
                sourceIndex.column(),
                Qt.QModelIndex(),
            )

        grandparent = parent.parent()
        if grandparent.isValid():
            # we don’t support grandchildren
            return Qt.QModelIndex()

        return self.index(
            self._breaks[parent.row()] + sourceIndex.row() + 1,
            sourceIndex.column(),
            Qt.QModelIndex(),
        )

    def mapToSource(self, proxyIndex):
        return self._map_firstlevel_to_source(proxyIndex)


class RosterModel(Qt.QAbstractListModel):
    on_label_edited = aioxmpp.callbacks.Signal()

    def __init__(self,
                 items: jclib.instrumentable_list.AbstractModelListView[
                     jclib.roster.AbstractRosterItem],
                 avatar_manager: jabbercat.avatar.AvatarManager):
        super().__init__()
        self._items = items
        self._avatar_manager = avatar_manager
        self._avatar_manager.on_avatar_changed.connect(
            self._on_avatar_changed,
            self._avatar_manager.on_avatar_changed.WEAK)
        self.__adaptor = model_adaptor.ModelListAdaptor(
            self._items, self
        )

    def flags(self, index):
        flags = super().flags(index)
        flags |= Qt.Qt.ItemIsEditable
        return flags

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role):
        if not index.isValid():
            return

        item = self._items[index.row()]

        if role == Qt.Qt.DisplayRole or role == Qt.Qt.EditRole:
            return item.label
        elif role == ROLE_OBJECT:
            return item
        elif role == ROLE_TAGS:
            return "".join(
                tag + "\n" for tag in sorted(item.tags)
            )

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        if role != Qt.Qt.EditRole:
            return False

        self.on_label_edited(self._items[index.row()], value)
        return False

    def _on_avatar_changed(self, account, address):
        for i, item in enumerate(self._items):
            if item.account != account or item.address != address:
                continue
            index = self.index(i, 0)
            self.dataChanged.emit(index, index, [Qt.Qt.DecorationRole])
            return


class RosterFilterModel(Qt.QSortFilterProxyModel):
    def __init__(self, parent: Qt.QObject=None):
        super().__init__(parent)

        self._tags_filter_model = None
        self._tags_filter_set = None
        self._tags_filter_set_connections = []
        self._filter_by_text = None

    @staticmethod
    def _normalize_for_find(s: str):
        return unicodedata.normalize("NFKC", s).casefold()

    @property
    def tags_filter_model(self):
        return self._tags_filter_model

    @tags_filter_model.setter
    def tags_filter_model(self, value: Qt.QAbstractItemModel):
        for signal, token in self._tags_filter_set_connections:
            signal.disconnect(token)
        self._tags_filter_set_connections.clear()

        self._tags_filter_model = value

        if self._tags_filter_model is not None:
            self._tags_filter_set = CheckModelSet(
                self._tags_filter_model,
                0, Qt.Qt.DisplayRole,
            )
            self._tags_filter_set_connections.append(
                (
                    self._tags_filter_set.on_changed,
                    self._tags_filter_set.on_changed.connect(
                        self._tags_set_changed,
                        self._tags_filter_set.on_changed.WEAK
                    )
                )
            )

        self.invalidateFilter()

    def _tags_set_changed(self):
        self.invalidateFilter()

    @property
    def filter_by_text(self):
        return self._filter_by_text

    @filter_by_text.setter
    def filter_by_text(self, value: str):
        self._filter_by_text = self._normalize_for_find(value)
        self.invalidateFilter()

    @filter_by_text.deleter
    def filter_by_text(self):
        self._filter_by_text = None

    def _contains_normalized(self, normed: str, other: str):
        return normed in self._normalize_for_find(other)

    def filterAcceptsRow(self,
                         source_row: int,
                         source_parent: Qt.QModelIndex):
        source = self.sourceModel()
        item = source.data(
            source.index(source_row, 0, source_parent), ROLE_OBJECT
        )

        if self._filter_by_text is not None:
            if (not self._contains_normalized(self._filter_by_text,
                                              str(item.address)) and
                    not self._contains_normalized(self._filter_by_text,
                                                  item.label)):
                return False

        filter_tags = self._tags_filter_set.checked
        if set(item.tags) & filter_tags != filter_tags:
            return False

        return True


class TagsModel(Qt.QAbstractListModel):
    def __init__(self,
                 model: jclib.instrumentable_list.AbstractModelListView[str],
                 parent: Qt.QObject = None):
        super().__init__()
        self._model = model
        self.__adaptor = model_adaptor.ModelListAdaptor(
            self._model, self
        )

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._model)

    def data(self,
             index: Qt.QModelIndex,
             role: int = Qt.Qt.DisplayRole):
        if not index.isValid():
            return None

        tag = self._model[index.row()]
        if role == Qt.Qt.DisplayRole or role == ROLE_OBJECT:
            return tag
        elif role == Qt.Qt.DecorationRole:
            return utils.text_to_qtcolor(
                jclib.utils.normalise_text_for_hash(tag)
            )


class CheckModel(Qt.QIdentityProxyModel):
    def __init__(self, parent: Qt.QObject = None):
        super().__init__(parent)
        self._checked_items = set()
        self.rowsAboutToBeRemoved.connect(self._begin_remove_rows)
        self._check_column = 0

    def _begin_remove_rows(self, parent, index1, index2):
        removed_objects = {
            self.data(self.index(i, self.check_column, parent), ROLE_OBJECT)
            for i in range(index1, index2 + 1)
        }
        self._checked_items -= removed_objects

    @property
    def check_column(self) -> int:
        """
        The column at which the check box is inserted.
        """
        return self._check_column

    @check_column.setter
    def check_column(self, value: int):
        self.beginResetModel()
        self._check_column = value
        self.endResetModel()

    @property
    def checked_items(self):
        """
        The ROLE_OBJECT data of each checked item as a set.
        """
        return self._checked_items

    def flags(self, index: Qt.QModelIndex):
        flags = super().flags(index)
        if index.column() == self.check_column:
            flags |= Qt.Qt.ItemIsUserCheckable
        return flags

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        if not index.isValid():
            return super().data(index, role)
        if role == Qt.Qt.CheckStateRole and index.column() == self.check_column:
            value = super().data(index, ROLE_OBJECT)
            return (Qt.Qt.Checked
                    if value in self._checked_items
                    else Qt.Qt.Unchecked)
        return super().data(index, role)

    def setData(self, index: Qt.QModelIndex, value, role: int = Qt.Qt.EditRole):
        if not index.isValid():
            return super().setData(index, value, role)
        if index.column() != self.check_column:
            return super().setData(index, value, role)
        if role != Qt.Qt.CheckStateRole:
            return super().setDate(index, value, role)

        if value == Qt.Qt.Checked:
            self._checked_items.add(self.data(index, ROLE_OBJECT))
        else:
            self._checked_items.discard(self.data(index, ROLE_OBJECT))

        self.dataChanged.emit(index, index, [Qt.Qt.CheckStateRole])

        return True

    def clear_check_states(self):
        self._checked_items.clear()
        self.dataChanged.emit(
            self.index(0, self._check_column),
            self.index(self.rowCount() - 1, self._check_column),
            [Qt.Qt.CheckStateRole],
        )


class CheckModelSet:
    on_changed = aioxmpp.callbacks.Signal()

    def __init__(self,
                 model: Qt.QAbstractItemModel,
                 check_column: int,
                 set_role: int,
                 set_column: int = None):
        super().__init__()
        self._model = model
        self._model.dataChanged.connect(self._data_changed)
        self._model.rowsInserted.connect(self._rows_inserted)
        self._model.rowsAboutToBeRemoved.connect(self._rows_about_to_be_removed)
        self._model.modelAboutToBeReset.connect(self._model_about_to_be_reset)
        self._model.modelReset.connect(self._model_reset)
        self._check_column = check_column
        self._set_role = set_role
        self._set_column = (set_column
                            if set_column is not None
                            else check_column)
        self._internal_set = set()
        self._model_reset()

    def _data_changed(self,
                      top_left: Qt.QModelIndex,
                      bottom_right: Qt.QModelIndex,
                      roles: typing.Iterable[int] = []):
        if roles and Qt.Qt.CheckStateRole not in roles:
            return
        if self._check_column not in range(top_left.column(),
                                           bottom_right.column() + 1):
            return
        for row in range(top_left.row(), bottom_right.row() + 1):
            checked = (
                self._model.data(self._model.index(row, self._check_column),
                                 Qt.Qt.CheckStateRole) == Qt.Qt.Checked
            )
            element = self._model.data(
                self._model.index(row, self._set_column),
                self._set_role
            )
            if checked:
                self._internal_set.add(element)
            else:
                self._internal_set.discard(element)
        self.on_changed()

    def _rows_inserted(self, parent, index1, index2):
        changed = False
        for row in range(index1, index2 + 1):
            check_index = self._model.index(row, self._check_column)
            if self._model.data(check_index,
                                Qt.Qt.CheckStateRole) != Qt.Qt.Checked:
                continue

            element_index = self._model.index(row, self._set_column)
            element = self._model.data(element_index, self._set_role)
            self._internal_set.add(element)
            changed = True

        if changed:
            self.on_changed()

    def _rows_about_to_be_removed(self, parent, index1, index2):
        changed = False
        for row in range(index1, index2 + 1):
            check_index = self._model.index(row, self._check_column)
            if self._model.data(check_index,
                                Qt.Qt.CheckStateRole) != Qt.Qt.Checked:
                continue

            element_index = self._model.index(row, self._set_column)
            element = self._model.data(element_index, self._set_role)
            self._internal_set.discard(element)
            changed = True
        if changed:
            self.on_changed()

    def _model_about_to_be_reset(self):
        self._internal_set.clear()

    def _model_reset(self):
        self._rows_inserted(None, 0, self._model.rowCount() - 1)
        self.on_changed()

    @property
    def checked(self) -> typing.Set:
        return self._internal_set
