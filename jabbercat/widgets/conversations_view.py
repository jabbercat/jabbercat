from .. import Qt, models


class ConversationItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    NAME_FONT_SIZE = 1.0
    PREVIEW_FONT_SIZE = 0.9
    UNREAD_COUNTER_MAX = 100
    UNREAD_COUNTER_HORIZ_PADDING = 4
    UNREAD_COUNTER_VERT_PADDING = 2
    UNREAD_COUNTER_FONT_SIZE = 0.9

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

    def sizeHint(self, option, index):
        name_font, preview_font, unread_counter_font = self._get_fonts(
            option.font
        )
        name_metrics = Qt.QFontMetrics(name_font)
        name_height = name_metrics.ascent() + name_metrics.descent()

        preview_metrics = Qt.QFontMetrics(preview_font)
        preview_text_height = (preview_metrics.ascent() +
                               preview_metrics.descent())

        unread_counter_metrics = Qt.QFontMetrics(unread_counter_font)

        total_height = (self.PADDING * 2 +
                        self.UNREAD_COUNTER_VERT_PADDING * 2 +
                        name_height +
                        self.SPACING +
                        preview_text_height)

        min_width = (
            self.PADDING * 2 +
            name_metrics.width('…') +
            self.UNREAD_COUNTER_HORIZ_PADDING * 2 +
            unread_counter_metrics.width('{}+'.format(self.UNREAD_COUNTER_MAX))
        )

        return Qt.QSize(min_width, total_height)

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

        name_metrics = Qt.QFontMetrics(name_font)
        preview_metrics = Qt.QFontMetrics(preview_font)
        unread_counter_metrics = Qt.QFontMetrics(unread_counter_font)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.PADDING,
            self.PADDING + self.UNREAD_COUNTER_VERT_PADDING,
        )

        unread_counter_value = item.get_unread_count()
        name_right_x = option.rect.right() - self.PADDING

        painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        if unread_counter_value > 0:
            if unread_counter_value > self.UNREAD_COUNTER_MAX:
                unread_counter_text = "{}+".format(unread_counter_value)
            else:
                unread_counter_text = str(unread_counter_value)

            # TODO: set this to bold again if a highlight/mention happened
            unread_counter_font.setWeight(Qt.QFont.Normal)

            painter.setFont(preview_font)
            unread_counter_width = unread_counter_metrics.width(
                unread_counter_text
            )

            unread_counter_full_width = \
                self.UNREAD_COUNTER_HORIZ_PADDING * 2 + unread_counter_width

            unread_counter_pos = Qt.QPoint(
                option.rect.right() - self.PADDING -
                unread_counter_width - self.UNREAD_COUNTER_HORIZ_PADDING,
                top_left.y() + name_metrics.ascent(),
            )

            painter.setPen(Qt.Qt.NoPen)
            painter.setBrush(Qt.QBrush(option.palette.dark()))
            painter.drawRoundedRect(
                Qt.QRect(
                    unread_counter_pos - Qt.QPoint(
                        self.UNREAD_COUNTER_HORIZ_PADDING,
                        self.UNREAD_COUNTER_VERT_PADDING +
                        name_metrics.ascent(),
                    ),
                    unread_counter_pos + Qt.QPoint(
                        unread_counter_width +
                        self.UNREAD_COUNTER_HORIZ_PADDING,
                        name_metrics.descent() +
                        self.UNREAD_COUNTER_VERT_PADDING
                    ),
                ),
                self.UNREAD_COUNTER_HORIZ_PADDING,
                self.UNREAD_COUNTER_HORIZ_PADDING,
            )

            painter.setPen(option.palette.brightText().color())
            painter.drawText(
                unread_counter_pos,
                unread_counter_text,
            )

            name_right_x -= unread_counter_full_width + self.SPACING

        if (option.state & Qt.QStyle.State_Selected and
                option.state & Qt.QStyle.State_Active):
            textcolor = option.palette.highlightedText().color()
        else:
            textcolor = option.palette.text().color()
        painter.setPen(textcolor)

        name_height = name_metrics.ascent() + name_metrics.descent()
        name_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                name_right_x,
                top_left.y() + name_height,
            )
        )

        painter.setFont(name_font)
        name = name_metrics.elidedText(
            str(item.label),
            Qt.Qt.ElideMiddle,
            name_rect.width()
        )

        painter.drawText(name_rect, Qt.Qt.TextSingleLine, name)

        top_left += Qt.QPoint(
            0,
            name_height,
        )

        try:
            last_message, = item.get_last_messages(
                max_count=1,
            )
        except ValueError:
            pass
        else:
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
                    body.replace("\n", " ")
                ),
                Qt.Qt.ElideRight,
                preview_rect.width()
            )

            preview_color = Qt.QColor(textcolor)
            preview_color.setAlphaF(preview_color.alphaF() * 0.8)
            painter.setPen(preview_color)
            painter.setFont(preview_font)
            painter.drawText(preview_rect, Qt.Qt.TextSingleLine, body)
