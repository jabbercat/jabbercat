import contextlib
import unittest
import unittest.mock

import PyQt5.Qt as Qt

import aioxmpp

import mlxc.identity as identity

import mlxcqt.models as models


TEST_JID1 = aioxmpp.JID.fromstr("romeo@montague.lit")
TEST_JID2 = aioxmpp.JID.fromstr("juliet@capulet.lit")


class TestAccountsModel(unittest.TestCase):
    def setUp(self):
        self.accounts = identity.Accounts()
        self.accounts.new_account(TEST_JID1, None)
        self.accounts.new_account(TEST_JID2, None)
        self.accounts.set_account_enabled(self.accounts[1], False)
        self.m = models.AccountsModel(self.accounts)

    def tearDown(self):
        del self.m
        del self.accounts

    def test_row_count_on_root_follows_accounts(self):
        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            2,
        )

        self.accounts.remove_account(self.accounts[0])

        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            1,
        )

    def test_index_checks_row(self):
        self.assertFalse(
            self.m.index(-1, 0, Qt.QModelIndex()).isValid(),
        )

        self.assertTrue(
            self.m.index(0, 0, Qt.QModelIndex()).isValid(),
        )

        self.assertTrue(
            self.m.index(1, 0, Qt.QModelIndex()).isValid(),
        )

        self.assertFalse(
            self.m.index(2, 0, Qt.QModelIndex()).isValid(),
        )

    def test_index_checks_parent(self):
        self.assertFalse(
            self.m.index(0, 0, self.m.index(0, 0)).isValid(),
        )

    def test_index_checks_column(self):
        self.assertFalse(
            self.m.index(0, -1, Qt.QModelIndex()).isValid(),
        )

        self.assertTrue(
            self.m.index(0, 0, Qt.QModelIndex()).isValid(),
        )

        self.assertTrue(
            self.m.index(0, 1, Qt.QModelIndex()).isValid(),
        )

        self.assertFalse(
            self.m.index(0, 2, Qt.QModelIndex()).isValid(),
        )

    def test_row_count_on_items(self):
        self.assertEqual(
            self.m.rowCount(self.m.index(1, 0, Qt.QModelIndex())),
            0,
        )

    def test_forward_removal_signals(self):
        def beginHandler(*args):
            self.assertEqual(self.m.rowCount(Qt.QModelIndex()), 2)

        def endHandler(*args):
            self.assertEqual(self.m.rowCount(Qt.QModelIndex()), 1)

        mock = unittest.mock.Mock()
        mock.begin.side_effect = beginHandler
        mock.end.side_effect = endHandler

        self.m.rowsAboutToBeRemoved.connect(mock.begin)
        self.m.rowsRemoved.connect(mock.end)

        self.accounts.remove_account(self.accounts[1])

        mock.begin.assert_called_once_with(Qt.QModelIndex(), 1, 1)
        mock.end.assert_called_once_with(Qt.QModelIndex(), 1, 1)

    def test_forward_insertion_signals(self):
        def beginHandler(*args):
            self.assertEqual(self.m.rowCount(Qt.QModelIndex()), 2)

        def endHandler(*args):
            self.assertEqual(self.m.rowCount(Qt.QModelIndex()), 3)

        mock = unittest.mock.Mock()
        mock.begin.side_effect = beginHandler
        mock.end.side_effect = endHandler

        self.m.rowsAboutToBeInserted.connect(mock.begin)
        self.m.rowsInserted.connect(mock.end)

        self.accounts.new_account(aioxmpp.JID.fromstr("foo@bar.example"),
                                  None)

        mock.begin.assert_called_once_with(Qt.QModelIndex(), 2, 2)
        mock.end.assert_called_once_with(Qt.QModelIndex(), 2, 2)

    def test_forward_data_changed_signal(self):
        mock = unittest.mock.Mock()

        self.m.dataChanged.connect(mock)

        self.accounts.set_account_enabled(self.accounts[0], False)

        mock.assert_called_once_with(
            self.m.index(0, 0),
            self.m.index(0, self.m.COLUMN_COUNT - 1),
            [],
        )

    def test_flags_address_column(self):
        self.assertEqual(
            self.m.flags(self.m.index(
                0, self.m.COLUMN_ADDRESS,
                Qt.QModelIndex())),
            Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled |
            Qt.Qt.ItemNeverHasChildren
        )

    def test_flags_enabled_column(self):
        self.assertEqual(
            self.m.flags(self.m.index(
                0, self.m.COLUMN_ENABLED,
                Qt.QModelIndex())),
            Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled |
            Qt.Qt.ItemNeverHasChildren | Qt.Qt.ItemIsUserCheckable
        )

    def test_column_count(self):
        self.assertEqual(
            self.m.columnCount(),
            2,
        )

        self.assertEqual(
            self.m.columnCount(),
            self.m.COLUMN_COUNT,
        )

    def test_data_name_column_display_role(self):
        for i, account in enumerate(self.accounts):
            self.assertEqual(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ADDRESS),
                    Qt.Qt.DisplayRole,
                ),
                str(account.jid)
            )

            self.assertEqual(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ADDRESS),
                ),
                str(account.jid)
            )

    def test_data_name_column_check_state_role(self):
        for i, account in enumerate(self.accounts):
            self.assertIsNone(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ADDRESS),
                    Qt.Qt.CheckStateRole,
                ),
            )

    def test_data_name_column_other_role(self):
        for i, account in enumerate(self.accounts):
            self.assertIsNone(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ADDRESS),
                    unittest.mock.sentinel.other,
                ),
            )

    def test_data_enabled_column_display_role(self):
        for i, account in enumerate(self.accounts):
            self.assertIsNone(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ENABLED),
                    Qt.Qt.DisplayRole,
                ),
            )

    def test_data_enabled_column_check_state_role(self):
        for i, account in enumerate(self.accounts):
            self.assertEqual(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_ENABLED),
                    Qt.Qt.CheckStateRole,
                ),
                Qt.Qt.Checked if account.enabled else Qt.Qt.Unchecked
            )

    def test_data_object_role(self):
        for column in range(0, self.m.COLUMN_COUNT):
            for i, account in enumerate(self.accounts):
                self.assertIs(
                    self.m.data(
                        self.m.index(i, column),
                        models.ROLE_OBJECT,
                    ),
                    account,
                )

    def test_data_invalid_index(self):
        self.assertIsNone(
            self.m.data(Qt.QModelIndex()),
        )

    def test_sibling(self):
        index = self.m.index(1, 0, Qt.QModelIndex())
        sibling = self.m.sibling(0, 1, index)
        self.assertTrue(sibling.isValid())
        self.assertEqual(sibling.row(), 0)
        self.assertEqual(sibling.column(), 1)

    def test_setData_name_column_edit_role(self):
        self.assertFalse(
            self.m.setData(
                self.m.index(
                    0,
                    self.m.COLUMN_ADDRESS),
                "foo",
                Qt.Qt.EditRole
            )
        )

    def test_setData_set_enabled_to_false(self):
        with contextlib.ExitStack() as stack:
            set_account_enabled = stack.enter_context(
                unittest.mock.patch.object(
                    self.accounts,
                    "set_account_enabled"
                )
            )

            self.assertTrue(
                self.m.setData(
                    self.m.index(0, self.m.COLUMN_ENABLED),
                    Qt.Qt.Unchecked,
                    Qt.Qt.CheckStateRole,
                )
            )

            set_account_enabled.assert_called_once_with(
                self.accounts[0],
                False,
            )

    def test_setData_set_enabled_unchanged(self):
        with contextlib.ExitStack() as stack:
            set_account_enabled = stack.enter_context(
                unittest.mock.patch.object(
                    self.accounts,
                    "set_account_enabled"
                )
            )

            self.assertTrue(
                self.m.setData(
                    self.m.index(0, self.m.COLUMN_ENABLED),
                    Qt.Qt.Checked,
                    Qt.Qt.CheckStateRole,
                )
            )

            set_account_enabled.assert_called_once_with(
                self.accounts[0],
                True,
            )

        with contextlib.ExitStack() as stack:
            set_account_enabled = stack.enter_context(
                unittest.mock.patch.object(
                    self.accounts,
                    "set_account_enabled"
                )
            )

            self.assertTrue(
                self.m.setData(
                    self.m.index(1, self.m.COLUMN_ENABLED),
                    Qt.Qt.Unchecked,
                    Qt.Qt.CheckStateRole,
                )
            )

            set_account_enabled.assert_called_once_with(
                self.accounts[1],
                False,
            )

    def test_setData_set_enabled_to_true(self):
        with contextlib.ExitStack() as stack:
            set_account_enabled = stack.enter_context(
                unittest.mock.patch.object(
                    self.accounts,
                    "set_account_enabled"
                )
            )

            self.assertTrue(
                self.m.setData(
                    self.m.index(1, self.m.COLUMN_ENABLED),
                    Qt.Qt.Checked,
                    Qt.Qt.CheckStateRole,
                )
            )

            set_account_enabled.assert_called_once_with(
                self.accounts[1],
                True,
            )

    def test_headerData_horiz_address_column(self):
        with contextlib.ExitStack() as stack:
            tr = stack.enter_context(
                unittest.mock.patch("mlxcqt.Qt.translate")
            )

            result = self.m.headerData(
                self.m.COLUMN_ADDRESS,
                Qt.Qt.Horizontal,
                Qt.Qt.DisplayRole,
            )

        tr.assert_called_once_with("Address")

        self.assertEqual(result, tr())

    def test_headerData_horiz_enabled_column(self):
        with contextlib.ExitStack() as stack:
            tr = stack.enter_context(
                unittest.mock.patch("mlxcqt.Qt.translate")
            )

            result = self.m.headerData(
                self.m.COLUMN_ENABLED,
                Qt.Qt.Horizontal,
                Qt.Qt.DisplayRole,
            )

        tr.assert_called_once_with("Enabled")

        self.assertEqual(result, tr())


class TestFlattenModelToSeparators(unittest.TestCase):
    ITEMS = [
        {
            Qt.Qt.DisplayRole: "1",
            "children": [
                {
                    Qt.Qt.DisplayRole: "1.1",
                },
                {
                    Qt.Qt.DisplayRole: "1.2",
                    "children": [
                        {
                            Qt.Qt.DisplayRole: "1.2.1",
                        },
                        {
                            Qt.Qt.DisplayRole: "1.2.2",
                        }
                    ]
                },
                {
                    Qt.Qt.DisplayRole: "1.3",
                },
            ]
        },
        {
            Qt.Qt.DisplayRole: "2",
        },
        {
            Qt.Qt.DisplayRole: "3",
            "children": [
                {
                    Qt.Qt.DisplayRole: "3.1",
                },
                {
                    Qt.Qt.DisplayRole: "3.2",
                },
                {
                    Qt.Qt.DisplayRole: "3.3",
                },
            ]
        },
    ]

    def _init_subtree(self, subtree):
        item = Qt.QStandardItem()
        for role, value in subtree.items():
            if role == "children":
                continue
            item.setData(value, role)

        for child in subtree.get("children", []):
            item.appendRow(self._init_subtree(child))

        return item

    def _init_data(self, items):
        data = Qt.QStandardItemModel()
        for item in items:
            data.appendRow(self._init_subtree(item))
        return data

    def setUp(self):
        self.fm = models.FlattenModelToSeparators()
        self.data = self._init_data(self.ITEMS)
        self.listener = unittest.mock.Mock()
        self.source_listener = unittest.mock.Mock()
        for cb in ["rowsAboutToBeInserted", "rowsInserted",
                   "rowsAboutToBeRemoved", "rowsRemoved"]:
            handler = getattr(self.listener, cb)
            handler.return_value = None
            getattr(self.fm, cb).connect(handler)

            handler = getattr(self.source_listener, cb)
            handler.return_value = None
            getattr(self.data, cb).connect(handler)

    def test_empty_rowCount(self):
        self.assertEqual(
            self.fm.rowCount(Qt.QModelIndex()),
            0,
        )

    def test_rowCount_of_root(self):
        self.fm.setSourceModel(self.data)
        self.assertEqual(
            self.fm.rowCount(Qt.QModelIndex()),
            9,
        )

    def _check_mapping_to_source_dynamic(self):
        i_absolute = 0
        for i in range(self.data.rowCount()):
            flattened_idx = self.fm.index(i_absolute, 0, Qt.QModelIndex())
            self.assertTrue(flattened_idx.isValid())
            parent_idx = self.fm.mapToSource(flattened_idx)
            self.assertEqual(parent_idx.row(), i)

            nchildren = self.data.rowCount(parent_idx)
            for j in range(nchildren):
                flattened_idx = self.fm.index(
                    i_absolute+j+1, 0,
                    Qt.QModelIndex()
                )
                child_idx = self.fm.mapToSource(flattened_idx)
                self.assertEqual(child_idx.row(), j)
                self.assertEqual(child_idx.parent(), parent_idx)

            i_absolute += nchildren + 1

    def _check_mapping_from_source_dynamic(self):
        i_absolute = 0
        for i in range(self.data.rowCount()):
            parent_idx = self.data.index(i, 0, Qt.QModelIndex())
            flattened_idx = self.fm.mapFromSource(parent_idx)
            self.assertTrue(flattened_idx.isValid())
            self.assertEqual(flattened_idx.row(), i_absolute)

            nchildren = self.data.rowCount(parent_idx)
            for j in range(nchildren):
                child_idx = self.data.index(
                    j,
                    0,
                    parent_idx,
                )
                flattened_idx = self.fm.mapFromSource(child_idx)
                self.assertEqual(flattened_idx.row(), i_absolute+j+1)
                self.assertFalse(flattened_idx.parent().isValid())

            i_absolute += nchildren + 1

    def test_mapToSource_root(self):
        self.fm.setSourceModel(self.data)
        i_absolute = 0
        for i, item in enumerate(self.ITEMS):
            heading_idx = self.fm.index(i_absolute, 0, Qt.QModelIndex())
            self.assertTrue(heading_idx.isValid())
            source_idx = self.fm.mapToSource(heading_idx)
            self.assertTrue(source_idx.isValid())
            self.assertEqual(
                source_idx.model(),
                self.data,
            )
            self.assertEqual(
                source_idx.row(),
                i,
            )
            children = item.get("children", [])
            i_absolute += len(children) + 1

    def test_mapToSource_inlined_children(self):
        self.fm.setSourceModel(self.data)
        i_absolute = 0
        for i, item in enumerate(self.ITEMS):
            parent_idx = self.fm.mapToSource(
                self.fm.index(i_absolute, 0, Qt.QModelIndex())
            )
            children = item.get("children", [])
            for j, child in enumerate(children):
                child_idx = self.fm.index(i_absolute+j+1, 0, Qt.QModelIndex())
                self.assertTrue(child_idx.isValid())
                source_idx = self.fm.mapToSource(child_idx)
                self.assertTrue(source_idx.isValid())
                self.assertEqual(
                    source_idx.model(),
                    self.data,
                )
                self.assertEqual(
                    source_idx.row(),
                    j,
                )
                self.assertEqual(
                    source_idx.parent(),
                    parent_idx,
                )

            i_absolute += len(children) + 1

    def test_mapToSource_complete(self):
        self.fm.setSourceModel(self.data)
        self._check_mapping_to_source_dynamic()

    def test_mapFromSource_root(self):
        self.fm.setSourceModel(self.data)
        i_absolute = 0
        for i, item in enumerate(self.ITEMS):
            source_idx = self.data.index(i, 0, Qt.QModelIndex())
            self.assertTrue(source_idx.isValid())
            heading_idx = self.fm.mapFromSource(source_idx)
            self.assertTrue(heading_idx.isValid())
            self.assertEqual(
                heading_idx.model(),
                self.fm,
            )
            self.assertEqual(
                heading_idx.row(),
                i_absolute,
            )

            children = item.get("children", [])
            i_absolute += len(children) + 1

    def test_mapFromSource_inlined_children(self):
        self.fm.setSourceModel(self.data)
        i_absolute = 0
        for i, item in enumerate(self.ITEMS):
            parent_idx = self.data.index(i, 0, Qt.QModelIndex())

            children = item.get("children", [])
            for j, child in enumerate(children):
                source_idx = self.data.index(j, 0, parent_idx)
                self.assertTrue(source_idx.isValid())
                inlined_idx = self.fm.mapFromSource(source_idx)
                self.assertTrue(inlined_idx.isValid())
                self.assertEqual(
                    inlined_idx.model(),
                    self.fm,
                )
                self.assertEqual(
                    inlined_idx.row(),
                    i_absolute+j+1,
                )

            i_absolute += len(children) + 1

    def test_mapFromSource_complete(self):
        self.fm.setSourceModel(self.data)
        self._check_mapping_from_source_dynamic()

    def test_insert_inlined_child(self):
        self.fm.setSourceModel(self.data)
        item = Qt.QStandardItem()
        parent = self.data.item(1)
        parent.appendRow(item)
        self.listener.rowsInserted.assert_called_once_with(
            Qt.QModelIndex(), 5, 5,
        )
        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_insert_childless_root(self):
        self.fm.setSourceModel(self.data)
        item = Qt.QStandardItem()
        self.data.appendRow(item)
        self.listener.rowsInserted.assert_called_once_with(
            Qt.QModelIndex(), 9, 9,
        )
        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_insert_root_with_children(self):
        self.maxDiff = None

        self.fm.setSourceModel(self.data)
        item = Qt.QStandardItem()
        for i in range(2):
            item.appendRow(Qt.QStandardItem())

        self.data.appendRow(item)

        self.assertSequenceEqual(
            self.listener.mock_calls,
            [
                unittest.mock.call.rowsAboutToBeInserted(
                    Qt.QModelIndex(), 9, 9),
                unittest.mock.call.rowsInserted(Qt.QModelIndex(), 9, 9),
                unittest.mock.call.rowsAboutToBeInserted(
                    Qt.QModelIndex(), 10, 11),
                unittest.mock.call.rowsInserted(Qt.QModelIndex(), 10, 11),
            ]
        )

        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_insert_multiple(self):
        self.maxDiff = None

        self.fm.setSourceModel(self.data)
        items = [Qt.QStandardItem() for i in range(3)]
        items[0].appendRow(Qt.QStandardItem())
        items[0].appendRow(Qt.QStandardItem())
        items[2].appendRow(Qt.QStandardItem())

        self.data.invisibleRootItem().appendRows(items)

        self.source_listener.rowsInserted.assert_called_once_with(
            Qt.QModelIndex(),
            3, 5
        )

        self.assertSequenceEqual(
            self.listener.mock_calls,
            [
                unittest.mock.call.rowsAboutToBeInserted(
                    Qt.QModelIndex(), 9, 11),
                unittest.mock.call.rowsInserted(Qt.QModelIndex(), 9, 11),
                unittest.mock.call.rowsAboutToBeInserted(
                    Qt.QModelIndex(), 10, 11),
                unittest.mock.call.rowsInserted(Qt.QModelIndex(), 10, 11),
                unittest.mock.call.rowsAboutToBeInserted(
                    Qt.QModelIndex(), 14, 14),
                unittest.mock.call.rowsInserted(Qt.QModelIndex(), 14, 14),
            ]
        )

        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_remove_inlined_child(self):
        self.fm.setSourceModel(self.data)

        self.data.item(0).takeRow(0)

        self.listener.rowsRemoved.assert_called_once_with(
            Qt.QModelIndex(),
            1, 1,
        )
        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_remove_childless_root(self):
        self.fm.setSourceModel(self.data)

        self.data.takeRow(1)

        self.listener.rowsRemoved.assert_called_once_with(
            Qt.QModelIndex(), 4, 4,
        )
        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()

    def test_remove_root_with_child(self):
        self.maxDiff = None

        self.fm.setSourceModel(self.data)

        self.data.takeRow(0)

        self.assertSequenceEqual(
            self.listener.mock_calls,
            [
                unittest.mock.call.rowsAboutToBeRemoved(
                    Qt.QModelIndex(), 0, 3),
                unittest.mock.call.rowsRemoved(Qt.QModelIndex(), 0, 3),
            ]
        )

        self._check_mapping_from_source_dynamic()
        self._check_mapping_to_source_dynamic()
