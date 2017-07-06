import unittest
import unittest.mock

import PyQt5.Qt as Qt

import mlxcqt.models as models


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
        for cb in ["rowsAboutToBeInserted", "rowsInserted"]:
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
