import asyncio
import bisect
import contextlib
import functools
import random

import aioxmpp.structs

from . import Qt, model_adaptor


def asyncified_done(task):
    task.result()


def asyncified_unblock(dlg, cursor, task):
    dlg.setCursor(cursor)
    dlg.setEnabled(True)


def asyncify(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        task = asyncio.async(fn(*args, **kwargs))
        task.add_done_callback(asyncified_done)
    return wrapper


def asyncify_blocking(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        prev_cursor = self.cursor()
        self.setEnabled(False)
        self.setCursor(Qt.Qt.WaitCursor)
        try:
            task = asyncio.async(fn(self, *args, **kwargs))
        except:
            self.setEnabled(True)
            self.setCursor(prev_cursor)
            raise
        task.add_done_callback(asyncified_done)
        task.add_done_callback(functools.partial(
            asyncified_unblock,
            self, prev_cursor))

    return wrapper


@contextlib.contextmanager
def block_widget(widget):
    prev_cursor = widget.cursor()
    widget.setEnabled(False)
    widget.setCursor(Qt.Qt.WaitCursor)
    try:
        yield
    finally:
        widget.setCursor(prev_cursor)
        widget.setEnabled(True)


@asyncio.coroutine
def block_widget_for_coro(widget, coro):
    with block_widget(widget):
        yield from coro


@asyncio.coroutine
def exec_async(dlg, set_modal=Qt.Qt.WindowModal):
    future = asyncio.Future()
    def done(result):
        nonlocal future
        future.set_result(result)
    dlg.finished.connect(done)
    if set_modal is not None:
        dlg.windowModality = set_modal
    dlg.show()
    try:
        return (yield from future)
    except asyncio.CancelledError:
        print("being cancelled, rejecting dialogue and re-raising")
        dlg.finished.disconnect(done)
        dlg.reject()
        raise


class JoinedListsModel(Qt.QAbstractListModel):
    def __init__(self, *models, parent=None):
        super().__init__(parent=parent)
        self._models = tuple(models)
        self._reset()
        for model in self._models:
            self._link_model(model)

    def _link_model(self, model):
        model.rowsInserted.connect(self._rowsInserted)
        model.rowsMoved.connect(self._rowsMoved)
        model.rowsRemoved.connect(self._rowsRemoved)
        model.columnsInserted.connect(self._columnsInserted)
        model.columnsMoved.connect(self._columnsMoved)
        model.columnsRemoved.connect(self._columnsRemoved)
        model.modelAboutToBeReset.connect(self._modelAboutToBeReset)
        model.modelReset.connect(self._modelReset)
        model.rowsAboutToBeInserted.connect(functools.partial(
            self._rowsAboutToBeInserted,
            model
        ))
        model.rowsAboutToBeMoved.connect(functools.partial(
            self._rowsAboutToBeMoved,
            model
        ))
        model.rowsAboutToBeRemoved.connect(functools.partial(
            self._rowsAboutToBeRemoved,
            model
        ))

    def _rowsInserted(self):
        self.endInsertRows()

    def _rowsMoved(self):
        self.endMoveRows()

    def _rowsRemoved(self):
        self.endRemoveRows()

    def _columnsInserted(self):
        self.endInsertColumns()

    def _columnsMoved(self):
        self.endMoveColumns()

    def _columnsRemoved(self):
        self.endRemoveColumns()

    def _modelAboutToBeReset(self):
        self.beginResetModel()
        self._mapping.clear()

    def _modelReset(self):
        self._reset()
        self.endResetModel()

    def _rowsAboutToBeInserted(self, model, index, start, end):
        modeli = self._models.index(model)
        offset = self._mapping[modeli]
        self.beginInsertRows(index, start+offset, end+offset)
        added_rows = (end - start)+1
        for i in range(modeli+1, len(self._models)):
            self._mapping[i] += added_rows
        self._row_count += added_rows

    def _rowsAboutToBeMoved(self, model,
                            src_index, start, end,
                            dst_index, child):
        modeli = self._models.index(model)
        offset = self._mapping[modeli]
        self.beginMoveRows(src_index, start+offset, end+offset,
                           dst_index, child+offset)

    def _rowsAboutToBeRemoved(self, model, index, start, end):
        modeli = self._models.index(model)
        offset = self._mapping[modeli]
        self.beginRemoveRows(index, start+offset, end+offset)
        removed_rows = (end - start)+1
        for i in range(modeli+1, len(self._models)):
            self._mapping[i] -= removed_rows
        self._row_count -= removed_rows

    def _reset(self):
        mapping = [None]*len(self._models)
        offset = 0
        for i, model in enumerate(self._models):
            mapping[i] = offset
            offset += model.rowCount()
        self._row_count = offset
        self._mapping = mapping

    def _map_to_model(self, index):
        modeli = bisect.bisect(self._mapping, index.row())-1
        model = self._models[modeli]
        model_offset = self._mapping[modeli]
        return model, model_offset

    def rowCount(self, index=Qt.QModelIndex()):
        if not index.isValid():
            return self._row_count
        return 0

    def data(self, index, role=Qt.Qt.DisplayRole):
        model, offset = self._map_to_model(index)
        return model.data(
            model.index(
                index.row()-offset,
                index.column()),
            role)

    def flags(self, index):
        model, offset = self._map_to_model(index)
        return model.flags(
            model.index(index.row()-offset, index.column())
        )


class DictItemModel(Qt.QAbstractListModel):
    def __init__(self, items, parent=None):
        super().__init__(parent=parent)
        self._items = items
        self._adaptor = model_adaptor.ModelListAdaptor(
            items,
            self
        )

    def rowCount(self, index=Qt.QModelIndex()):
        if index.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=Qt.Qt.DisplayRole):
        return self._items[index.row()].get(role)

    def flags(self, index):
        return self._items[index.row()].get(
            "flags",
            Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled)


class JIDValidator(Qt.QValidator):
    def validate(self, text, pos):
        try:
            jid = aioxmpp.structs.JID.fromstr(text)
            return (Qt.QValidator.Acceptable, text, pos)
        except ValueError:
            # explicitly allow partial jids, i.e. those with empty localpart or
            # resource
            if     (text.endswith("@") or
                    text.startswith("@") or
                    text.endswith("/") or
                    text.startswith("/")):
                return (Qt.QValidator.Intermediate, text, pos)
            return (Qt.QValidator.Invalid, text, pos)


_dragndrop_rng = random.SystemRandom()
_dragndrop_state = None, None

DRAG_MIME_TYPE = "application/vnd.net.zombofant.mlxc.drag-key"


def start_drag(data):
    global _dragndrop_state
    key = _dragndrop_rng.getrandbits(64).to_bytes(8, 'little')
    _dragndrop_state = key, data
    return key


def pop_drag(key):
    global _dragndrop_state
    stored_key, stored_data = _dragndrop_state
    _dragndrop_state = None, None
    if stored_key != key:
        return None

    return stored_data


def get_drag(key):
    global _dragndrop_state
    stored_key, stored_data = _dragndrop_state
    if stored_key != key:
        return None

    return stored_data
