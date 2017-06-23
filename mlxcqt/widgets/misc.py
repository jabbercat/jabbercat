import mlxc.identity

from .. import Qt, models


class PlaceholderTreeView(Qt.QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__placeholder_text = ""

    @property
    def placeholder_text(self):
        return self.__placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, value):
        self.__placeholder_text = value
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.placeholder_text:
            return

        model = self.model()
        if model is not None and model.rowCount(self.rootIndex()) > 0:
            return

        p = Qt.QPainter(self.viewport())
        p.drawText(self.rect(), Qt.Qt.AlignCenter, self.placeholder_text)


# from <https://stackoverflow.com/a/27172161/1248008>
class TreeComboBox(Qt.QComboBox):
    def __init__(self, *args):
        super().__init__(*args)

        self.__skip_next_hide = False

        tree_view = Qt.QTreeView(self)
        tree_view.setFrameShape(Qt.QFrame.NoFrame)
        tree_view.setEditTriggers(tree_view.NoEditTriggers)
        tree_view.setAlternatingRowColors(True)
        tree_view.setSelectionBehavior(tree_view.SelectRows)
        tree_view.setWordWrap(True)
        tree_view.setAllColumnsShowFocus(True)
        self.setView(tree_view)

        self.view().viewport().installEventFilter(self)

    def showPopup(self):
        self.setRootModelIndex(Qt.QModelIndex())
        super().showPopup()

    def hidePopup(self):
        self.setRootModelIndex(self.view().currentIndex().parent())
        self.setCurrentIndex(self.view().currentIndex().row())
        if self.__skip_next_hide:
            self.__skip_next_hide = False
        else:
            super().hidePopup()

    def selectIndex(self, index):
        self.setRootModelIndex(index.parent())
        self.setCurrentIndex(index.row())

    def currentModelIndex(self):
        return self.model().index(
            self.currentIndex(),
            0,
            self.rootModelIndex(),
        )

    def eventFilter(self, object, event):
        if event.type() == Qt.QEvent.MouseButtonPress and object is self.view().viewport():
            index = self.view().indexAt(event.pos())
            self.__skip_next_hide = not self.view().visualRect(index).contains(event.pos())
        return False


class AccountSelectorBox(TreeComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setInsertPolicy(Qt.QComboBox.NoInsert)
        self.view().header().hide()

        self._account_index = None

        self.currentIndexChanged.connect(
            self._selected_account_changed
        )

    def _selected_account_changed(self, *args, **kwargs):
        new_index = self.currentModelIndex()
        if not new_index.isValid():
            if self._account_index and not self._account_index.isValid():
                self._account_index = None
                self.currentAccountChanged.emit()
            return
        if not isinstance(new_index.data(models.AccountModel.ROLE_OBJECT),
                          mlxc.identity.Account):
            return
        new_index = Qt.QPersistentModelIndex(new_index)
        if new_index != self._account_index:
            self._account_index = new_index
            self.currentAccountChanged.emit()

    def setModel(self, model):
        super().setModel(model)
        self.view().setColumnHidden(
            models.AccountModel.COLUMN_ENABLED,
            True,
        )
        self.view().expandAll()

        # find first selectable
        model = self.model()
        for i in range(model.rowCount(Qt.QModelIndex())):
            identity_index = model.index(i, 0, Qt.QModelIndex())
            if model.rowCount(identity_index) > 0:
                account_index = model.index(
                    0, 0,
                    identity_index
                )
                break
        else:
            account_index = Qt.QModelIndex()

        self._account_index = None

        if account_index.isValid():
            self.selectIndex(account_index)

    def currentAccount(self):
        if not self._account_index or not self._account_index.isValid():
            return None
        return self.model().data(
            Qt.QModelIndex(self._account_index),
            models.AccountModel.ROLE_OBJECT,
        )

    currentAccountChanged = Qt.pyqtSignal()
