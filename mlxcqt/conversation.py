import asyncio
import functools

from datetime import datetime

import aioxmpp.im.p2p
import aioxmpp.im.service
import aioxmpp.structs

import mlxc.conversation

from . import Qt, utils, models

from .ui import p2p_conversation


def _connect_and_store_token(tokens, signal, handler):
    tokens.append(
        (signal, signal.connect(handler))
    )


class MessageInfo(Qt.QTextBlockUserData):
    from_ = None


class ConversationView(Qt.QWidget):
    def __init__(self, conversation):
        super().__init__()
        self.ui = p2p_conversation.Ui_P2PView()
        self.ui.setupUi(self)

        self.ui.title_label.setText(
            "Conversation with {}".format(conversation.peer_jid)
        )

        self.ui.message_input.installEventFilter(self)

        # self.ui.history.setMaximumBlockCount(100)

        self.__conversation = conversation
        self.__tokens = []
        _connect_and_store_token(
            self.__tokens,
            conversation.on_message,
            functools.partial(self.add_message),
        )
        self.__msgidmap = {}

    def eventFilter(self, obj, ev):
        if obj is not self.ui.message_input:
            return False
        if ev.type() != Qt.QEvent.KeyPress:
            return False

        if ev.key() == Qt.Qt.Key_Return:
            if ev.modifiers() == Qt.Qt.NoModifier:
                if not self.ui.message_input.document().isEmpty():
                    self._send_message()
                return True

        return False

    @utils.asyncify
    @asyncio.coroutine
    def _send_message(self):
        body = self.ui.message_input.toPlainText()
        msg = aioxmpp.Message(type_="chat")
        msg.body[None] = body
        self.ui.message_input.clear()
        yield from self.__conversation.send_message(msg)

    def _message_frame_format(self):
        fmt = Qt.QTextFrameFormat()
        return fmt

    def add_message(self, message, member, source):
        if not message.body:
            return

        from_ = message.from_
        if member is self.__conversation.me:
            from_ = "me"
        else:
            from_ = str(from_.bare())

        # info = MessageInfo()
        # info.from_ = from_

        doc = self.ui.history.document()

        # if doc.isEmpty():
        #     last_block = None
        #     prev_from = None
        #     cursor = Qt.QTextCursor(doc)
        # else:
        #     cursor = doc.rootFrame().childFrames()[-1].lastCursorPosition()
        #     last_block = cursor.block()
        #     prev_from = last_block.userData().from_

        # if prev_from != from_:
        #     cursor = Qt.QTextCursor(doc)
        #     cursor.movePosition(Qt.QTextCursor.End)
        #     fmt = self._message_frame_format()
        #     outer_frame = cursor.insertFrame(fmt)
        #     # start new part
        #     fmt = Qt.QTextFrameFormat()
        #     fmt.setWidth(Qt.QTextLength(Qt.QTextLength.FixedLength, 48))
        #     fmt.setHeight(Qt.QTextLength(Qt.QTextLength.FixedLength, 48))
        #     fmt.setBackground(Qt.QBrush(utils.text_to_qtcolor(from_)))
        #     fmt.setMargin(4)
        #     fmt.setPosition(Qt.QTextFrameFormat.FloatLeft)
        #     cursor.insertFrame(fmt)
        #     cursor.insertText(from_[0].upper())
        #     cursor.movePosition(Qt.QTextCursor.NextCharacter)
        #     tmp_cursor = outer_frame.firstCursorPosition()
        #     tmp_cursor.block().setVisible(False)
        #     last_block = None

        # if last_block is not None:
        #     cursor.insertBlock()
        # cursor.insertText("{}: {}".format(
        #     datetime.now().replace(microsecond=0).time(),
        #     message.body.lookup([
        #         aioxmpp.structs.LanguageRange.fromstr("*")
        #     ]).strip()
        # ))
        # cursor.block().setUserData(info)

        # fmt = Qt.QTextFrameFormat()

        # if doc.isEmpty():
        cursor = Qt.QTextCursor(doc)
        cursor.movePosition(Qt.QTextCursor.End)
        # else:
        #     last_frame = doc.rootFrame().childFrames()[-1]
        #     cursor = last_frame.lastCursorPosition()
        #     cursor.movePosition(Qt.QTextCursor.NextCharacter)

        # cursor.insertFrame(fmt)
        cursor.insertText("{} {}: {}\n".format(
            datetime.now().replace(microsecond=0).time(),
            from_,
            message.body.lookup([
                aioxmpp.structs.LanguageRange.fromstr("*")
            ]).strip()
        ))


# class ConversationsController(mlxc.conversation.Conversations):
#     def __init__(self, identities, client):
#         super().__init__(identities, client)
#         self._conversation_views = {}
#         self.__view = None
#         self.__pages = None
#         self.model = models.ConversationsModel(self.tree)
#         self.on_conversation_node_created.connect(self._new_conversation)

#     @property
#     def pages(self):
#         return self.__pages

#     @pages.setter
#     def pages(self, widget):
#         self.__pages = widget

#     @property
#     def view(self):
#         return self.__view

#     @view.setter
#     def view(self, widget):
#         self.__view = widget
#         self.__view.setModel(self.model)
#         for identity_wrapper in self.tree.root:
#             self.__view.expand(
#                 self.model.node_to_index(
#                     identity_wrapper._node
#                 )
#             )

#     def _identity_added(self, identity):
#         super()._identity_added(identity)
#         if self.__view is not None:
#             self.__view.expand(
#                 self.model.node_to_index(
#                     self.tree.root[-1]._node
#                 )
#             )

#     def _new_conversation(self, wrapper):
#         conversation = wrapper.conversation
#         view = ConversationView(conversation)
#         self._conversation_views[conversation] = view
#         self.__pages.addWidget(view)
