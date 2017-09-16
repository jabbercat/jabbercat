import asyncio

from . import Qt, utils
from .ui.dlg_custom_presence_states import Ui_dlg_custom_presence_states
from .ui.dlg_edit_custom_presence import Ui_dlg_edit_custom_presence


class DlgCustomPresenceStates(Qt.QDialog, Ui_dlg_custom_presence_states):
    def __init__(self, main_window):
        super().__init__()
        self.jclib = main_window.jclib
        self.presence_states = self.jclib.client.presence_states
        self.presence_states_qmodel = self.jclib.client.presence_states_qmodel

        self.setupUi(self)
        self.setModal(False)

        self.model_wrapper = Qt.QSortFilterProxyModel(self)
        self.model_wrapper.setSourceModel(self.presence_states_qmodel)
        self.model_wrapper.setSortLocaleAware(True)
        self.model_wrapper.setSortCaseSensitivity(False)
        self.model_wrapper.setSortRole(Qt.Qt.DisplayRole)
        self.model_wrapper.setDynamicSortFilter(True)

        self.state_list.setModel(self.model_wrapper)
        self.state_list.sortByColumn(0, Qt.Qt.AscendingOrder)

        self.cps_add.setDefaultAction(self.action_add_new)
        self.cps_delete_selected.setDefaultAction(
            self.action_delete_selected
        )

        self.action_add_new.triggered.connect(
            self._on_add_new
        )

    @utils.asyncify
    @asyncio.coroutine
    def _on_add_new(self, checked):
        pass
