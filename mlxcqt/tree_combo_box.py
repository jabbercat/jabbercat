from . import Qt

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
        print(self.currentIndex(), self.rootModelIndex().isValid(),
              self.rootModelIndex().row())
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
