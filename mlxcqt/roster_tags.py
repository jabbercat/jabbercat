import asyncio

import aioxmpp

import mlxc.instrumentable_list

from mlxc.client import RosterGroups
from .ui import roster_tags

from . import Qt, models


class RosterTagsPopup(Qt.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = roster_tags.Ui_RosterTagsPopup()
        self.ui.setupUi(self)
        self.ui.tag_input.textChanged.connect(
            self._tag_input_changed
        )
        self.ui.tag_input.returnPressed.connect(
            self._tag_input_return_pressed
        )
        self.ui.buttons.accepted.connect(
            self._accept,
        )
        self.ui.buttons.rejected.connect(
            self._reject,
        )

    def _accept(self):
        self._conclude(True)
        self.close()

    def _reject(self):
        self._conclude(False)
        self.close()

    def _tag_input_changed(self, new_text):
        self.proxied_model.setFilterRegExp(
            Qt.QRegExp(new_text, Qt.Qt.CaseInsensitive,
                       Qt.QRegExp.FixedString)
        )

    def _tag_input_return_pressed(self):
        group = self.ui.tag_input.text().strip()
        self.ui.tag_input.setText("")
        if group and group not in self.all_groups:
            self.all_groups.append(group)
            self.model.select_group(group)

    @asyncio.coroutine
    def run(self, pos, all_groups, roster_items):
        assert not hasattr(self, "_future")
        self._future = asyncio.Future()
        try:
            self.all_groups = mlxc.instrumentable_list.ModelList(all_groups)
            self.model = models.RosterTagsSelectionModel(self.all_groups)
            self.model.setup([item.groups for item in roster_items])
            self.proxied_model = Qt.QSortFilterProxyModel()
            self.proxied_model.setSourceModel(self.model)
            self.proxied_model.setSortRole(Qt.Qt.DisplayRole)
            self.proxied_model.setSortCaseSensitivity(False)
            self.proxied_model.setSortLocaleAware(True)
            self.proxied_model.setDynamicSortFilter(True)
            self.proxied_model.sort(0, Qt.Qt.AscendingOrder)
            self.proxied_model.setFilterRole(Qt.Qt.DisplayRole)
            self.proxied_model.setFilterCaseSensitivity(False)
            self.ui.tag_view.setModel(self.proxied_model)
            self.setWindowFlags(Qt.Qt.Popup)
            self.move(pos)
            self.show()
            if not (yield from self._future):
                return None
            return self.model._to_add, self.model._to_remove
        finally:
            try:
                del self.all_groups
                del self.model
                del self.proxied_model
            except AttributeError:
                pass
            del self._future

    def _conclude(self, code):
        if self._future.done():
            return
        self._future.set_result(code)

    def keyPressEvent(self, event):
        if event.key() == Qt.Qt.Key_Escape:
            self._conclude(False)
        return super().keyPressEvent(event)

    def closeEvent(self, event):
        self._conclude(True)
        return super().closeEvent(event)
