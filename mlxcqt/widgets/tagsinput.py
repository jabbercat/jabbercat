import functools

import aioxmpp.callbacks

import mlxc.utils

from .. import Qt, utils
from ..ui import tags_input, tag_bubble


class TagButton(Qt.QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._hover = False

    def sizeHint(self):
        metrics = Qt.QFontMetrics(self.font())
        return Qt.QSize(metrics.ascent(), metrics.ascent())

    def minimumSizeHint(self):
        metrics = Qt.QFontMetrics(self.font())
        return Qt.QSize(metrics.ascent(), metrics.ascent())

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)

        color = self.palette().color(self.foregroundRole())
        if self._hover:
            color.setHslF(
                color.hueF(),
                color.saturationF(),
                1 - color.lightnessF()
            )

        painter.setPen(
            Qt.QPen(
                Qt.QBrush(color),
                1,
            )
        )

        size = self.size()
        base_size = min(size.width(), size.height())
        margin = base_size * 0.8

        painter.drawLine(
            Qt.QPointF(margin, margin),
            Qt.QPointF(base_size - margin, base_size - margin),
        )

        painter.drawLine(
            Qt.QPointF(margin, base_size - margin),
            Qt.QPointF(base_size - margin, margin),
        )

    def enterEvent(self, event: Qt.QEvent):
        self._hover = True
        self.repaint()
        return super().enterEvent(event)

    def leaveEvent(self, event: Qt.QEvent):
        self._hover = False
        self.repaint()
        return super().leaveEvent(event)


class TagBubble(Qt.QWidget):
    on_delete = aioxmpp.callbacks.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._ui = tag_bubble.Ui_TagBubble()
        self._ui.setupUi(self)
        self._palette = Qt.QPalette(self.palette())
        self.setBackgroundRole(Qt.QPalette.Window)
        self.setForegroundRole(Qt.QPalette.WindowText)
        self._delete_button = TagButton(self)
        self._delete_button.clicked.connect(self._delete_button_clicked)
        self._ui.horizontalLayout.addWidget(self._delete_button)
        self._update_font()

    def _delete_button_clicked(self, *args, **kwargs):
        self.on_delete()

    def _update_font(self):
        base = self.font()
        f = Qt.QFont(base)
        f.setPointSizeF(base.pointSizeF() * 0.9)
        self._ui.label.setFont(f)
        self._delete_button.setFont(f)

    def event(self, event: Qt.QEvent):
        if event.type() == Qt.QEvent.FontChange:
            self._update_font()
        return super().event(event)

    @property
    def text(self):
        return self._ui.label.text()

    @text.setter
    def text(self, text):
        self._ui.label.setText(text)
        color = utils.text_to_qtcolor(
            mlxc.utils.normalise_text_for_hash(text)
        )
        self._palette.setColor(Qt.QPalette.Window, color)
        self.setPalette(self._palette)

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        painter.setPen(Qt.Qt.NoPen)
        painter.setBrush(self.palette().color(self.backgroundRole()))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 2, 2)


class TagTextInput(Qt.QLineEdit):
    pass


class TagsInput(Qt.QFrame):
    on_tags_changed = aioxmpp.callbacks.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._ui = tags_input.Ui_TagsInputFrame()
        self._ui.setupUi(self)
        self._tag_bubbles = []
        self._tags = {}
        self.setBackgroundRole(Qt.QPalette.Base)
        self.setForegroundRole(Qt.QPalette.Text)

    def _remove_bubble(self, bubble):
        index = self._tag_bubbles.index(bubble)
        del self._tag_bubbles[index]
        del self._tags[bubble.text]
        self._ui.horizontalLayout.removeWidget(bubble)
        self.children().remove(bubble)
        bubble.setParent(None)
        self.on_tags_changed()
        return True

    def _add_bubble(self, text):
        bubble = TagBubble()
        bubble.text = text
        bubble.on_delete.connect(
            functools.partial(self._remove_bubble, bubble)
        )
        self._ui.horizontalLayout.insertWidget(len(self._tag_bubbles), bubble)
        self._tag_bubbles.append(bubble)
        self._tags[text] = bubble
        self.on_tags_changed()

    def add_tag(self, tag):
        if tag in self._tags:
            return
        self._add_bubble(tag)

    def remove_tag(self, tag):
        self._remove_bubble(self._tags[tag])

    def has_tag(self, tag):
        return tag in self._tags

    def clear_tags(self):
        for widget in self._tag_bubbles:
            self._ui.horizontalLayout.removeWidget(widget)
            widget.setParent(None)
        self._tag_bubbles.clear()
        self._tags.clear()
        self.on_tags_changed()

    @property
    def tags(self):
        return self._tags.keys()
