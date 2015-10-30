import contextlib
import unittest
import unittest.mock

import aioxmpp.structs
import aioxmpp.roster

import mlxc.roster

import mlxcqt.roster
import mlxcqt.Qt as Qt


TEST_ACCOUNT_JID = aioxmpp.structs.JID.fromstr(
    "foo@a.example"
)

TEST_PEER_JID1 = aioxmpp.structs.JID.fromstr(
    "foo@b.example"
)

TEST_PEER_JID2 = aioxmpp.structs.JID.fromstr(
    "bar@b.example"
)


class TestViaView(unittest.TestCase):
    def setUp(self):
        self.item = aioxmpp.roster.Item(TEST_PEER_JID1)
        self.via = mlxc.roster.Via(TEST_ACCOUNT_JID, self.item)
        self.view = mlxcqt.roster.ViaView(self.via)

    def test_data_returns_label_in_DisplayRole(self):
        with unittest.mock.patch.object(
                mlxc.roster.Via,
                "label") as label:
            self.assertEqual(
                self.view.data(0, Qt.Qt.DisplayRole),
                label,
            )

    def test_data_returns_None_for_other_roles(self):
        self.item.name = object()
        self.assertIsNone(self.view.data(0, object()))

    def test_data_returns_None_for_other_columns(self):
        self.item.name = object()
        self.assertIsNone(self.view.data(1, Qt.Qt.DisplayRole))

    def test_attaches_to_Via(self):
        self.assertIs(mlxc.roster.Via.View, mlxcqt.roster.ViaView)

    def tearDow(self):
        del self.view
        del self.via
        del self.item


class TestContactView(unittest.TestCase):
    def setUp(self):
        self.item = aioxmpp.roster.Item(TEST_PEER_JID1)
        self.via = mlxc.roster.Via(TEST_ACCOUNT_JID, self.item)
        self.contact = mlxc.roster.Contact()
        self.view = mlxcqt.roster.ContactView(self.contact)

    def test_data_returns_label_in_DisplayRole(self):
        with unittest.mock.patch.object(
                mlxc.roster.Contact,
                "label") as label:
            self.assertEqual(
                self.view.data(0, Qt.Qt.DisplayRole),
                label,
            )

    def test_data_returns_None_for_other_roles(self):
        self.assertIsNone(self.view.data(0, object()))

    def test_data_returns_None_for_other_columns(self):
        self.assertIsNone(self.view.data(1, Qt.Qt.DisplayRole))

    def test_attaches_to_Contact(self):
        self.assertIs(mlxc.roster.Contact.View, mlxcqt.roster.ContactView)

    def tearDown(self):
        del self.view
        del self.contact
        del self.via
        del self.item


class TestGroupView(unittest.TestCase):
    def setUp(self):
        self.group = mlxc.roster.Group("name")
        self.view = mlxcqt.roster.GroupView(self.group)

    def test_data_returns_label_in_DisplayRole(self):
        self.assertEqual(
            self.view.data(0, Qt.Qt.DisplayRole),
            self.group.label
        )

    def test_data_returns_None_for_other_roles(self):
        self.assertIsNone(self.view.data(0, object()))

    def test_data_returns_None_for_other_columns(self):
        self.assertIsNone(self.view.data(1, Qt.Qt.DisplayRole))

    def test_attaches_to_Group(self):
        self.assertIs(mlxc.roster.Group.View, mlxcqt.roster.GroupView)

    def tearDown(self):
        del self.view
        del self.group


class TestRosterTreeModel(unittest.TestCase):
    def test_is_QAbstractItemModel(self):
        self.assertTrue(issubclass(
            mlxcqt.roster.RosterTreeModel,
            Qt.QAbstractItemModel
        ))

    def setUp(self):
        self.item1 = aioxmpp.roster.Item(TEST_PEER_JID1)
        self.item2 = aioxmpp.roster.Item(TEST_PEER_JID2)
        self.t = mlxc.roster.Tree()
        self.t.root.extend([
            mlxc.roster.Group(
                "A",
                initial=[
                    mlxc.roster.Contact(initial=[
                        mlxc.roster.Via(TEST_ACCOUNT_JID, self.item1),
                    ]),
                    mlxc.roster.Contact(initial=[
                        mlxc.roster.Via(TEST_ACCOUNT_JID, self.item2),
                    ]),
                ]
            ),
            mlxc.roster.Group(
                "B",
                initial=[
                    mlxc.roster.Contact(initial=[
                        mlxc.roster.Via(TEST_ACCOUNT_JID, self.item1),
                    ]),
                ]
            )
        ])

        self.model = mlxcqt.roster.RosterTreeModel(self.t)

    def test_index_with_invalid_parent_constraints_on_row_count(self):
        for row in range(len(self.t.root)):
            index = self.model.index(row, 0, Qt.QModelIndex())
            self.assertTrue(index.isValid())
            self.assertEqual(index.row(), row)
            self.assertEqual(index.column(), 0)
            self.assertIs(index.internalPointer(), self.t.root[row])

        index = self.model.index(len(self.t.root), 0, Qt.QModelIndex())
        self.assertFalse(index.isValid())

    def test_recursive_index(self):
        parent_index = self.model.index(1, 0, Qt.QModelIndex())
        index = self.model.index(0, 0, parent_index)
        self.assertTrue(index.isValid())
        self.assertIs(index.internalPointer(), self.t.root[1][0])
        self.assertEqual(index.row(), 0)

    def test_index_returns_invalid_index_if_parent_is_not_a_container(self):
        parent_index = self.model.index(
            0, 0,
            self.model.index(
                0, 0,
                self.model.index(1, 0, Qt.QModelIndex())))
        index = self.model.index(0, 0, parent_index)
        self.assertFalse(index.isValid())

    def test_recursive_index_constraints_on_row_count(self):
        parent_index = self.model.index(1, 0, Qt.QModelIndex())
        index = self.model.index(1, 0, parent_index)
        self.assertFalse(index.isValid())

    def test_rowCount_for_invalid_index_returns_root_length(self):
        self.assertEqual(
            self.model.rowCount(Qt.QModelIndex()),
            len(self.t.root)
        )

    def test_rowCount_for_valid_index_returns_number_of_children(self):
        parent_index = unittest.mock.MagicMock()
        parent_index.isValid.return_value = True
        parent_index.internalPointer.return_value = self.t.root[0]
        result = self.model.rowCount(parent_index)
        self.assertEqual(result, 2)
        calls = list(parent_index.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.isValid(),
                unittest.mock.call.internalPointer(),
            ]
        )

    def test_rowCount_for_valid_index_returns_zero_for_non_containers(self):
        parent_index = unittest.mock.MagicMock()
        parent_index.isValid.return_value = True
        parent_index.internalPointer.return_value = self.t.root[0][0][0]
        result = self.model.rowCount(parent_index)
        self.assertEqual(result, 0)

        calls = list(parent_index.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.isValid(),
                unittest.mock.call.internalPointer(),
            ]
        )

    def test_parent_returns_invalid_index_for_invalid_index(self):
        self.assertFalse(self.model.parent(Qt.QModelIndex()).isValid())

    def test_parent_uses__mkindex_for_valid_item(self):
        item_index = self.model.index(
            0, 0,
            self.model.index(
                1, 0,
                self.model.index(
                    0, 0,
                    Qt.QModelIndex()
                )
            )
        )
        self.assertTrue(item_index.isValid())
        self.assertIs(item_index.internalPointer(),
                      self.t.root[0][1][0])

        with unittest.mock.patch.object(
                self.model,
                "_mkindex") as mkindex:
            parent_index = self.model.parent(item_index)

        mkindex.assert_called_with(self.t.root[0][1][0].parent,
                                   item_index.column())
        self.assertEqual(mkindex(), parent_index)

    def test_columnCount_returns_one(self):
        self.assertEqual(
            self.model.columnCount(Qt.QModelIndex()),
            1
        )

    def test__mkindex_for_root(self):
        index = self.model._mkindex(self.t.root)
        self.assertFalse(index.isValid())

    def test__mkindex_for_other_item(self):
        index = self.model._mkindex(self.t.root[0])
        self.assertTrue(index.isValid())
        self.assertEqual(index.row(), 0)
        self.assertIs(index.internalPointer(), self.t.root[0])

        index = self.model._mkindex(self.t.root[1])
        self.assertTrue(index.isValid())
        self.assertEqual(index.row(), 1)
        self.assertIs(index.internalPointer(), self.t.root[1])

        index = self.model._mkindex(self.t.root[0][1])
        self.assertTrue(index.isValid())
        self.assertEqual(index.row(), 1)
        self.assertIs(index.internalPointer(), self.t.root[0][1])

    def test_forward_begin_insert_rows_event(self):
        with contextlib.ExitStack() as stack:
            beginInsertRows = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginInsertRows"))
            mkindex = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "_mkindex"))

            self.t.root.begin_insert_rows(
                self.t.root[0][1],
                0, 2)

        mkindex.assert_called_with(self.t.root[0][1])
        beginInsertRows.assert_called_with(
            mkindex(),
            0, 2)

    def test_forward_begin_move_rows_event(self):
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginMoveRows",
                new=base.beginMoveRows))
            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "_mkindex",
                new=base.mkindex))

            self.t.root.begin_move_rows(
                self.t.root[0][1],
                0, 2,
                self.t.root[1][0], 1)

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.mkindex(self.t.root[0][1]),
                unittest.mock.call.mkindex(self.t.root[1][0]),
                unittest.mock.call.beginMoveRows(
                    base.mkindex(), 0, 2,
                    base.mkindex(), 1)
            ]
        )

    def test_forward_begin_remove_rows_event(self):
        with contextlib.ExitStack() as stack:
            beginRemoveRows = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginRemoveRows"))
            mkindex = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "_mkindex"))

            self.t.root.begin_remove_rows(
                self.t.root[0][1],
                0, 2)

        mkindex.assert_called_with(self.t.root[0][1])
        beginRemoveRows.assert_called_with(
            mkindex(),
            0, 2)

    def test_forward_end_insert_rows(self):
        with contextlib.ExitStack() as stack:
            endInsertRows = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endInsertRows"))

            self.t.root.end_insert_rows()

        endInsertRows.assert_called_with()

    def test_forward_end_move_rows(self):
        with contextlib.ExitStack() as stack:
            endMoveRows = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endMoveRows"))

            self.t.root.end_move_rows()

        endMoveRows.assert_called_with()

    def test_forward_end_remove_rows(self):
        with contextlib.ExitStack() as stack:
            endRemoveRows = stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endRemoveRows"))

            self.t.root.end_remove_rows()

        endRemoveRows.assert_called_with()

    def test_data_returns_None_for_missing_view(self):
        index = unittest.mock.Mock()
        index.internalPointer.return_value = unittest.mock.Mock([])
        self.assertIsNone(self.model.data(index, object()))

    def test_data_returns_unknown_item_for_missing_view_and_display_role(self):
        index = unittest.mock.Mock()
        index.internalPointer.return_value = unittest.mock.Mock([])
        self.assertEqual(
            "unknown item",
            self.model.data(index, Qt.Qt.DisplayRole)
        )

    def test_data_asks_view(self):
        role = object()
        column = object()

        index = unittest.mock.Mock()
        index.column.return_value = column

        result = self.model.data(index, role)

        index.internalPointer.assert_called_with()
        index.internalPointer().view.data.assert_called_with(column, role)

        self.assertEqual(
            index.internalPointer().view.data(),
            result,
        )

    def tearDown(self):
        del self.t
