import jclib.identity
import jclib.metadata

from .. import Qt, avatar, models


class MemberItemDelegate(Qt.QItemDelegate):
    AVATAR_SIZE = 16
    PADDING = 2
    SPACING = 2

    def __init__(self,
                 avatar_manager: avatar.AvatarManager,
                 account: jclib.identity.Account,
                 metadata: jclib.metadata.MetadataFrontend,
                 parent=None,
                 *,
                 compact=True):
        super().__init__(parent)
        self.avatar_manager = avatar_manager
        self.account = account
        self.compact = compact

    def simpleSizeHint(self, font):
        font = Qt.QFont(font)
        metrics = Qt.QFontMetrics(font)
        text_height = metrics.ascent() + metrics.descent()

        return Qt.QSize(
            self.AVATAR_SIZE + self.SPACING + self.PADDING * 2,
            max(text_height, self.AVATAR_SIZE) + self.PADDING * 2,
        )

    def sizeHint(self, option, index):
        if self.compact:
            return self.simpleSizeHint(option.font)

        text = index.data(Qt.Qt.DisplayRole)

        font = Qt.QFont(option.font)
        metrics = Qt.QFontMetrics(font)
        text_height = metrics.ascent() + metrics.descent()
        text_width = metrics.boundingRect(text).width()

        return Qt.QSize(
            self.AVATAR_SIZE + self.SPACING +
            text_width + self.PADDING * 2,
            max(text_height, self.AVATAR_SIZE) + self.PADDING * 2,
        )

    def paint(self, painter, option, index):
        padding_point = Qt.QPoint(self.PADDING, self.PADDING)

        name = index.data(Qt.Qt.DisplayRole)
        item = index.data(models.ROLE_OBJECT)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)

        top_left = option.rect.topLeft() + padding_point

        self.drawFocus(
            painter, option,
            Qt.QRect(top_left,
                     option.rect.bottomRight() - padding_point)
        )

        pic = self.avatar_manager.get_avatar(
            self.account,
            item.direct_jid or item.conversation_jid,
            getattr(item, "nick", None),
        )

        backup = painter.worldTransform()
        avatar_scale_factor = self.AVATAR_SIZE / avatar.BASE_SIZE
        painter.translate(top_left)
        painter.scale(avatar_scale_factor, avatar_scale_factor)
        painter.drawPicture(Qt.QPointF(), pic)
        painter.setWorldTransform(backup)

        painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        top_left += Qt.QPoint(
            self.AVATAR_SIZE + self.SPACING,
            0,
        )

        name_metrics = Qt.QFontMetrics(option.font)

        name_rect = Qt.QRect(
            top_left,
            option.rect.bottomRight() - padding_point,
        )

        name = name_metrics.elidedText(
            name,
            Qt.Qt.ElideRight,
            name_rect.width(),
        )

        if (option.state & Qt.QStyle.State_Selected and
                option.state & Qt.QStyle.State_Active):
            textcolor = option.palette.highlightedText().color()
        else:
            textcolor = option.palette.text().color()
        painter.setPen(textcolor)

        painter.drawText(name_rect, Qt.Qt.TextSingleLine, name)
