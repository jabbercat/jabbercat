import mlxc.conversation

from . import Qt, webview


class ConversationsModel(Qt.QAbstractItemModel):
    def __init__(self, tree):
        super().__init__()
        self.tree = tree
        self.tree.begin_insert_rows.connect(self._begin_insert_rows)
        self.tree.end_insert_rows.connect(self._end_insert_rows)

        self.tree.begin_remove_rows.connect(self._begin_remove_rows)
        self.tree.end_remove_rows.connect(self._end_remove_rows)

    def _begin_insert_rows(self, node, index1, index2):
        parent_mi = self.node_to_index(node)
        self.beginInsertRows(parent_mi, index1, index2)

    def _end_insert_rows(self):
        self.endInsertRows()

    def _begin_remove_rows(self, node, index1, index2):
        parent_mi = self.node_to_index(node)
        self.beginRemoveRows(parent_mi, index1, index2)

    def _end_remove_rows(self):
        self.endRemoveRows()

    def node_to_index(self, node, column=0):
        if node.parent is None:
            return Qt.QModelIndex()
        if not isinstance(node, mlxc.instrumentable_list.ModelTreeNode):
            node = node._node
        return self.createIndex(
            node.parent_index,
            column,
            node,
        )

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.tree.root)
        node = parent.internalPointer()
        return len(node)

    def columnCount(self, parent):
        return 1

    def _ident_data(self, node, column, role):
        if role == Qt.Qt.DisplayRole:
            return str(node.identity.name)

    def _conv_data(self, node, column, role):
        if role == Qt.Qt.DisplayRole:
            return str(node.peer_jid)

    def data(self, index, role):
        if index.isValid():
            node = index.internalPointer()
        else:
            node = self.tree.root

        node = node.object_

        if isinstance(node, mlxc.conversation.ConversationIdentity):
            return self._ident_data(node, index.column(), role)
        elif isinstance(node, mlxc.conversation.Conversation):
            return self._conv_data(node, index.column(), role)

    def index(self, row, column, parent):
        parent = (self.tree.root
                  if not parent.isValid()
                  else parent.internalPointer())
        return self.node_to_index(parent[row], column)

    def parent(self, index):
        if not index.isValid():
            return Qt.QModelIndex()
        return self.node_to_index(index.internalPointer().parent)


class ConversationHistoryView(Qt.QWebEngineView):
    pass


class ConversationView(Qt.QWidget):
    pass


class PeerConversationView(ConversationView):
    pass


class ConversationsController:
    def __init__(self, conversations, conversations_view, parent=None):
        super().__init__()
        self.conversations = conversations
        self.view = conversations_view
        self.conversations.on_conversation_started.connect(
            self.on_conversation_started,
        )
        self.conversations.on_conversation_stopped.connect(
            self.on_conversation_stopped,
        )

        view = webview.CustomWebView(parent=self)
        view.setUrl(Qt.QUrl("qrc:/html/index.html"))
        self.addWidget(view)

    def on_conversation_started(self, conversation):
        view = webview.CustomWebView(parent=self)
        view.setUrl(Qt.QUrl("qrc:/html/conversation-template.html"))
        self._conversation_views[conversation] = view
        self.addWidget(view)

    def on_conversation_stopped(self, conversation):
        pass
