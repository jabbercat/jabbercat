import collections.abc
import contextlib
import unittest
import unittest.mock

import PyQt5.Qt as Qt

import aioxmpp

import jclib.identity as identity
import jclib.instrumentable_list
import jclib.roster
import jclib.utils

import jabbercat.avatar

import jabbercat.utils as utils

import jabbercat.models as models

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
                unittest.mock.patch("jabbercat.model_adaptor.ModelListAdaptor")
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
            return unittest.mock.Mock([
                "label",
                "account",
                "address",
            ])

        self.cs = jclib.instrumentable_list.ModelList()
        self.cs.append(make_mock())
        self.cs.append(make_mock())
        self.cs.append(make_mock())
        self.cs.on_unread_count_changed = aioxmpp.callbacks.AdHocSignal()

        self.avatar = unittest.mock.Mock(spec=jabbercat.avatar.AvatarManager)
        self.metadata = unittest.mock.Mock(spec=jclib.metadata.MetadataFrontend)

        self.m = models.ConversationsModel(self.cs, self.avatar, self.metadata)

    def test_uses_model_list_adaptor(self):
        convs = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("jabbercat.model_adaptor.ModelListAdaptor")
            )

            result = models.ConversationsModel(convs,
                                               unittest.mock.Mock(),
                                               unittest.mock.Mock())

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
            value = self.m.data(
                self.m.index(i, self.m.COLUMN_LABEL),
                Qt.Qt.DisplayRole,
            )

            self.metadata.get.assert_called_once_with(
                jclib.roster.RosterMetadata.NAME,
                conv.account,
                conv.address
            )

            self.assertEqual(
                value,
                self.metadata.get(),
            )

            self.metadata.get.reset_mock()

    def test_data_label_column_object_role(self):
        for i, conv in enumerate(self.cs):
            self.assertIs(
                self.m.data(
                    self.m.index(i, self.m.COLUMN_LABEL),
                    models.ROLE_OBJECT,
                ),
                conv,
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

    def test_emits_dataChanged_on_unread_counter_change(self):
        cb = unittest.mock.Mock()
        self.m.dataChanged.connect(cb)

        self.cs.on_unread_count_changed(
            self.cs[1],
            12,
        )

        cb.assert_called_once_with(
            self.m.index(1, 0, Qt.QModelIndex()),
            self.m.index(1, 0, Qt.QModelIndex()),
            [Qt.Qt.DisplayRole],
        )

    def test_emits_dataChanged_on_avatar_change(self):
        self.cs[0].account = unittest.mock.sentinel.account1
        self.cs[0].conversation_address = TEST_JID1
        self.cs[1].account = unittest.mock.sentinel.account2
        self.cs[1].conversation_address = TEST_JID1
        self.cs[2].account = unittest.mock.sentinel.account1
        self.cs[2].conversation_address = TEST_JID2

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
        self.cs[0].account = unittest.mock.sentinel.account1
        self.cs[0].conversation_address = TEST_JID1
        self.cs[1].account = unittest.mock.sentinel.account2
        self.cs[1].conversation_address = TEST_JID1
        self.cs[2].account = unittest.mock.sentinel.account1
        self.cs[2].conversation_address = TEST_JID2

        cb = unittest.mock.Mock()
        self.m.dataChanged.connect(cb)

        self.m._on_avatar_changed(
            unittest.mock.sentinel.account2,
            TEST_JID2,
        )

        cb.assert_not_called()


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
        self.roster = jclib.instrumentable_list.ModelList()
        self.roster.extend(
            unittest.mock.Mock(spec=jclib.roster.AbstractRosterItem)
            for i in range(3)
        )
        self.avatar = unittest.mock.Mock(spec=jabbercat.avatar.AvatarManager)
        self.metadata = unittest.mock.Mock(spec=jclib.metadata.MetadataFrontend)
        self.m = models.RosterModel(self.roster, self.avatar, self.metadata)
        self.listener = make_listener(self.m)

    def test_uses_model_list_adaptor(self):
        items = unittest.mock.Mock([])

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("jabbercat.model_adaptor.ModelListAdaptor")
            )

            result = models.RosterModel(items, self.avatar, self.metadata)

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


class TestRosterFilterModel(unittest.TestCase):
    def setUp(self):
        self.roster = jclib.instrumentable_list.ModelList()
        self.roster.extend(
            unittest.mock.Mock(spec=jclib.roster.AbstractRosterItem)
            for i in range(3)
        )

        self.roster[0].tags = ["foo", "bar"]
        self.roster[1].tags = ["bar"]
        self.roster[2].tags = ["foo", "baz"]

        self.avatar = unittest.mock.Mock(spec=jabbercat.avatar.AvatarManager)
        self.metadata = unittest.mock.Mock(spec=jclib.metadata.MetadataFrontend)
        self.rm = models.RosterModel(self.roster, self.avatar, self.metadata)
        self.rfm = models.RosterFilterModel()
        self.rfm.setSourceModel(self.rm)

        self.tags = jclib.instrumentable_list.ModelList([
            "foo", "bar", "baz",
        ])
        self.tags_model = models.TagsModel(self.tags)
        self.tags_check_model = models.CheckModel()
        self.tags_check_model.setSourceModel(self.tags_model)

        self.rfm.tags_filter_model = self.tags_check_model

        self.listener = make_listener(self.rfm)

    def tearDown(self):
        pass

    def test_filterAcceptsRow_passes_by_default(self):
        self.assertTrue(
            self.rfm.filterAcceptsRow(0, Qt.QModelIndex()),
        )

    def test_filter_by_tags(self):
        self.tags_check_model.setData(
            self.tags_check_model.index(0, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.assertTrue(self.rfm.filterAcceptsRow(0, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(1, Qt.QModelIndex()))
        self.assertTrue(self.rfm.filterAcceptsRow(2, Qt.QModelIndex()))

    def test_filter_by_tags_follows_model(self):
        self.tags_check_model.setData(
            self.tags_check_model.index(0, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.tags_check_model.setData(
            self.tags_check_model.index(1, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.assertTrue(self.rfm.filterAcceptsRow(0, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(1, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(2, Qt.QModelIndex()))

        self.tags_check_model.setData(
            self.tags_check_model.index(0, 0),
            Qt.Qt.Unchecked,
            Qt.Qt.CheckStateRole,
        )

        self.assertTrue(self.rfm.filterAcceptsRow(0, Qt.QModelIndex()))
        self.assertTrue(self.rfm.filterAcceptsRow(1, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(2, Qt.QModelIndex()))

    def test_filter_by_text_matches_on_jid(self):
        self.roster[0].address = TEST_JID1
        self.roster[0].label = "Romeo Montague"
        self.roster[1].address = TEST_JID2
        self.roster[1].label = "Juliet Capulet"
        self.roster[2].address = aioxmpp.JID.fromstr("test@server.example")
        self.roster[2].label = "Meaningful Label"

        self.rfm.filter_by_text = "test"

        self.assertFalse(self.rfm.filterAcceptsRow(0, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(1, Qt.QModelIndex()))
        self.assertTrue(self.rfm.filterAcceptsRow(2, Qt.QModelIndex()))

    def test_filter_by_text_matches_on_label(self):
        self.roster[0].address = TEST_JID1
        self.roster[0].label = "Romeo Montague"
        self.roster[1].address = TEST_JID2
        self.roster[1].label = "Juliet Capulet"
        self.roster[2].address = aioxmpp.JID.fromstr("test@server.example")
        self.roster[2].label = "Meaningful Label"

        self.rfm.filter_by_text = "meaningful"

        self.assertFalse(self.rfm.filterAcceptsRow(0, Qt.QModelIndex()))
        self.assertFalse(self.rfm.filterAcceptsRow(1, Qt.QModelIndex()))
        self.assertTrue(self.rfm.filterAcceptsRow(2, Qt.QModelIndex()))


class TestTagsModel(unittest.TestCase):
    def setUp(self):
        self.tags = jclib.instrumentable_list.ModelList([
            "foo",
            "bar",
        ])
        self.m = models.TagsModel(self.tags)

    def test_uses_model_list_adaptor(self):
        tags = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch("jabbercat.model_adaptor.ModelListAdaptor")
            )

            result = models.TagsModel(tags)

        ModelListAdaptor.assert_called_once_with(tags, result)

    def test_row_count_on_root_follows_tags(self):
        self.assertEqual(
            self.m.rowCount(Qt.QModelIndex()),
            2,
        )

        del self.tags[1]

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

        self.assertFalse(
            self.m.index(0, 1, Qt.QModelIndex()).isValid(),
        )

    def test_row_count_on_items(self):
        self.assertEqual(
            self.m.rowCount(self.m.index(1, 0, Qt.QModelIndex())),
            0,
        )

    def test_data_returns_None_for_invalid_index(self):
        self.assertIsNone(
            self.m.data(Qt.QModelIndex(), Qt.Qt.DisplayRole),
        )

    def test_data_returns_None_for_other_roles(self):
        self.assertIsNone(
            self.m.data(
                self.m.index(1),
                unittest.mock.sentinel.role
            ),
        )

    def test_data_returns_tag_name_for_display_role(self):
        for i, tag in enumerate(self.tags):
            self.assertEqual(
                self.m.data(self.m.index(i), Qt.Qt.DisplayRole),
                tag,
            )

    def test_data_returns_tag_name_for_object_role(self):
        for i, tag in enumerate(self.tags):
            self.assertEqual(
                self.m.data(self.m.index(i), models.ROLE_OBJECT),
                tag,
            )

    def test_data_returns_color_for_decoration_role(self):
        for i, tag in enumerate(self.tags):
            color = utils.text_to_qtcolor(
                jclib.utils.normalise_text_for_hash(tag)
            )
            self.assertEqual(
                self.m.data(self.m.index(i), Qt.Qt.DecorationRole),
                color,
            )

    def test_flags(self):
        self.assertEqual(
            self.m.flags(self.m.index(1)),
            Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled |
            Qt.Qt.ItemNeverHasChildren
        )


class TestCheckModel(unittest.TestCase):
    def setUp(self):
        self.tags = jclib.instrumentable_list.ModelList([
            "foo",
            "bar",
        ])
        self.tm = models.TagsModel(self.tags)
        self.m = models.CheckModel()
        self.m.setSourceModel(self.tm)

        self.listener = unittest.mock.Mock([])
        self.listener.dataChanged = unittest.mock.Mock()
        self.listener.dataChanged.return_value = None
        self.m.dataChanged.connect(self.listener.dataChanged)

    def test_is_identity_proxy_model(self):
        self.assertIsInstance(
            self.m,
            Qt.QIdentityProxyModel,
        )

    def test_check_column_defaults_to_0(self):
        self.assertEqual(self.m.check_column, 0)

    def test_flags_include_user_checkable_for_check_column(self):
        self.assertEqual(
            self.m.flags(self.m.index(0, 0)),
            Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled |
            Qt.Qt.ItemNeverHasChildren | Qt.Qt.ItemIsUserCheckable
        )

    def test_data_returns_None_for_check_state_role_and_invalid_index(self):
        self.assertIsNone(
            self.m.data(Qt.QModelIndex(), Qt.Qt.CheckStateRole),
        )

    def test_data_returns_valid_check_state_for_check_column(self):
        self.assertEqual(
            self.m.data(self.m.index(0, 0), Qt.Qt.CheckStateRole),
            Qt.Qt.Unchecked,
        )

    def test_setData_allows_checking_items(self):
        result = self.m.setData(
            self.m.index(0, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.listener.dataChanged.assert_called_once_with(
            self.m.index(0, 0),
            self.m.index(0, 0),
            [Qt.Qt.CheckStateRole],
        )

        self.assertTrue(result)

        self.assertEqual(
            self.m.data(self.m.index(0, 0), Qt.Qt.CheckStateRole),
            Qt.Qt.Checked,
        )

        self.assertSetEqual({"foo"}, self.m.checked_items)

    def test_check_uncheck_etc(self):
        self.m.setData(
            self.m.index(0, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )
        self.assertSetEqual({"foo"}, self.m.checked_items)

        self.m.setData(
            self.m.index(1, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )
        self.assertSetEqual({"foo", "bar"}, self.m.checked_items)

        self.m.setData(
            self.m.index(1, 0),
            Qt.Qt.Unchecked,
            Qt.Qt.CheckStateRole,
        )
        self.assertSetEqual({"foo"}, self.m.checked_items)

        self.m.setData(
            self.m.index(1, 0),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )
        self.assertSetEqual({"foo", "bar"}, self.m.checked_items)

        self.m.setData(
            self.m.index(0, 0),
            Qt.Qt.Unchecked,
            Qt.Qt.CheckStateRole,
        )
        self.assertSetEqual({"bar"}, self.m.checked_items)

    def test_remove_checked_items_when_removed(self):
        self.m.setData(self.m.index(0, 0), Qt.Qt.Checked, Qt.Qt.CheckStateRole)

        del self.tags[0]

        self.assertSetEqual(set(), self.m.checked_items)

    def test_clear_check_states(self):
        self.m.setData(self.m.index(0, 0), Qt.Qt.Checked, Qt.Qt.CheckStateRole)
        self.m.setData(self.m.index(1, 0), Qt.Qt.Checked, Qt.Qt.CheckStateRole)

        self.listener.dataChanged.reset_mock()

        self.m.clear_check_states()

        self.listener.dataChanged.assert_called_once_with(
            self.m.index(0, 0),
            self.m.index(self.m.rowCount() - 1, 0),
            [Qt.Qt.CheckStateRole]
        )


class TestCheckModelSet(unittest.TestCase):
    def setUp(self):
        self.model = Qt.QStandardItemModel()

        for tag in ["foo", "bar", "baz"]:
            self.model.appendRow(self._make_item(tag))

        self.s = models.CheckModelSet(
            self.model,
            1,
            models.ROLE_OBJECT,
            0,
        )

        self.listener = make_listener(self.s)

    def _make_item(self, tag):
        col1, col2 = Qt.QStandardItem(), Qt.QStandardItem()
        col1.setData("This is " + tag, Qt.Qt.DisplayRole)
        col1.setData(tag, models.ROLE_OBJECT)
        col2.setData(Qt.Qt.Unchecked, Qt.Qt.CheckStateRole)
        col2.setData("filter for this", Qt.Qt.DisplayRole)
        return col1, col2

    def test_empty_by_default(self):
        self.assertCountEqual(set(), self.s.checked)

    def test_follows_checked_items(self):
        self.model.setData(
            self.model.index(1, 1),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.assertCountEqual(
            {"bar"},
            self.s.checked,
        )

        self.listener.on_changed.assert_called_once_with()
        self.listener.reset_mock()

        self.model.setData(
            self.model.index(0, 1),
            Qt.Qt.Checked,
            Qt.Qt.CheckStateRole,
        )

        self.assertCountEqual(
            {"foo", "bar"},
            self.s.checked,
        )

        self.listener.on_changed.assert_called_once_with()
        self.listener.reset_mock()

        self.model.setData(
            self.model.index(1, 1),
            Qt.Qt.Unchecked,
            Qt.Qt.CheckStateRole,
        )

        self.assertCountEqual(
            {"foo"},
            self.s.checked,
        )

        self.listener.on_changed.assert_called_once_with()
        self.listener.reset_mock()

    def test_follows_inserted_items(self):
        col1, col2 = self._make_item("fnord")
        col2.setData(Qt.Qt.Checked, Qt.Qt.CheckStateRole)
        self.model.appendRow([col1, col2])

        self.assertCountEqual(
            {"fnord"},
            self.s.checked,
        )

        self.listener.on_changed.assert_called_once_with()

    def test_does_not_add_non_checked_new_items(self):
        col1, col2 = self._make_item("fnord")
        self.model.appendRow([col1, col2])

        self.assertCountEqual(
            {},
            self.s.checked,
        )

        self.listener.on_changed.assert_not_called()

    def test_follows_removed_items(self):
        self.model.setData(self.model.index(1, 1),
                           Qt.Qt.Checked,
                           Qt.Qt.CheckStateRole)

        self.assertCountEqual(
            {"bar"},
            self.s.checked,
        )

        self.listener.on_changed.reset_mock()

        self.model.invisibleRootItem().removeRow(1)

        self.assertCountEqual(
            set(),
            self.s.checked,
        )

        self.listener.on_changed.assert_called_once_with()

    def test_initialises_properly(self):
        self.model.setData(self.model.index(1, 1),
                           Qt.Qt.Checked,
                           Qt.Qt.CheckStateRole)

        self.s = models.CheckModelSet(
            self.model,
            1,
            models.ROLE_OBJECT,
            0,
        )

        self.assertCountEqual(
            {"bar"},
            self.s.checked,
        )
