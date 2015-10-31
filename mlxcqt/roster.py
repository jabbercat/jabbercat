import mlxc.roster

from . import Qt


class NodeView:
    def __init__(self, node):
        super().__init__()
        self.node = node

    def data(self, column, role):
        if role == Qt.Qt.DisplayRole and column == 0:
            return self.node.label


class ViaView(NodeView):
    pass

mlxc.roster.Via.attach_view(ViaView)


class MetaContactView(NodeView):
    pass

mlxc.roster.MetaContact.attach_view(MetaContactView)


class GroupView(NodeView):
    pass

mlxc.roster.Group.attach_view(GroupView)


class RosterTreeModel(Qt.QAbstractItemModel):
    def __init__(self, tree, parent=None):
        super().__init__(parent=parent)
        self._tree = tree
        self._tree.begin_insert_rows = self.begin_insert_rows
        self._tree.begin_move_rows = self.begin_move_rows
        self._tree.begin_remove_rows = self.begin_remove_rows
        self._tree.end_insert_rows = self.end_insert_rows
        self._tree.end_move_rows = self.end_move_rows
        self._tree.end_remove_rows = self.end_remove_rows

    def _mkindex(self, item, column=0):
        if item is self._tree.root:
            return Qt.QModelIndex()
        return self.createIndex(
            item.index_at_parent,
            column,
            item)

    def begin_insert_rows(self, item, index1, index2):
        self.beginInsertRows(
            self._mkindex(item),
            index1, index2)

    def begin_move_rows(self,
                        srcitem, srcindex1, srcindex2,
                        destitem, destindex):
        self.beginMoveRows(
            self._mkindex(srcitem),
            srcindex1, srcindex2,
            self._mkindex(destitem),
            destindex)

    def begin_remove_rows(self, item, index1, index2):
        self.beginRemoveRows(
            self._mkindex(item),
            index1, index2)

    def end_insert_rows(self):
        self.endInsertRows()

    def end_move_rows(self):
        self.endMoveRows()

    def end_remove_rows(self):
        self.endRemoveRows()

    def rowCount(self, index):
        if not index.isValid():
            return len(self._tree.root)

        item = index.internalPointer()
        if isinstance(item, mlxc.roster.Container):
            return len(item)
        return 0

    def index(self, row, column, parent=Qt.QModelIndex()):
        if not parent.isValid():
            try:
                return self.createIndex(row, column, self._tree.root[row])
            except IndexError:
                return Qt.QModelIndex()

        parent_object = parent.internalPointer()
        if not isinstance(parent_object, mlxc.roster.Container):
            return Qt.QModelIndex()

        try:
            return self.createIndex(row, column, parent_object[row])
        except IndexError:
            return Qt.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return index

        item = index.internalPointer()
        return self._mkindex(item.parent, index.column())

    def columnCount(self, index):
        return 1

    def data(self, index, role=Qt.Qt.DisplayRole):
        item = index.internalPointer()
        try:
            view = item.view
        except AttributeError:
            if role == Qt.Qt.DisplayRole:
                return "unknown item"
            return None

        return view.data(index.column(), role)
