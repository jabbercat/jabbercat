import typing

from .. import Qt, models, avatar
from .misc import PlaceholderListView


class ConversationItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    NAME_FONT_SIZE = 1.0
    PREVIEW_FONT_SIZE = 0.9
    UNREAD_COUNTER_MAX = 100
    UNREAD_COUNTER_HORIZ_PADDING = 4
    UNREAD_COUNTER_VERT_PADDING = 2
    UNREAD_COUNTER_FONT_SIZE = 0.9
    AVATAR_PADDING = SPACING

    def __init__(self, avatar_manager, parent=None):
        super().__init__(parent)
        self.avatar_manager = avatar_manager

    def _get_fonts(self, base_font):
        name_font = Qt.QFont(base_font)
        name_font.setPointSizeF(name_font.pointSizeF() * self.NAME_FONT_SIZE)

        preview_font = Qt.QFont(base_font)
        preview_font.setPointSizeF(
            preview_font.pointSizeF() * self.PREVIEW_FONT_SIZE
        )

        unread_counter_font = Qt.QFont(base_font)
        unread_counter_font.setWeight(Qt.QFont.Bold)
        unread_counter_font.setPointSizeF(
            preview_font.pointSizeF() * self.UNREAD_COUNTER_FONT_SIZE
        )

        return name_font, preview_font, unread_counter_font

    def _get_additional_metrics(self,
                                name_metrics: Qt.QFontMetrics,
                                preview_metrics: Qt.QFontMetrics):
        name_text_height = (
            name_metrics.ascent() +
            name_metrics.descent()
        )
        preview_text_height = (
            preview_metrics.ascent() +
            preview_metrics.descent()
        )

        avatar_size = (
            name_text_height +
            self.SPACING +
            preview_text_height
        )
        return name_text_height, preview_text_height, avatar_size

    def simpleSizeHint(self, font):
        name_font, preview_font, unread_counter_font = self._get_fonts(
            font
        )
        name_metrics = Qt.QFontMetrics(name_font)

        preview_metrics = Qt.QFontMetrics(preview_font)

        unread_counter_metrics = Qt.QFontMetrics(unread_counter_font)

        name_text_height, preview_text_height, avatar_size = \
            self._get_additional_metrics(name_metrics, preview_metrics)

        total_height = (self.PADDING * 2 +
                        self.UNREAD_COUNTER_VERT_PADDING * 2 +
                        name_text_height +
                        self.SPACING +
                        preview_text_height)

        min_width = (
            self.PADDING * 2 +
            avatar_size + self.AVATAR_PADDING +
            name_metrics.width('…') +
            self.UNREAD_COUNTER_HORIZ_PADDING * 2 +
            unread_counter_metrics.width('{}+'.format(self.UNREAD_COUNTER_MAX))
        )

        return Qt.QSize(min_width, total_height)

    def sizeHint(self, option, index):
        return self.simpleSizeHint(option.font)

    def _draw_unread_counter(self,
                             painter: Qt.QPainter,
                             option,
                             top_left: Qt.QPoint,
                             value: int,
                             font: Qt.QFont,
                             metrics: Qt.QFontMetrics,
                             name_ascent: float,
                             name_descent: float):
        if value > self.UNREAD_COUNTER_MAX:
            text = "{}+".format(value)
        else:
            text = str(value)

        # TODO: set this to bold again if a highlight/mention happened
        font.setWeight(Qt.QFont.Normal)

        painter.setFont(font)
        width = metrics.width(text)

        full_width = self.UNREAD_COUNTER_HORIZ_PADDING * 2 + width

        pos = Qt.QPoint(
            option.rect.right() - self.PADDING -
            width - self.UNREAD_COUNTER_HORIZ_PADDING,
            top_left.y() + name_ascent,
        )

        painter.setPen(Qt.Qt.NoPen)
        painter.setBrush(Qt.QBrush(option.palette.dark()))
        painter.drawRoundedRect(
            Qt.QRect(
                pos - Qt.QPoint(
                    self.UNREAD_COUNTER_HORIZ_PADDING,
                    self.UNREAD_COUNTER_VERT_PADDING +
                    name_ascent,
                ),
                pos + Qt.QPoint(
                    width +
                    self.UNREAD_COUNTER_HORIZ_PADDING,
                    name_descent +
                    self.UNREAD_COUNTER_VERT_PADDING
                ),
            ),
            self.UNREAD_COUNTER_HORIZ_PADDING,
            self.UNREAD_COUNTER_HORIZ_PADDING,
        )

        painter.setPen(option.palette.brightText().color())
        painter.drawText(
            pos,
            text,
        )

        return full_width + self.SPACING

    def _draw_preview_text(self,
                           painter: Qt.QPainter,
                           option,
                           textcolor: Qt.QColor,
                           top_left: Qt.QPoint,
                           preview_font: Qt.QFont,
                           preview_metrics: Qt.QFontMetrics,
                           item):
        try:
            last_message, = item.get_last_messages(
                max_count=1,
            )
        except ValueError:
            return

        _, _, is_self, _, display_name, _, message = last_message
        body = message.body.any()

        preview_height = (preview_metrics.ascent() +
                          preview_metrics.descent())

        preview_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right() - self.PADDING,
                top_left.y() + preview_height,
            )
        )

        body = preview_metrics.elidedText(
            "{}: {}".format(
                display_name,
                body.strip().replace("\n", " ")
            ),
            Qt.Qt.ElideRight,
            preview_rect.width()
        )

        preview_color = Qt.QColor(textcolor)
        preview_color.setAlphaF(preview_color.alphaF() * 0.8)
        painter.setPen(preview_color)
        painter.setFont(preview_font)
        painter.drawText(preview_rect, Qt.Qt.TextSingleLine, body)

        return preview_rect.bottomLeft()

    def paint(self, painter, option, index):
        item = index.data(models.ROLE_OBJECT)
        name_font, preview_font, unread_counter_font = self._get_fonts(
            option.font
        )

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)
        padding_point = Qt.QPoint(self.PADDING, self.PADDING)
        self.drawFocus(
            painter, option,
            Qt.QRect(option.rect.topLeft() + padding_point,
                     option.rect.bottomRight() - padding_point)
        )

        name_metrics = Qt.QFontMetrics(name_font)
        preview_metrics = Qt.QFontMetrics(preview_font)
        unread_counter_metrics = Qt.QFontMetrics(unread_counter_font)
        name_height, _, avatar_size = \
            self._get_additional_metrics(name_metrics, preview_metrics)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.PADDING,
            self.PADDING + self.UNREAD_COUNTER_VERT_PADDING,
        )

        pic = self.avatar_manager.get_avatar(
            item.account,
            item.conversation_address,
        )
        backup = painter.worldTransform()
        avatar_scale_factor = avatar_size / avatar.BASE_SIZE
        painter.translate(top_left)
        painter.scale(avatar_scale_factor, avatar_scale_factor)
        painter.drawPicture(Qt.QPointF(), pic)
        painter.setWorldTransform(backup)

        top_left += Qt.QPoint(
            avatar_size + self.AVATAR_PADDING,
            0,
        )

        unread_counter_value = item.get_unread_count()
        name_right_x = option.rect.right() - self.PADDING

        painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        if unread_counter_value > 0:
            name_right_x -= self._draw_unread_counter(
                painter,
                option,
                top_left,
                unread_counter_value,
                unread_counter_font,
                unread_counter_metrics,
                name_metrics.ascent(),
                name_metrics.descent(),
            )

        if (option.state & Qt.QStyle.State_Selected and
                option.state & Qt.QStyle.State_Active):
            textcolor = option.palette.highlightedText().color()
        else:
            textcolor = option.palette.text().color()
        painter.setPen(textcolor)

        name_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                name_right_x,
                top_left.y() + name_height,
            )
        )

        painter.setFont(name_font)
        name = name_metrics.elidedText(
            index.data(Qt.Qt.DisplayRole),
            Qt.Qt.ElideRight,
            name_rect.width()
        )

        painter.drawText(name_rect, Qt.Qt.TextSingleLine, name)

        top_left += Qt.QPoint(
            0,
            name_height,
        )

        top_left = self._draw_preview_text(
            painter,
            option,
            textcolor,
            top_left,
            preview_font,
            preview_metrics,
            item,
        )


class ConversationsView(PlaceholderListView):
    def selectionCommand(
            self,
            index: Qt.QModelIndex,
            event: typing.Optional[Qt.QEvent]
            ) -> Qt.QItemSelectionModel.SelectionFlags:
        if event is not None and event.type() == Qt.QEvent.MouseButtonPress:
            return Qt.QItemSelectionModel.ClearAndSelect
        return Qt.QItemSelectionModel.NoUpdate

    def setModel(self, model):
        old_model = self.model()
        if old_model is not None:
            old_model.rowsRemoved.disconnect(self._rows_removed)
            old_model.rowsInserted.disconnect(self._rows_inserted)
            old_model.modelReset.disconnect(self._model_reset)
        super().setModel(model)
        if model is not None:
            model.rowsRemoved.connect(self._rows_removed)
            model.rowsInserted.connect(self._rows_inserted)
            model.modelReset.connect(self._model_reset)
        self.updateGeometry()

    def _rows_inserted(self, parent, first, last):
        self.updateGeometry()

    def _rows_removed(self, parent, first, last):
        self.updateGeometry()

    def _model_reset(self):
        self.updateGeometry()

    def sizeHint(self):
        origSize = super().sizeHint()

        model = self.model()
        if model is None:
            return origSize

        delegate = self.itemDelegate()
        if not isinstance(delegate, ConversationItemDelegate):
            return origSize

        nrows = max(model.rowCount(Qt.QModelIndex()), 1)
        height = delegate.simpleSizeHint(self.font()).height()
        result = Qt.QSize(origSize.width(), height * nrows)
        return result
