import functools
import typing

from .. import Qt


def _color_icon(color: Qt.QColor):
    pixmap = Qt.QPixmap(16, 16)
    pixmap.fill(color)
    return Qt.QIcon(pixmap)


class TagsMenu(Qt.QMenu):
    TAGS_OFFSET = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_model = None
        self._check_column = 0

    def _action_triggered(self, action: Qt.QAction, checked: bool = False):
        row = self.actions().index(action) - self.TAGS_OFFSET
        index = self._source_model.index(row, self._check_column)
        applied = self._source_model.setData(
            index,
            Qt.Qt.Checked if checked else Qt.Qt.Unchecked,
            Qt.Qt.CheckStateRole,
        )
        if not applied:
            value = self._source_model.data(
                index,
                Qt.Qt.CheckStateRole,
            )
            action.setChecked(value == Qt.Qt.Checked)

    def _begin_reset_model(self):
        self.clear()
        self.addSection(self.tr("Tags"))

    def _make_action(self, source_index: Qt.QModelIndex):
        label = self._source_model.data(source_index, Qt.Qt.DisplayRole)
        color = self._source_model.data(source_index, Qt.Qt.DecorationRole)
        action = Qt.QAction(self)
        action.setText(label)
        action.setIcon(_color_icon(color))
        action.setCheckable(True)
        action.triggered.connect(functools.partial(
            self._action_triggered,
            action
        ))
        return action

    def _end_reset_model(self):
        if self._source_model is None:
            return
        new_actions = [
            self._make_action(self._source_model.index(i, self._check_column))
            for i in range(self._source_model.rowCount())
        ]
        self.addActions(new_actions)

    def _data_changed(self,
                      top_left: Qt.QModelIndex,
                      bottom_right: Qt.QModelIndex,
                      roles: typing.Sequence[int] = []):
        if roles and Qt.Qt.CheckStateRole not in roles:
            return
        columns = range(top_left.column(), bottom_right.column() + 1)
        if self._check_column not in columns:
            return
        actions = self.actions()
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self._source_model.index(row, self._check_column)
            action = actions[self.TAGS_OFFSET + row]
            action.setChecked(
                self._source_model.data(
                    index,
                    Qt.Qt.CheckStateRole
                ) == Qt.Qt.Checked
            )

    def _rows_about_to_be_removed(self, parent, index1, index2):
        if parent.isValid():
            return
        actions = list(self.actions())
        for row in range(index1, index2 + 1):
            self.removeAction(actions[row + self.TAGS_OFFSET])

    def _rows_inserted(self, parent, index1, index2):
        if parent.isValid():
            return
        new_actions = [
            self._make_action(self._source_model.index(i, self._check_column))
            for i in range(index1, index2 + 1)
        ]
        actions = self.actions()
        mapped_index1 = index1 + self.TAGS_OFFSET
        if mapped_index1 == len(actions):
            self.addActions(new_actions)
        else:
            self.insertActions(actions[mapped_index1], new_actions)

    def _rows_about_to_be_moved(self, src_parent, src_index1, src_index2,
                                dest_parent, dest_index):
        self._begin_reset_model()

    def _rows_moved(self, src_parent, src_index1, src_index2,
                    dest_parent, dest_index):
        self._end_reset_model()

    @property
    def source_model(self):
        return self._source_model

    @source_model.setter
    def source_model(self, model: Qt.QAbstractItemModel):
        self._begin_reset_model()
        if self._source_model is not None:
            self._source_model.modelAboutToBeReset.disconnect(
                self._begin_reset_model
            )
            self._source_model.modelReset.disconnect(
                self._end_reset_model
            )
            self._source_model.dataChanged.disconnect(
                self._data_changed
            )
            self._source_model.rowsAboutToBeRemoved.disconnect(
                self._rows_about_to_be_removed,
            )
            self._source_model.rowsInserted.disconnect(
                self._rows_inserted,
            )
            self._source_model.rowsAboutToBeMoved.disconnect(
                self._rows_about_to_be_moved,
            )
            self._source_model.rowsMoved.disconnect(
                self._rows_moved,
            )
        self._source_model = model
        if self._source_model is not None:
            self._source_model.modelAboutToBeReset.connect(
                self._begin_reset_model
            )
            self._source_model.modelReset.connect(
                self._end_reset_model
            )
            self._source_model.dataChanged.connect(
                self._data_changed
            )
            self._source_model.rowsAboutToBeRemoved.connect(
                self._rows_about_to_be_removed,
            )
            self._source_model.rowsInserted.connect(
                self._rows_inserted,
            )
            self._source_model.rowsAboutToBeMoved.connect(
                self._rows_about_to_be_moved,
            )
            self._source_model.rowsMoved.connect(
                self._rows_moved,
            )
        self._end_reset_model()

