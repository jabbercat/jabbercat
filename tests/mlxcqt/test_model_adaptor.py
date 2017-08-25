import unittest
import unittest.mock

import mlxcqt.model_adaptor as model_adaptor

from mlxcqt import Qt


class TestModelListAdaptor(unittest.TestCase):
    def setUp(self):
        self.base = unittest.mock.Mock([])
        self.base.model = unittest.mock.Mock()
        self.base.mlist = unittest.mock.Mock([
            "begin_insert_rows",
            "begin_move_rows",
            "begin_remove_rows",
            "end_insert_rows",
            "end_move_rows",
            "end_remove_rows",
            "data_changed",
        ])
        self.adaptor = model_adaptor.ModelListAdaptor(
            self.base.mlist,
            self.base.model)
        self.base.mock_calls.clear()

    def test_attaches_on_init(self):
        self.base.mlist.begin_insert_rows.connect.assert_called_once_with(
            self.adaptor.begin_insert_rows,
        )

        self.base.mlist.begin_move_rows.connect.assert_called_once_with(
            self.adaptor.begin_move_rows,
        )

        self.base.mlist.begin_remove_rows.connect.assert_called_once_with(
            self.adaptor.begin_remove_rows,
        )

        self.base.mlist.end_insert_rows.connect.assert_called_once_with(
            self.adaptor.end_insert_rows,
        )

        self.base.mlist.end_move_rows.connect.assert_called_once_with(
            self.adaptor.end_move_rows,
        )

        self.base.mlist.end_remove_rows.connect.assert_called_once_with(
            self.adaptor.end_remove_rows,
        )

    def test_begin_insert_rows(self):
        null = object()
        index1 = object()
        index2 = object()

        self.adaptor.begin_insert_rows(null, index1, index2)

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.beginInsertRows(
                    Qt.QModelIndex(),
                    index1,
                    index2
                )
            ]
        )

    def test_end_insert_rows(self):
        self.adaptor.end_insert_rows()

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.endInsertRows()
            ]
        )

    def test_begin_remove_rows(self):
        null = object()
        index1 = object()
        index2 = object()

        self.adaptor.begin_remove_rows(null, index1, index2)

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.beginRemoveRows(
                    Qt.QModelIndex(),
                    index1,
                    index2
                )
            ]
        )

    def test_end_remove_rows(self):
        self.adaptor.end_remove_rows()

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.endRemoveRows()
            ]
        )

    def test_begin_move_rows(self):
        srcparent = object()
        srcindex1 = object()
        srcindex2 = object()
        destparent = object()
        destindex = object()

        self.adaptor.begin_move_rows(
            srcparent, srcindex1, srcindex2,
            destparent, destindex)

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.beginMoveRows(
                    Qt.QModelIndex(),
                    srcindex1,
                    srcindex2,
                    Qt.QModelIndex(),
                    destindex
                )
            ]
        )

    def test_end_move_rows(self):
        self.adaptor.end_move_rows()

        calls = list(self.base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.model.endMoveRows()
            ]
        )


# class TestItemModelAdaptor(unittest.TestCase):
#     def setUp(self):
#         self.base = unittest.mock.MagicMock()
#         self.base.handler = unittest.mock.Mock()
#         self.model = model_adaptor.ListModel(
#             self.base.mlist,
#             self.base.handler,
#             parent=None)

#     def test_is_abstract_item_model(self):
#         self.assertIsInstance(
#             self.model,
#             Qt.QAbstractListModel
#         )

#     def test_rowCount(self):
#         result = self.model.rowCount(Qt.QModelIndex())
#         self.assertEqual(
#             result,
#             len(self.base.mlist)
#         )

#     def test_data_for_root_index(self):
#         role = object()
#         self.assertIsNone(self.model.data(Qt.QModelIndex(), role))

#     def test_data_for_valid_index(self):
#         role = object()

#         self.base.mlist.__len__.return_value = 10
#         self.base.mock_calls.clear()

#         result = self.model.data(self.model.index(5), role)
#         calls = list(self.base.mock_calls)

#         self.assertSequenceEqual(
#             calls[2:],  # first are __len__ and __getitem__
#             [
#                 unittest.mock.call.handler.get_data(
#                     self.base.mlist[5],
#                     role
#                 ),
#             ]
#         )

#         self.assertEqual(
#             result,
#             self.base.handler.get_data()
#         )

#     def test_headerData(self):
#         section = object()
#         orientation = object()
#         role = object()

#         result = self.model.headerData(
#             section, orientation, role
#         )

#         self.assertSequenceEqual(
#             self.base.mock_calls,
#             [
#                 unittest.mock.call.handler.get_header_data(
#                     section, orientation, role
#                 ),
#             ]
#         )

#     def tearDown(self):
#         del self.model
#         del self.base
