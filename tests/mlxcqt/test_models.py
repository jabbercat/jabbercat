import contextlib
import unittest
import unittest.mock

import PyQt5.Qt as Qt

import aioxmpp

import mlxc.identity as identity
import mlxc.instrumentable_list
import mlxc.roster

import mlxcqt.avatar

import mlxcqt.models as models

from aioxmpp.testutils import (
    make_listener,
)


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

    def test_uses_model_list_adaptor(self):
        accounts = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("mlxcqt.model_adaptor.ModelListAdaptor")
            )

            result = models.AccountsModel(accounts)

        ModelListAdaptor.assert_called_once_with(accounts, result)

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
                unittest.mock.patch.object(self.m, "tr")
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
                unittest.mock.patch.object(self.m, "tr")
            )

            result = self.m.headerData(
                self.m.COLUMN_ENABLED,
                Qt.Qt.Horizontal,
                Qt.Qt.DisplayRole,
            )

        tr.assert_called_once_with("Enabled")

        self.assertEqual(result, tr())


class TestConversationsModel(unittest.TestCase):
    def setUp(self):
        def make_mock():
            return unittest.mock.Mock(["label"])

        self.cs = mlxc.instrumentable_list.ModelList()
        self.cs.append(make_mock())
        self.cs.append(make_mock())
        self.cs.append(make_mock())

        self.m = models.ConversationsModel(self.cs)

    def test_uses_model_list_adaptor(self):
        convs = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("mlxcqt.model_adaptor.ModelListAdaptor")
            )

            result = models.ConversationsModel(convs)

        ModelListAdaptor.assert_called_once_with(convs, result)

    def test_row_count_on_root_follows_convs(self):
        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            len(self.cs),
        )

        self.cs.append(unittest.mock.sentinel.item)

        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            len(self.cs),
        )

    def test_column_count(self):
        self.assertEqual(
            self.m.columnCount(Qt.QModelIndex()),
            self.m.COLUMN_COUNT,
        )
        self.assertEqual(
            self.m.COLUMN_COUNT,
            1,
        )

    def test_index_checks_row(self):
        self.assertFalse(self.m.index(-1, 0).isValid())
        self.assertTrue(self.m.index(0, 0).isValid())
        self.assertTrue(self.m.index(1, 0).isValid())
        self.assertTrue(self.m.index(2, 0).isValid())
        self.assertFalse(self.m.index(3, 0).isValid())

    def test_index_checks_column(self):
        self.assertFalse(self.m.index(0, -1).isValid())
        self.assertTrue(self.m.index(0, 0).isValid())
        self.assertFalse(self.m.index(0, 1).isValid())

    def test_row_count_on_items(self):
        index = self.m.index(0, 0)
        self.assertEqual(self.m.rowCount(index), 0)

    def test_index_checks_parent(self):
        parent = self.m.index(0, 0)
        self.assertTrue(parent.isValid())
        self.assertFalse(self.m.index(0, 0, parent).isValid())

    def test_data_label_column_display_role(self):
        for i, conv in enumerate(self.cs):
            self.assertEqual(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_LABEL),
                    Qt.Qt.DisplayRole,
                ),
                conv.label,
            )

            self.assertEqual(
                self.m.data(self.m.index(i, self.m.COLUMN_LABEL)),
                conv.label,
            )

    def test_data_label_column_other_role(self):
        for i, _ in enumerate(self.cs):
            self.assertIsNone(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_LABEL),
                    unittest.mock.sentinel.other_role,
                ),
            )

    def test_data_invalid_index(self):
        self.assertIsNone(
            self.m.data(
                Qt.QModelIndex(),
                Qt.Qt.DisplayRole
            ),
        )


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


class TestRosterModel(unittest.TestCase):
    def setUp(self):
        self.roster = mlxc.instrumentable_list.ModelList()
        self.roster.extend(
            unittest.mock.Mock(spec=mlxc.roster.AbstractRosterItem)
            for i in range(3)
        )
        self.avatar = unittest.mock.Mock(spec=mlxcqt.avatar.AvatarManager)
        self.m = models.RosterModel(self.roster, self.avatar)
        self.listener = make_listener(self.m)

    def test_uses_model_list_adaptor(self):
        items = unittest.mock.Mock([])

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("mlxcqt.model_adaptor.ModelListAdaptor")
            )

            result = models.RosterModel(items, self.avatar)

        ModelListAdaptor.assert_called_once_with(items, result)

    def test_connects_to_on_avatar_changed_weakly(self):
        self.avatar.on_avatar_changed.connect.assert_called_once_with(
            self.m._on_avatar_changed,
            self.avatar.on_avatar_changed.WEAK,
        )

    def test_row_count_on_root_follows_items(self):
        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            len(self.roster),
        )

        self.roster.append("foo")

        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            len(self.roster),
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

        self.assertTrue(
            self.m.index(2, 0, Qt.QModelIndex()).isValid(),
        )

        self.assertFalse(
            self.m.index(3, 0, Qt.QModelIndex()).isValid(),
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

        self.assertFalse(
            self.m.index(0, 1, Qt.QModelIndex()).isValid(),
        )

    def test_row_count_on_items(self):
        self.assertEqual(
            self.m.rowCount(self.m.index(0, 0, Qt.QModelIndex())),
            0,
        )

    def test_flags(self):
        self.assertEqual(
            self.m.flags(self.m.index(0, 0)),
            Qt.Qt.ItemIsEnabled | Qt.Qt.ItemIsSelectable |
            Qt.Qt.ItemNeverHasChildren | Qt.Qt.ItemIsEditable
        )

    def test_data_returns_label_for_display_role(self):
        for i, item in enumerate(self.roster):
            self.assertEqual(
                self.m.data(self.m.index(i, 0), Qt.Qt.DisplayRole),
                item.label,
            )

    def test_data_returns_label_for_edit_role(self):
        for i, item in enumerate(self.roster):
            self.assertEqual(
                self.m.data(self.m.index(i, 0), Qt.Qt.EditRole),
                item.label,
            )

    def test_data_returns_object_for_object_role(self):
        for i, item in enumerate(self.roster):
            self.assertIs(
                self.m.data(self.m.index(i, 0), models.ROLE_OBJECT),
                item,
            )

    def test_data_returns_sorted_newline_joined_tags_for_tags_role(self):
        self.roster[1].tags = ["foo", "fnord", "bar"]

        self.assertEqual(
            self.m.data(self.m.index(1, 0), models.ROLE_TAGS),
            "bar\nfnord\nfoo\n",
        )

    def test_data_returns_None_for_invalid_index(self):
        self.assertIsNone(self.m.data(Qt.QModelIndex(),
                                      unittest.mock.ANY))

    def test_data_returns_None_for_other_roles(self):
        self.assertIsNone(
            self.m.data(self.m.index(0, 0), unittest.mock.sentinel.other_role)
        )

    def test_setData_emits_on_label_edited(self):
        result = self.m.setData(
            self.m.index(1, 0),
            unittest.mock.sentinel.value,
            Qt.Qt.EditRole,
        )

        self.assertIs(result, False)

        self.listener.on_label_edited.assert_called_once_with(
            self.roster[1],
            unittest.mock.sentinel.value,
        )

    def test_setData_does_not_emit_for_invalid_index(self):
        self.assertIs(
            self.m.setData(
                Qt.QModelIndex(),
                unittest.mock.sentinel.value,
                Qt.Qt.EditRole,
            ),
            False
        )

        self.listener.on_label_edited.assert_not_called()

    def test_setData_does_not_emit_for_unknown_role(self):
        self.assertIs(
            self.m.setData(
                self.m.index(1, 0),
                unittest.mock.sentinel.value,
                unittest.mock.sentinel.role,
            ),
            False,
        )

        self.listener.on_label_edited.assert_not_called()

    def test_emits_dataChanged_on_avatar_change(self):
        self.roster[0].account = unittest.mock.sentinel.account1
        self.roster[0].address = TEST_JID1
        self.roster[1].account = unittest.mock.sentinel.account2
        self.roster[1].address = TEST_JID1
        self.roster[2].account = unittest.mock.sentinel.account1
        self.roster[2].address = TEST_JID2

        cb = unittest.mock.Mock()
        self.m.dataChanged.connect(cb)

        self.m._on_avatar_changed(
            unittest.mock.sentinel.account1,
            TEST_JID2,
        )

        cb.assert_called_once_with(
            self.m.index(2, 0),
            self.m.index(2, 0),
            [Qt.Qt.DecorationRole],
        )

    def test_ignores_avatars_for_non_contact_unknown_addresses(self):
        self.roster[0].account = unittest.mock.sentinel.account1
        self.roster[0].address = TEST_JID1
        self.roster[1].account = unittest.mock.sentinel.account2
        self.roster[1].address = TEST_JID1
        self.roster[2].account = unittest.mock.sentinel.account1
        self.roster[2].address = TEST_JID2

        cb = unittest.mock.Mock()
        self.m.dataChanged.connect(cb)

        self.m._on_avatar_changed(
            unittest.mock.sentinel.account2,
            TEST_JID2,
        )

        cb.assert_not_called()
