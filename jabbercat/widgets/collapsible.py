from .. import Qt


class FancySpacer(Qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundRole(Qt.QPalette.Base)
        self.setAutoFillBackground(True)

    def sizeHint(self):
        return Qt.QSize(0, 0)


class CollapsibleButton(Qt.QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundRole(Qt.QPalette.Base)
        self.setAutoFillBackground(True)

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        style = self.style()

        check_opt = Qt.QStyleOptionButton()
        check_opt.initFrom(self)

        indicator_rect = style.subElementRect(
            Qt.QStyle.SE_CheckBoxIndicator,
            check_opt,
            None,
        )

        text_rect = style.subElementRect(
            Qt.QStyle.SE_CheckBoxContents,
            check_opt,
            None,
        )

        branch_opt = Qt.QStyleOption()
        branch_opt.initFrom(self)
        branch_opt.state = Qt.QStyle.State_Children | Qt.QStyle.State_Sibling
        if self.checkState() == Qt.Qt.Checked:
            branch_opt.state |= Qt.QStyle.State_Open
        branch_opt.rect = indicator_rect

        self.style().drawPrimitive(
            Qt.QStyle.PE_IndicatorBranch,
            branch_opt,
            painter,
        )

        check_opt.rect = text_rect
        check_opt.text = self.text()

        self.style().drawControl(
            Qt.QStyle.CE_CheckBoxLabel,
            check_opt,
            painter,
        )


class Collapsible(Qt.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._button = CollapsibleButton(self)
        self._button.clicked.connect(self._update_widget)
        self.setLayout(Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom))
        layout = self.layout()
        layout.addWidget(self._button)
        layout.setContentsMargins(0, 0, 0, 0)

        self._widget = None

    @Qt.pyqtProperty(str)
    def label(self) -> str:
        return self._button.text()

    @label.setter
    def label(self, value):
        self._button.setText(value)

    def _update_widget(self, checked=False):
        if self._widget is None:
            return

        if self._button.checkState() == Qt.Qt.Checked:
            self._widget.show()
        else:
            self._widget.hide()

    def setWidget(self, widget):
        if self._widget is not None:
            self.layout().removeWidget(self._widget)
        self._widget = widget
        if self._widget is not None:
            self.layout().addWidget(self._widget)
        self._update_widget()
