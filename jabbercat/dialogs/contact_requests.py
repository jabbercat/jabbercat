import asyncio
import enum

import jclib.roster
import jclib.tasks

from .. import Qt, models
from ..ui import dlg_contact_requests


class Filter(Qt.QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(
            source_row,
            models.ContactRequestModel.COLUMN_TYPE,
            source_parent,
        )

        return (
            index.data(models.ROLE_OBJECT) is not None and
            super().filterAcceptsRow(source_row, source_parent)
        )


class DlgContactRequests(Qt.QDialog):
    def __init__(self, roster, parent=None):
        super().__init__(parent)
        self.ui = dlg_contact_requests.Ui_DlgContactRequests()
        self.ui.setupUi(self)

        self._model = models.ContactRequestModel(roster)
        self._filtered_model = Filter()
        self._filtered_model.setSourceModel(self._model)
        self._filtered_model.setDynamicSortFilter(True)

        self.ui.requestsView.setModel(self._filtered_model)
        self.ui.requestsView.selectionModel().selectionChanged.connect(
            self._selection_changed
        )

        self.ui.btnDeny.clicked.connect(self._deny_triggered)
        self.ui.btnApprove.clicked.connect(self._approve_triggered)

    def showEvent(self, event: Qt.QShowEvent):
        self.ui.requestsView.resizeColumnsToContents()
        super().showEvent(event)

    def _selection_changed(self, selected, deselected):
        type_set = {
            self._filtered_model.data(
                selected,
                models.ROLE_OBJECT,
            )
            for selected in self.ui.requestsView.selectionModel().selectedRows(
                models.ContactRequestModel.COLUMN_TYPE,
            )
        }

        has_inbound = models.RequestType.INBOUND in type_set
        has_outbound = models.RequestType.OUTBOUND in type_set

        self.ui.btnDeny.setEnabled(has_inbound)
        self.ui.btnApprove.setEnabled(has_inbound)

        self.ui.btnResend.setEnabled(has_outbound)
        self.ui.btnRetract.setEnabled(has_outbound)

    def _deny_triggered(self, *args):
        items = [
            self._filtered_model.data(
                selected,
                models.ROLE_OBJECT
            )
            for selected in self.ui.requestsView.selectionModel(
            ).selectedRows(models.ContactRequestModel.COLUMN_LABEL)
            if self._filtered_model.data(selected.sibling(
                selected.row(),
                models.ContactRequestModel.COLUMN_TYPE
            ), models.ROLE_OBJECT) == models.RequestType.INBOUND
        ]

        jclib.tasks.manager.start(self._execute_approvedeny(items, False))

    def _approve_triggered(self, *args):
        items = [
            self._filtered_model.data(
                selected,
                models.ROLE_OBJECT
            )
            for selected in self.ui.requestsView.selectionModel(
            ).selectedRows(models.ContactRequestModel.COLUMN_LABEL)
            if self._filtered_model.data(selected.sibling(
                selected.row(),
                models.ContactRequestModel.COLUMN_TYPE
            ), models.ROLE_OBJECT) == models.RequestType.INBOUND
        ]

        jclib.tasks.manager.start(self._execute_approvedeny(items, True))

    @asyncio.coroutine
    def _execute_approvedeny(self, items, approve):
        if approve:
            template = "Denying {} contact request(s)"
            func = "approve"
        else:
            template = "Approving {} contact request(s)"
            func = "remove"

        jclib.tasks.manager.update_text(
            template.format(len(items))
        )

        yield from asyncio.gather(
            *(
                getattr(item.owner, func)(item)
                for item in items
            )
        )
