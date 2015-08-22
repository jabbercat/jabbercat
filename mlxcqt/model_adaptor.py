from . import Qt


class ModelListAdaptor:
    def __init__(self, mlist, model):
        super().__init__()
        self.model = model

        mlist.begin_insert_rows = self.begin_insert_rows
        mlist.end_insert_rows = self.end_insert_rows

        mlist.begin_remove_rows = self.begin_remove_rows
        mlist.end_remove_rows = self.end_remove_rows

        mlist.begin_move_rows = self.begin_move_rows
        mlist.end_move_rows = self.end_move_rows

    def begin_insert_rows(self, _, index1, index2):
        self.model.beginInsertRows(
            Qt.QModelIndex(),
            index1,
            index2
        )

    def end_insert_rows(self):
        self.model.endInsertRows()

    def begin_remove_rows(self, _, index1, index2):
        self.model.beginRemoveRows(
            Qt.QModelIndex(),
            index1,
            index2
        )

    def end_remove_rows(self):
        self.model.endRemoveRows()

    def begin_move_rows(self,
                        srcparent, srcindex1, srcindex2,
                        destparent, destindex):
        self.model.beginMoveRows(
            Qt.QModelIndex(),
            srcindex1,
            srcindex2,
            Qt.QModelIndex(),
            destindex
        )

    def end_move_rows(self):
        self.model.endMoveRows()


# class ListModel(Qt.QAbstractListModel):
#     def __init__(self, mlist, handler, *, parent=None):
#         super().__init__(parent)
#         self._mlist = mlist
#         self._handler = handler

#     def rowCount(self, parent_index):
#         return len(self._mlist)

#     def data(self, index, role):
#         if not index.isValid():
#             return None
#         row_index = index.row()
#         return self._handler.get_data(self._mlist[row_index], role)

#     def headerData(self, section, orientation, role):
#         return self._handler.get_header_data(section, orientation, role)
