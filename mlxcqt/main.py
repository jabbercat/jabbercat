import asyncio
import functools
import logging
import random

import aioxmpp

import mlxc.conversation
import mlxc.main
import mlxc.utils

from . import Qt, client, roster, utils, conversation, webview, account_manager

from .ui.main import Ui_Main


_PEPPER = random.SystemRandom().getrandbits(64).to_bytes(64//8, "little")


class RosterItemDelegate(Qt.QItemDelegate):
    PADDING = 2
    SPACING = 2
    LEFT_PADDING = PADDING + 6
    TAG_MARGIN = 2
    TAG_PADDING = 2
    TAG_FONT_SIZE = 0.9
    NAME_FONT_SIZE = 1.1

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def _get_fonts(self, base_font):
        name_font = Qt.QFont(base_font)
        name_font.setWeight(Qt.QFont.Bold)
        name_font.setPointSizeF(name_font.pointSizeF()*self.NAME_FONT_SIZE)

        tag_font = Qt.QFont(base_font)
        tag_font.setPointSizeF(tag_font.pointSizeF()*self.TAG_FONT_SIZE)
        return name_font, tag_font

    def sizeHint(self, option, index):
        name_font, tag_font = self._get_fonts(option.font)
        name_metrics = Qt.QFontMetrics(name_font)
        name_height = name_metrics.ascent() + name_metrics.descent()

        tag_metrics = Qt.QFontMetrics(tag_font)
        tag_text_height = tag_metrics.ascent() + tag_metrics.descent()

        total_height = (self.PADDING*2 +
                        name_height +
                        self.SPACING +
                        tag_text_height +
                        self.SPACING +
                        tag_text_height +
                        self.TAG_PADDING*2 +
                        self.TAG_MARGIN*2)

        return Qt.QSize(0, total_height)

    def paint(self, painter, option, index):
        item = index.data(roster.RosterModel.ITEM_ROLE)

        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        if option.state & Qt.QStyle.State_Selected:
            painter.setBrush(Qt.QBrush(option.palette.highlight()))
        else:
            painter.setBrush(Qt.QBrush(option.backgroundBrush))
        painter.drawRect(option.rect)

        painter.setPen(Qt.Qt.NoPen)
        painter.setBrush(Qt.QColor(*item.account.colour))
        painter.drawRect(
            Qt.QRect(
                option.rect.topLeft(),
                option.rect.topLeft() + Qt.QPoint(
                    self.LEFT_PADDING - self.PADDING,
                    option.rect.height(),
                )
            )
        )

        painter.setRenderHint(Qt.QPainter.Antialiasing, True)

        if option.state & Qt.QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        name_font, tag_font = self._get_fonts(option.font)
        name_font.setWeight(Qt.QFont.Bold)
        name_metrics = Qt.QFontMetrics(name_font)
        painter.setFont(name_font)

        tag_metrics = Qt.QFontMetrics(tag_font)

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.LEFT_PADDING+self.SPACING, self.PADDING
        )

        name_rect = Qt.QRect(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING*2,
                name_metrics.ascent() + name_metrics.descent(),
            )
        )

        name = index.data()

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
                option.rect.width() - self.PADDING*2,
                tag_metrics.ascent() + tag_metrics.descent(),
            )
        )

        jid = str(item.jid)

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

        groups = sorted(
            ((group_full,
              mlxc.utils.normalise_text_for_hash(group_full))
             for group_full in item.groups),
            key=lambda x: x[1]
        )
        for group, group_norm in groups:
            width = tag_metrics.width(group)

            colour = utils.text_to_qtcolor(
                group_norm,
                None,
            )

            painter.setPen(Qt.QPen(Qt.Qt.NoPen))
            painter.setBrush(Qt.QBrush(colour))
            painter.drawRoundedRect(
                Qt.QRectF(top_left, top_left + Qt.QPoint(
                    width + 2*self.TAG_PADDING,
                    tag_metrics.ascent() + tag_metrics.descent() +
                    2*self.TAG_PADDING
                )),
                2.0, 2.0,
            )

            painter.setPen(option.palette.text().color())
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_metrics.ascent() + self.TAG_PADDING,
                group,
            )

            top_left += Qt.QPoint(
                self.TAG_MARGIN + 2*self.TAG_PADDING + width,
                0
            )

        if not item.groups:
            painter.drawText(
                top_left.x() + self.TAG_PADDING,
                top_left.y() + tag_metrics.ascent() + self.TAG_PADDING,
                "no tags"
            )


class MainWindow(Qt.QMainWindow):
    def __init__(self, main, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Main()
        self.ui.setupUi(self)
        self.main = main
        self.account_manager = account_manager.DlgAccountManager(
            main.client,
            main.identities,
        )

        sorted_roster = Qt.QSortFilterProxyModel(self.ui.roster_view)
        sorted_roster.setSourceModel(self.main.roster.model)
        sorted_roster.setSortRole(Qt.Qt.DisplayRole)
        sorted_roster.setSortLocaleAware(True)
        sorted_roster.setSortCaseSensitivity(False)
        sorted_roster.setDynamicSortFilter(True)
        sorted_roster.sort(0, Qt.Qt.AscendingOrder)
        self.ui.roster_view.setModel(sorted_roster)
        delegate = RosterItemDelegate(self.ui.roster_view)
        self.ui.roster_view.setItemDelegate(delegate)

        #self.ui.conversations_view.setModel(self.main.conversations_model)
        #self.ui.conversations_view.expandAll()

        view = webview.CustomWebView(self.ui.conversation_pages)
        view.setUrl(Qt.QUrl("qrc:/html/index.html"))
        self.ui.conversation_pages.addWidget(view)

        self.ui.action_manage_accounts.triggered.connect(
            self.account_manager.open
        )

    def closeEvent(self, ev):
        result = super().closeEvent(ev)
        self.main.quit()
        return result


class QtMain(mlxc.main.Main):
    Client = client.Client

    def __init__(self, loop):
        super().__init__(loop)
        self.roster = roster.Roster()
        self.client.on_client_prepare.connect(self.roster.connect_client)
        self.client.on_client_stopped.connect(self.roster.disconnect_client)

        # acc = self.identities.new_account(
        #     private,
        #     aioxmpp.JID.fromstr("jonas@wielicki.name"),
        #     tuple(round(v*255) for v in mlxc.utils.text_to_colour(
        #         "jonas@wielicki.name",
        #         None,
        #     ))
        # )
        # self.identities.set_account_enabled(acc, False)

        # work = self.identities.new_identity("Work")

        # acc = self.identities.new_account(
        #     work,
        #     aioxmpp.JID.fromstr("jonas@zombofant.net"),
        #     tuple(round(v*255) for v in mlxc.utils.text_to_colour(
        #         "jonas@zombofant.net",
        #         None,
        #     ))
        # )
        # self.identities.set_account_enabled(acc, False)

        self.window = MainWindow(self)

    @asyncio.coroutine
    def run_core(self):
        self.window.show()
        yield from super().run_core()
        try:
            yield from asyncio.wait_for(self.client.shutdown(),
                                        timeout=5)
        except asyncio.TimeoutError:
            pass
