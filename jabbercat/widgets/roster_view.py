import aioxmpp.callbacks

import random

import jclib.utils

import jabbercat.utils as utils

from .. import Qt, models


_PEPPER = random.SystemRandom().getrandbits(64).to_bytes(64 // 8, "little")


class RosterItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    LEFT_PADDING = PADDING + 6
    TAG_MARGIN = 2
    TAG_PADDING = 2
    TAG_FONT_SIZE = 0.9
    MIN_TAG_WIDTH = 16
    NAME_FONT_SIZE = 1.1

    MAX_AVATAR_SIZE = 48

    on_tag_clicked = aioxmpp.callbacks.Signal()

    def __init__(self, avatar_manager, parent=None):
        super().__init__(parent=parent)
        self.avatar_manager = avatar_manager
        self._cache = aioxmpp.cache.LRUDict()
        self._cache.maxsize = 128

    def _get_fonts(self, base_font):
        name_font = Qt.QFont(base_font)
        name_font.setWeight(Qt.QFont.Bold)
        name_font.setPointSizeF(name_font.pointSizeF() * self.NAME_FONT_SIZE)

        tag_font = Qt.QFont(base_font)
        tag_font.setPointSizeF(tag_font.pointSizeF() * self.TAG_FONT_SIZE)
        return name_font, tag_font

    def flush_caches(self):
        self._cache.clear()

    def layout_tags(self, font_metrics: Qt.QFontMetrics, tags, width):
        tags = tuple(sorted(
            ((tag_full,
              jclib.utils.normalise_text_for_hash(tag_full))
             for tag_full in tags),
            key=lambda x: x[1]
        ))

        cache_key = tags, width

        try:
            return self._cache[cache_key]
        except KeyError:
            pass

        text_widths = [
            max(font_metrics.width(tag), self.MIN_TAG_WIDTH)
            for tag, _ in tags
        ]

        text_colours = [
            utils.text_to_qtcolor(normalized_tag)
            for _, normalized_tag in tags
        ]

        tag_widths = [
            max(text_width, self.MIN_TAG_WIDTH) +
            self.TAG_PADDING * 2
            for text_width in text_widths
        ]

        margin_width = max(
            (len(tags) - 1) * self.TAG_MARGIN,
            0,
        )

        total_width = sum(tag_widths) + margin_width
        min_tag_width_full = self.MIN_TAG_WIDTH + self.TAG_PADDING * 2

        if total_width > width:
            min_width = len(tags) * min_tag_width_full + margin_width
            if width <= min_width:
                scale = 0
            else:
                variable_width = total_width - min_width
                if variable_width == 0:
                    scale = 1
                else:
                    scale = (width - min_width) / variable_width
        else:
            scale = 1

        if scale < 1:
            tag_widths = [
                round(
                    (tag_width - min_tag_width_full) * scale
                ) + min_tag_width_full
                for tag_width in tag_widths
            ]

            texts = [
                font_metrics.elidedText(
                    text,
                    Qt.Qt.ElideMiddle,
                    tag_width - self.TAG_PADDING * 2,
                )
                for (text, _), tag_width in zip(tags, tag_widths)
            ]
        else:
            texts = [text for text, _ in tags]

        item = {
            "tags": tags,
            "texts": texts,
            "width": total_width,
            "text_widths": text_widths,
            "text_colours": text_colours,
            "tag_widths": tag_widths,
            "scale": scale,
        }

        self._cache[cache_key] = item

        return item

    def sizeHint(self, option, index):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        name_height = name_metrics.ascent() + name_metrics.descent()

        tag_metrics = Qt.QFontMetrics(tag_font)
        tag_text_height = tag_metrics.ascent() + tag_metrics.descent()

        total_height = (self.PADDING * 2 +
                        name_height +
                        self.SPACING +
                        tag_text_height +
                        self.SPACING +
                        tag_text_height +
                        self.TAG_PADDING * 2 +
                        self.TAG_MARGIN * 2)

        item = index.data(models.ROLE_OBJECT)
        ntags = len(item.tags)

        min_width = (self.LEFT_PADDING +
                     self.MAX_AVATAR_SIZE +
                     self.SPACING +
                     ntags * (
                         self.MIN_TAG_WIDTH +
                         self.TAG_PADDING * 2 +
                         self.TAG_MARGIN + 2) +
                     self.PADDING)

        return Qt.QSize(min_width, total_height)

    def _tag_rects(self, font_metrics, top_left, layout):
        tag_text_height = font_metrics.ascent() + font_metrics.descent()

        for tag_width in layout["tag_widths"]:
            tag_rect = Qt.QRectF(
                top_left,
                top_left + Qt.QPoint(
                    tag_width,
                    tag_text_height + 2 * self.TAG_PADDING,
                )
            )
            yield tag_rect

            top_left += Qt.QPoint(
                tag_width + self.TAG_MARGIN,
                0
            )

    def _hits_tag(self, local_pos, option, item):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        tag_metrics = Qt.QFontMetrics(tag_font)

        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
            self.PADDING
        )

        top_left += Qt.QPoint(
            0,
            name_metrics.ascent() + name_metrics.descent() + self.SPACING
        )

        top_left += Qt.QPoint(
            self.TAG_MARGIN,
            tag_metrics.ascent() + tag_metrics.descent() + self.SPACING
        )

        layout = self.layout_tags(
            tag_metrics,
            item.tags,
            option.rect.width() - (
                top_left.x() - option.rect.x()
            ) - self.PADDING
        )

        for (tag, _), tag_rect in zip(
                layout["tags"],
                self._tag_rects(tag_metrics, top_left, layout)):

            if tag_rect.contains(local_pos):
                return tag

        return None

    def paint(self, painter, option, index):
        item = index.data(models.ROLE_OBJECT)
        name_font, tag_font = self._get_fonts(option.font)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)

        cursor_pos = option.widget.mapFromGlobal(Qt.QCursor.pos())

        name = item.label

        colour = utils.text_to_qtcolor(
            name,
        )

        # painter.drawRect(
        #     Qt.QRect(
        #         option.rect.topLeft(),
        #         option.rect.topLeft() + Qt.QPoint(
        #             self.LEFT_PADDING - self.PADDING,
        #             option.rect.height()-1,
        #         )
        #     )
        # )

        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        avatar_origin = option.rect.topLeft()
        avatar_origin = avatar_origin + Qt.QPoint(
            self.PADDING + self.SPACING,
            option.rect.height() / 2 - avatar_size / 2
        )

        pic = self.avatar_manager.get_avatar(
            item.account,
            item.address,
        )
        painter.drawPicture(avatar_origin, pic)

        # pen_colour = Qt.QColor(colour)
        # pen_colour.setAlpha(127)
        # painter.setPen(Qt.QPen(pen_colour))
        # painter.setBrush(colour)

        # avatar_rect = Qt.QRectF(
        #     avatar_origin,
        #     avatar_origin + Qt.QPoint(avatar_size, avatar_size)
        # )

        # # painter.drawRoundedRect(
        # #     avatar_rect,
        # #     avatar_size / 24, avatar_size / 24,
        # # )

        # painter.drawRect(
        #     avatar_rect,
        # )

        # painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        # painter.setPen(Qt.QPen(Qt.QColor(255, 255, 255, 255)))
        # painter.setBrush(Qt.QBrush())
        # avatar_font = Qt.QFont(name_font)
        # avatar_font.setPixelSize(avatar_size*0.85-2*self.PADDING)
        # avatar_font.setWeight(Qt.QFont.Thin)
        # painter.setFont(avatar_font)
        # painter.drawText(
        #     Qt.QRectF(
        #         avatar_origin + Qt.QPoint(self.PADDING, self.PADDING),
        #         avatar_origin + Qt.QPoint(avatar_size-self.PADDING*2,
        #                                   avatar_size-self.PADDING*2),
        #     ),
        #     Qt.Qt.AlignHCenter | Qt.Qt.AlignVCenter | Qt.Qt.TextSingleLine,
        #     name[0].upper(),
        # )

        if option.state & Qt.QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        name_metrics = Qt.QFontMetrics(name_font)
        painter.setFont(name_font)

        tag_metrics = Qt.QFontMetrics(tag_font)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
            self.PADDING
        )

        name_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right() - self.PADDING,
                top_left.y() + name_metrics.ascent() + name_metrics.descent(),
            )
        )

        # import hashlib
        # hash_ = hashlib.sha1()
        # hash_.update(name.encode("utf-8") + _PEPPER)
        # name = hash_.hexdigest()

        name = name_metrics.elidedText(
            name,
            Qt.Qt.ElideRight,
            name_rect.width()
        )

        painter.drawText(name_rect, Qt.Qt.TextSingleLine, name)

        painter.setFont(tag_font)

        top_left += Qt.QPoint(
            0,
            name_metrics.ascent() + name_metrics.descent() + self.SPACING
        )

        jid_rect = Qt.QRect(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING * 2,
                tag_metrics.ascent() + tag_metrics.descent(),
            )
        )

        jid = str(item.address)

        # hash_ = hashlib.sha1()
        # hash_.update(jid.encode("utf-8") + _PEPPER)
        # jid = hash_.hexdigest()

        jid = name_metrics.elidedText(
            jid,
            Qt.Qt.ElideLeft,
            jid_rect.width()
        )
        painter.drawText(jid_rect, Qt.Qt.TextSingleLine, jid)

        top_left += Qt.QPoint(
            self.TAG_MARGIN,
            tag_metrics.ascent() + tag_metrics.descent() + self.SPACING
        )

        tags_layout = self.layout_tags(
            tag_metrics,
            item.tags,
            option.rect.width() - (
                top_left.x() - option.rect.x()
            ) - self.PADDING,
        )

        tag_text_ascent = tag_metrics.ascent()

        for text, tag_rect, colour in zip(
                tags_layout["texts"],
                self._tag_rects(tag_metrics, top_left, tags_layout),
                tags_layout["text_colours"]):
            if tag_rect.contains(cursor_pos):
                colour = colour.lighter(125)

            painter.setPen(Qt.QPen(Qt.Qt.NoPen))
            painter.setBrush(Qt.QBrush(colour))

            painter.drawRoundedRect(
                tag_rect,
                2.0, 2.0,
            )

            painter.setPen(option.palette.text().color())
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_text_ascent + self.TAG_PADDING,
                text,
            )

        if not item.tags:
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_metrics.ascent() + self.TAG_PADDING,
                "no tags"
            )

    def updateEditorGeometry(self, editor, option, index):
        print("updating editor geometry", editor)
        avatar_size = min(option.rect.height() - self.PADDING * 2,
                          self.MAX_AVATAR_SIZE)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING + self.SPACING * 2 + avatar_size,
            self.PADDING
        )

        editor_rect = Qt.QRect(
            top_left,
            Qt.QPoint(
                option.rect.right() - self.PADDING,
                top_left.y() + editor.geometry().height()
            )
        )
        print(editor_rect)

        editor.setGeometry(editor_rect)

    def editorEvent(self, event, model, option, index):
        if (event.type() == Qt.QEvent.MouseButtonPress and
                event.button() == Qt.Qt.LeftButton):
            item = index.data(models.ROLE_OBJECT)
            tag_hit = self._hits_tag(event.pos(), option, item)
            if tag_hit is not None:
                self.on_tag_clicked(tag_hit, event.modifiers())
                return True
        elif event.type() == Qt.QEvent.MouseMove:
            option.widget.update(index)
        return super().editorEvent(event, model, option, index)
