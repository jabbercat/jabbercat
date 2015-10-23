import contextlib
import unittest
import unittest.mock

import aioxmpp.callbacks

import mlxcqt.Qt as Qt
import mlxcqt.utils as utils


def mk_model_mock():
    mock = unittest.mock.Mock([
        "buddy",
        "canDropMimeData",
        "canFetchMore",
        "columnCount",
        "data",
        "dropMimeData",
        "fetchMore",
        "flags",
        "hasChildren",
        "hasIndex",
        "headerData",
        "index",
        "insertColumn",
        "insertColumns",
        "insertRow",
        "insertRows",
        "itemData",
        "match",
        "mimeData",
        "mimeTypes",
        "moveColumn",
        "moveColumns",
        "moveRow",
        "moveRows",
        "parent",
        "removeColumn",
        "removeColumns",
        "removeRow",
        "removeRows",
        "roleNames",
        "rowCount",
        "setData",
        "setHeaderData",
        "setItemdata",
        "sibling",
        "sort",
        "span",
        "supportedDragActions",
        "supportedDropActions"
    ])

    for signal_name in [
            "columnsAboutToBeInserted",
            "columnsAboutToBeMoved",
            "columnsAboutToBeRemoved",
            "columnsInserted",
            "columnsMoved",
            "columnsRemoved",
            "dataChanged",
            "headerDataChanged",
            "layoutAboutToBeChanged",
            "layoutChanged",
            "modelAboutToBeReset",
            "modelReset",
            "rowsAboutToBeInserted",
            "rowsAboutToBeMoved",
            "rowsAboutToBeRemoved",
            "rowsInserted",
            "rowsMoved",
            "rowsRemoved"
            ]:
        setattr(mock, signal_name, aioxmpp.callbacks.AdHocSignal())
    return mock


class TestJoinedListsModel(unittest.TestCase):
    def setUp(self):
        self.base = unittest.mock.Mock()
        self.base.model1 = mk_model_mock()
        self.base.model1.rowCount.return_value = 2
        self.base.model2 = mk_model_mock()
        self.base.model2.rowCount.return_value = 3
        self.base.model3 = mk_model_mock()
        self.base.model3.rowCount.return_value = 1
        self.model1 = self.base.model1
        self.model2 = self.base.model2
        self.model3 = self.base.model3
        self.model = utils.JoinedListsModel(
            self.model1,
            self.model2,
            self.model3
        )

        self.delegate_map = [
            (self.model1, 0),
            (self.model1, 1),
            (self.model2, 0),
            (self.model2, 1),
            (self.model2, 2),
            (self.model3, 0)
        ]


    def test_is_QAbstractListModel(self):
        self.assertIsInstance(self.model, Qt.QAbstractListModel)

    def test_insert_column_returns_false(self):
        self.assertFalse(self.model.insertColumn(0))

    def test_insert_columns_returns_false(self):
        self.assertFalse(self.model.insertColumns(0, 10))

    def test_insert_row_returns_false(self):
        self.assertFalse(self.model.insertRow(0))

    def test_insert_rows_returns_false(self):
        self.assertFalse(self.model.insertRows(0, 10))

    def test_rowCount_with_invalid_index_returns_sum(self):
        self.assertEqual(
            self.model.rowCount(),
            6
        )

    def test_rowCount_with_valid_index_and_invalid_parent_returns_zero(self):
        self.assertEqual(self.model.rowCount(self.model.index(0)), 0)

    # def test_rowCount_with_valid_index_and_invalid_parent_delegates(self):
    #     for i, (model, model_index) in enumerate(self.delegate_map):
    #         index = self.model.index(i)
    #         self.assertTrue(index.isValid())
    #         self.assertEqual(index.row(), i)
    #         self.model.rowCount(index)
    #         model.rowCount.assert_called_with(
    #             model.index(model_index)
    #         )

    def test_data_delegates_to_models(self):
        role = object()
        for i, (model, model_index) in enumerate(self.delegate_map):
            index = self.model.index(i)
            self.assertTrue(index.isValid())
            self.assertEqual(index.row(), i)
            result = self.model.data(index, role)
            model.index.assert_called_with(model_index, 0)
            model.data.assert_called_with(
                model.index(model_index),
                role
            )
            self.assertEqual(result, model.data())

    def test_flags_delegates_to_models(self):
        for i, (model, model_index) in enumerate(self.delegate_map):
            index = self.model.index(i)
            self.assertTrue(index.isValid())
            self.assertEqual(index.row(), i)
            result = self.model.flags(index)
            model.index.assert_called_with(model_index, 0)
            model.flags.assert_called_with(
                model.index(model_index)
            )
            self.assertEqual(result, model.flags())

    def test_simple_events_are_reemitted(self):
        simple_events = [
            ("rowsInserted", "endInsertRows"),
            ("rowsMoved",  "endMoveRows"),
            ("rowsRemoved", "endRemoveRows"),
            ("columnsInserted", "endInsertColumns"),
            ("columnsMoved", "endMoveColumns"),
            ("columnsRemoved", "endRemoveColumns"),
            ("modelAboutToBeReset", "beginResetModel"),
            ("modelReset", "endResetModel"),
        ]

        for signal_name, to_call in simple_events:
            with unittest.mock.patch.object(
                    self.model,
                    to_call) as mock:
                for model in [self.model1, self.model2, self.model3]:
                    getattr(model, signal_name)()

            self.assertSequenceEqual(
                mock.mock_calls,
                [unittest.mock.call()]*3,
                "{} not forwarded correctly to {}".format(
                    signal_name,
                    to_call)
            )

    def test_rowsAboutToBeInserted_is_handled(self):
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginInsertRows",
                new=base.beginInsertRows
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endInsertRows",
                new=base.endInsertRows
            ))

            self.model2.rowsAboutToBeInserted(
                Qt.QModelIndex(),
                1, 3
            )
            self.model2.rowCount.return_value = 6
            self.model2.rowsInserted()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.beginInsertRows(
                    Qt.QModelIndex(),
                    3, 5
                ),
                unittest.mock.call.endInsertRows()
            ]
        )
        self.assertEqual(9, self.model.rowCount())

    def test_rowsAboutToBeMoved_is_handled(self):
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginMoveRows",
                new=base.beginMoveRows
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endMoveRows",
                new=base.endMoveRows
            ))

            self.model2.rowsAboutToBeMoved(
                Qt.QModelIndex(),
                0, 1,
                Qt.QModelIndex(),
                2
            )
            self.model2.rowsMoved()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.beginMoveRows(
                    Qt.QModelIndex(),
                    2, 3,
                    Qt.QModelIndex(),
                    4
                ),
                unittest.mock.call.endMoveRows()
            ]
        )
        self.assertEqual(6, self.model.rowCount())

    def test_rowsAboutToBeRemoved_is_handled(self):
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "beginRemoveRows",
                new=base.beginRemoveRows
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.model,
                "endRemoveRows",
                new=base.endRemoveRows
            ))

            self.model2.rowsAboutToBeRemoved(
                Qt.QModelIndex(),
                0, 2
            )
            self.model2.rowsRemoved()

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.beginRemoveRows(
                    Qt.QModelIndex(),
                    2, 4
                ),
                unittest.mock.call.endRemoveRows()
            ]
        )
        self.assertEqual(3, self.model.rowCount())


class TestDictItemModel(unittest.TestCase):
    def test_init(self):
        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch(
                    "mlxcqt.model_adaptor.ModelListAdaptor",
                    new=base.ModelListAdaptor
                )
            )

            model = utils.DictItemModel(base.items)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.ModelListAdaptor(
                    base.items,
                    model
                ),
            ]
        )

    def setUp(self):
        self.items = unittest.mock.MagicMock()
        self.model = utils.DictItemModel(self.items)
        self.items.mock_calls.clear()

    def test_is_QAbstractListModel(self):
        self.assertIsInstance(self.model, Qt.QAbstractListModel)

    def test_rowCount_returns_length_for_invalid_index(self):
        self.assertEqual(
            self.model.rowCount(Qt.QModelIndex()),
            len(self.items)
        )

    def test_rowCount_returns_zero_for_valid_index(self):
        self.items.__len__.return_value = 2
        self.assertEqual(self.model.rowCount(self.model.index(0)), 0)

    def test_data_returns_dict_entry(self):
        self.items.__len__.return_value = 2
        index = self.model.index(0)
        role = object()
        self.items.mock_calls.clear()
        value = self.model.data(index, role)
        self.assertSequenceEqual(
            self.items.mock_calls,
            [
                unittest.mock._Call(("__getitem__", (0,), {})),
                unittest.mock._Call(("__getitem__().get", (role,), {})),
            ]
        )

    def test_flags_returns_dict_entry_with_sensible_default(self):
        self.items.__len__.return_value = 2
        index = self.model.index(0)
        self.items.mock_calls.clear()
        value = self.model.flags(index)
        self.assertSequenceEqual(
            self.items.mock_calls,
            [
                unittest.mock._Call(("__getitem__", (0,), {})),
                unittest.mock._Call((
                    "__getitem__().get",
                    ("flags", Qt.Qt.ItemIsSelectable | Qt.Qt.ItemIsEnabled),
                    {})),
            ]
        )


class TestJIDValidator(unittest.TestCase):
    def setUp(self):
        self.validator = utils.JIDValidator()

    def test_return_intermediate_for_partial_jid(self):
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Intermediate, "foo@", pos),
            self.validator.validate("foo@", pos)
        )
        self.assertEqual(
            (Qt.QValidator.Intermediate, "@bar", pos),
            self.validator.validate("@bar", pos)
        )
        self.assertEqual(
            (Qt.QValidator.Intermediate, "foo/", pos),
            self.validator.validate("foo/", pos)
        )
        self.assertEqual(
            (Qt.QValidator.Intermediate, "/foo", pos),
            self.validator.validate("/foo", pos)
        )

    def test_accept_complete_jid(self):
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Acceptable, "foo@bar.baz/fnord", pos),
            self.validator.validate("foo@bar.baz/fnord", pos)
        )
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Acceptable, "foo@bar.baz", pos),
            self.validator.validate("foo@bar.baz", pos)
        )
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Acceptable, "bar.baz/fnord", pos),
            self.validator.validate("bar.baz/fnord", pos)
        )
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Acceptable, "bar.baz", pos),
            self.validator.validate("bar.baz", pos)
        )
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Acceptable, "a@foo/bar/", pos),
            self.validator.validate("a@foo/bar/", pos)
        )

    def test_reject_too_long_jids(self):
        pos = object()
        self.assertEqual(
            (Qt.QValidator.Invalid, "fooo"*1024, pos),
            self.validator.validate("fooo"*1024, pos)
        )

