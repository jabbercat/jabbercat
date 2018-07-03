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
        branch_opt.state = Qt.QStyle.State_Children
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

    def hitButton(self, pos):
        # deliberately skipping the QCheckBox implementation here
        return Qt.QAbstractButton.hitButton(self, pos)
