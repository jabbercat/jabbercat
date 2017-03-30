import PyQt5.Qt as Qt

import mlxc.instrumentable_list


class AccountModel(Qt.QAbstractItemModel):
    COLUMN_NAME = 0
    COLUMN_ENABLED = 1
    COLUMN_COUNT = 2

    def __init__(self, tree, identities=None):
        super().__init__()
        self.tree = tree
        self.identities = identities
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
        return self.COLUMN_COUNT

    def index(self, row, column, parent):
        parent = (self.tree.root
                  if not parent.isValid()
                  else parent.internalPointer())
        if not (0 <= row < len(parent)):
            return Qt.QModelIndex()
        return self.node_to_index(parent[row], column)

    def parent(self, index):
        if not index.isValid():
            return Qt.QModelIndex()
        return self.node_to_index(index.internalPointer().parent)

    def _data_account(self, obj, column, role):
        if role == Qt.Qt.DisplayRole or role == Qt.Qt.EditRole:
            return {
                self.COLUMN_NAME: str(obj.jid),
            }.get(column)
        elif role == Qt.Qt.CheckStateRole:
            if column == self.COLUMN_ENABLED:
                if obj.enabled:
                    return Qt.Qt.Checked
                else:
                    return Qt.Qt.Unchecked

    def _data_identity(self, obj, column, role):
        if role == Qt.Qt.DisplayRole or role == Qt.Qt.EditRole:
            return {
                self.COLUMN_NAME: obj.name,
            }.get(column)
        elif role == Qt.Qt.CheckStateRole:
            if column == 1:
                if obj.enabled:
                    return Qt.Qt.Checked
                else:
                    return Qt.Qt.Unchecked

    def headerData(self, section, orientation, role):
        if orientation != Qt.Qt.Horizontal:
            return
        if role != Qt.Qt.DisplayRole:
            return
        return {
            self.COLUMN_NAME: "Name",
            self.COLUMN_ENABLED: "Enabled",
        }.get(section)

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 1:
            flags |= Qt.Qt.ItemIsUserCheckable
        return flags

    def data(self, index, role):
        if not index.isValid():
            return

        node = index.internalPointer()
        column = index.column()
        object_ = node.object_
        if isinstance(object_, mlxc.identity.Identity):
            result = self._data_identity(object_, column, role)
        elif isinstance(object_, mlxc.identity.Account):
            result = self._data_account(object_, column, role)
        else:
            result = None
        return result

    def setData(self, index, value, role):
        if self.identities is None:
            return False
        if role != Qt.Qt.CheckStateRole:
            return False
        if index.column() != self.COLUMN_ENABLED:
            return False

        checked = value == Qt.Qt.Checked
        object_ = index.internalPointer().object_
        if isinstance(object_, mlxc.identity.Identity):
            self.identities.set_identity_enabled(object_, checked)
            return True
        elif isinstance(object_, mlxc.identity.Account):
            self.identities.set_account_enabled(object_, checked)
            return True

        return False


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
            return str(node.conversation.peer_jid)

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
