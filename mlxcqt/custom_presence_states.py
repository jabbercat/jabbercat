import asyncio

from . import Qt, utils
from .ui.dlg_custom_presence_states import Ui_dlg_custom_presence_states
from .ui.dlg_edit_custom_presence import Ui_dlg_edit_custom_presence


class DlgCustomPresenceStates(Qt.QDialog, Ui_dlg_custom_presence_states):
    def __init__(self, main_window):
        super().__init__()
        self.mlxc = main_window.mlxc
        self.presence_states = self.mlxc.client.presence_states
        self.presence_states_qmodel = self.mlxc.client.presence_states_qmodel

        self.setupUi(self)
        self.setModal(False)

        model_wrapper = Qt.QSortFilterProxyModel(self)
        model_wrapper.setSourceModel(self.presence_states_qmodel)
        model_wrapper.setSortLocaleAware(True)
        model_wrapper.setSortCaseSensitivity(False)
        model_wrapper.setSortRole(Qt.Qt.DisplayRole)
        model_wrapper.setDynamicSortFilter(True)

        self.state_list.setModel(model_wrapper)
        self.state_list.sortByColumn(0, Qt.Qt.AscendingOrder)
