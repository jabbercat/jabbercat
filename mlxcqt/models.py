import bisect
import enum

import mlxc.identity
import mlxc.instrumentable_list

from . import Qt
from . import model_adaptor


ROLE_OBJECT = Qt.Qt.UserRole + 1


class AccountsModel(Qt.QAbstractTableModel):
    COLUMN_ADDRESS = 0
    COLUMN_ENABLED = 1
    COLUMN_COUNT = 2

    def __init__(self, accounts: mlxc.identity.Accounts):
        super().__init__()
        self.__accounts = accounts

        self.__accounts.begin_remove_rows.connect(self._begin_remove_rows)
        self.__accounts.end_remove_rows.connect(self._end_remove_rows)

        self.__accounts.begin_insert_rows.connect(self._begin_insert_rows)
        self.__accounts.end_insert_rows.connect(self._end_insert_rows)

        self.__accounts.data_changed.connect(self._data_changed)

    def _begin_remove_rows(self, _, index1, index2):
        self.beginRemoveRows(Qt.QModelIndex(), index1, index2)

    def _end_remove_rows(self):
        self.endRemoveRows()

    def _begin_insert_rows(self, _, index1, index2):
        self.beginInsertRows(Qt.QModelIndex(), index1, index2)

    def _end_insert_rows(self):
        self.endInsertRows()

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

    def data(self, index, role=Qt.Qt.DisplayRole):
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

    def setData(self, index, value, role=Qt.Qt.EditRole):
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

    def headerData(self, section, orientation, role=Qt.Qt.DisplayRole):
        if orientation != Qt.Qt.Horizontal:
            return None

        if role != Qt.Qt.DisplayRole:
            return None

        if section == self.COLUMN_ADDRESS:
            return self.tr("Address")
        elif section == self.COLUMN_ENABLED:
            return self.tr("Enabled")


class ConversationsModel(Qt.QAbstractItemModel):
    def __init__(self, tree):
        super().__init__()
        self.tree = tree
        self.tree.begin_insert_rows.connect(self._begin_insert_rows)
        self.tree.end_insert_rows.connect(self._end_insert_rows)

        self.tree.begin_remove_rows.connect(self._begin_remove_rows)
        self.tree.end_remove_rows.connect(self._end_remove_rows)

    def _begin_insert_rows(self, node, index1, index2):
        parent_mi = self.node_to_index(node)
        self.beginInsertRows(parent_mi, index1, index2)

    def _end_insert_rows(self):
        self.endInsertRows()

    def _begin_remove_rows(self, node, index1, index2):
        parent_mi = self.node_to_index(node)
        self.beginRemoveRows(parent_mi, index1, index2)

    def _end_remove_rows(self):
        self.endRemoveRows()

    def node_to_index(self, node, column=0):
        if node.parent is None:
            return Qt.QModelIndex()
        if not isinstance(node, mlxc.instrumentable_list.ModelTreeNode):
            node = node._node
        return self.createIndex(
            node.parent_index,
            column,
            node,
        )

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.tree.root)
        node = parent.internalPointer()
        return len(node)

    def columnCount(self, parent):
        return 1

    def _ident_data(self, node, column, role):
        if role == Qt.Qt.DisplayRole:
            return str(node.identity.name)

    def _conv_data(self, node, column, role):
        if role == Qt.Qt.DisplayRole:
            return str(node.conversation.jid)

    def data(self, index, role):
        if index.isValid():
            node = index.internalPointer()
        else:
            node = self.tree.root

        node = node.object_

        if isinstance(node, mlxc.conversation.ConversationIdentity):
            return self._ident_data(node, index.column(), role)
        elif isinstance(node, mlxc.conversation.ConversationNode):
            return self._conv_data(node, index.column(), role)

    def index(self, row, column, parent):
        parent = (self.tree.root
                  if not parent.isValid()
                  else parent.internalPointer())
        return self.node_to_index(parent[row], column)

    def parent(self, index):
        if not index.isValid():
            return Qt.QModelIndex()
        return self.node_to_index(index.internalPointer().parent)


class RosterTagsSelectionModel(Qt.QAbstractListModel):
    COLUMN_NAME = 0
    COLUMN_COUNT = 1

    def __init__(self, model_list, parent=None):
        super().__init__(parent=parent)
        self._model_list = model_list
        self._to_add = set()
        self._to_remove = set()
        self._original = {}
        self.__adaptor = model_adaptor.ModelListAdaptor(model_list, self)

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
            self.index(len(self._model_list)-1, 0),
            [Qt.Qt.CheckStateRole]
        )

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
        elif role == Qt.Qt.CheckStateRole:
            group = self._model_list[row]
            if group in self._to_add:
                return Qt.Qt.Checked
            elif group in self._to_remove:
                return Qt.Qt.Unchecked
            return self._original.get(group, Qt.Qt.Unchecked)

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
            AccountModel.COLUMN_ENABLED,
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
            i_absolute += nchildren+1

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
                    self._breaks[parent.row()+1:],
                    parent.row()+1):  # update breaks *after* the parent
                self._breaks[i] += new_children
            self.endInsertRows()
        else:
            # adding new root
            # find break for start index
            if start >= len(self._breaks):
                offset = self._len() - start
            else:
                offset = self._breaks[start+1] - start

            start_mapped = start + offset
            end_mapped = end + offset
            new_children = (end - start) + 1

            self.beginInsertRows(Qt.QModelIndex(), start_mapped, end_mapped)
            for i, old_break in enumerate(
                    self._breaks[start+1:],
                    start+1):  # update breaks *after* the newly inserted ones
                self._breaks[i] += new_children

            # insert new breaks
            self._breaks[start+1:start+1] = range(start_mapped, end_mapped+1)
            self.endInsertRows()

            source = self.sourceModel()
            for new_i in range(start, end+1):
                new_idx = source.index(new_i, 0, Qt.QModelIndex())
                nchildren = source.rowCount(new_idx)
                if nchildren == 0:
                    continue

                self._source_rowsInserted(new_idx, 0, nchildren-1)

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
                    self._breaks[start+1:],
                    start+1):  # update breaks *after* the newly inserted ones
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
            for source_row in range(start, end+1):
                source_idx = source.index(source_row, 0, parent)
                end_mapped_inlined += source.rowCount(source_idx)
            to_remove = (end_mapped_inlined - start_mapped) + 1

            self.beginRemoveRows(Qt.QModelIndex(), start_mapped,
                                 end_mapped_inlined)

            del self._breaks[start:end+1]

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
            self.sourceModel().index(len(self._breaks)-1, 0, Qt.QModelIndex())
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
        mapping = bisect.bisect(self._breaks, row)-1
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
