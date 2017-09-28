import contextlib
import unittest
import unittest.mock

import jclib.instrumentable_list

import jabbercat.models

from jabbercat import Qt

import jabbercat.widgets.tagsmenu as tagsmenu


class Test_color_icon(unittest.TestCase):
    def setUp(self):
        self.QPixmap = unittest.mock.Mock(["__call__"])
        self.pixmap = unittest.mock.Mock(spec=Qt.QPixmap)
        self.QPixmap.return_value = self.pixmap

        self.QIcon = unittest.mock.Mock(["__call__"])
        self.icon = unittest.mock.Mock(spec=Qt.QIcon)
        self.QIcon.return_value = self.icon

        self.patches = [
            unittest.mock.patch("jabbercat.Qt.QPixmap", new=self.QPixmap),
            unittest.mock.patch("jabbercat.Qt.QIcon", new=self.QIcon),
        ]

        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_creates_filled_icon(self):
        color = unittest.mock.Mock(spec=Qt.QColor)

        result = tagsmenu._color_icon(color)

        self.QPixmap.assert_called_once_with(16, 16)
        self.pixmap.fill.assert_called_once_with(color)
        self.QIcon.assert_called_once_with(self.pixmap)

        self.assertEqual(self.icon, result)


class TestTagsMenu(unittest.TestCase):
    def setUp(self):
        self.tags = jclib.instrumentable_list.ModelList([
            "foo",
            "bar",
            "baz",
        ])

        self.tags_model = jabbercat.models.TagsModel(self.tags)
        self.cm = jabbercat.models.CheckModel()
        self.cm.setSourceModel(self.tags_model)

        self.m = tagsmenu.TagsMenu()
        self.m.source_model = self.cm

    def tearDown(self):
        pass

    def test_actions_for_model_items(self):
        actions = self.m.actions()
        for i, tag in enumerate(self.tags):
            action = actions[i + self.m.TAGS_OFFSET]
            self.assertEqual(action.text(), tag)
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.isChecked())

    def test_model_changes_update_actions(self):
        self.cm.setData(self.cm.index(1, 0),
                        Qt.Qt.Checked,
                        Qt.Qt.CheckStateRole)

        self.assertTrue(self.m.actions()[1 + self.m.TAGS_OFFSET].isChecked())

    def test_triggering_actions_changes_model(self):
        action = self.m.actions()[self.m.TAGS_OFFSET + 2]

        action.triggered.emit(True)

        self.assertEqual(
            self.cm.data(self.cm.index(2, 0), Qt.Qt.CheckStateRole),
            Qt.Qt.Checked,
        )

        action.triggered.emit(False)

        self.assertEqual(
            self.cm.data(self.cm.index(2, 0), Qt.Qt.CheckStateRole),
            Qt.Qt.Unchecked,
        )

    def test_remove_actions_following_model(self):
        del self.tags[1]

        actions = self.m.actions()
        for i, tag in enumerate(self.tags):
            action = actions[i + self.m.TAGS_OFFSET]
            self.assertEqual(action.text(), tag)
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.isChecked())

    def test_insert_actions_following_model(self):
        self.tags.insert(1, "fnord")

        actions = self.m.actions()
        for i, tag in enumerate(self.tags):
            action = actions[i + self.m.TAGS_OFFSET]
            self.assertEqual(action.text(), tag)
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.isChecked())

    def test_append_actions_following_model(self):
        self.tags.append("fnord")

        actions = self.m.actions()
        for i, tag in enumerate(self.tags):
            action = actions[i + self.m.TAGS_OFFSET]
            self.assertEqual(action.text(), tag)
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.isChecked())

    def test_follows_move_in_model(self):
        self.tags.move(2, 0)

        actions = self.m.actions()
        for i, tag in enumerate(self.tags):
            action = actions[i + self.m.TAGS_OFFSET]
            self.assertEqual(action.text(), tag)
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.isChecked())
