import mlxc.instrumentable_list

from .. import models, Qt
from ..ui import roster_tags_box


class RosterTagsBox(Qt.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = roster_tags_box.Ui_RosterTagsBox()
        self.ui.setupUi(self)

        self.ui.tag_input.textChanged.connect(
            self._tag_input_changed
        )
        self.ui.tag_input.returnPressed.connect(
            self._tag_input_return_pressed
        )

        self._proxy_model = Qt.QSortFilterProxyModel()
        self._proxy_model.setSortRole(Qt.Qt.DisplayRole)
        self._proxy_model.setSortCaseSensitivity(False)
        self._proxy_model.setSortLocaleAware(True)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.sort(0, Qt.Qt.AscendingOrder)
        self._proxy_model.setFilterRole(Qt.Qt.DisplayRole)
        self._proxy_model.setFilterCaseSensitivity(False)

        self._model = None

        self.ui.tag_view.setModel(self._proxy_model)

    def setup(self, all_groups, item_groups):
        if self._model:
            self._proxy_model.setSourceModel(None)
            del self._model, self._all_groups_model
        self._all_groups_model = mlxc.instrumentable_list.ModelList(all_groups)
        self._model = models.RosterTagsSelectionModel(self._all_groups_model)
        self._model.setup(item_groups)
        self._proxy_model.setSourceModel(self._model)

    def _tag_input_changed(self, new_text):
        self._proxy_model.setFilterRegExp(
            Qt.QRegExp(new_text, Qt.Qt.CaseInsensitive,
                       Qt.QRegExp.FixedString)
        )

    def _tag_input_return_pressed(self):
        group = self.ui.tag_input.text().strip()
        self.ui.tag_input.setText("")
        if group and group not in self._all_groups_model:
            self._all_groups_model.append(group)
            self._model.select_group(group)

    def get_diff(self):
        return self._model._to_add, self._model._to_remove
