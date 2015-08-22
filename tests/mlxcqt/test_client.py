import contextlib
import unittest
import unittest.mock

import mlxc.client

import mlxcqt.client as client

from mlxcqt import Qt


class TestAccountsModel(unittest.TestCase):
    def test_init(self):
        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            ModelListAdaptor = stack.enter_context(
                unittest.mock.patch(
                    "mlxcqt.model_adaptor.ModelListAdaptor",
                    new=base.ModelListAdaptor
                )
            )

            model = client.AccountsModel(base.accounts)

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.ModelListAdaptor(
                    base.accounts._jidlist,
                    model
                )
            ]
        )

    def setUp(self):
        self.base = unittest.mock.Mock()
        self.base.accounts = unittest.mock.MagicMock()
        self.accounts = self.base.accounts
        self.model = client.AccountsModel(self.accounts)

    def test_rowCount_returns_accounts_length_for_invalid_model_index(self):
        self.assertEqual(
            self.model.rowCount(Qt.QModelIndex()),
            len(self.accounts)
        )

    def test_rowCount_returns_zero_for_valid_model_index(self):
        index = self.model.index(0, parent=Qt.QModelIndex())
        self.assertEqual(self.model.rowCount(index), 0)

    def test_data_returns_None_for_invalid_model_index(self):
        self.assertIsNone(
            self.model.data(Qt.QModelIndex(), object())
        )

    def test_data_returns_None_for_non_display_role(self):
        self.accounts.__len__.return_value = 1
        index = self.model.index(0, parent=Qt.QModelIndex())
        self.assertIsNone(
            self.model.data(index, Qt.Qt.ToolTipRole)
        )

    def test_data_returns_str_of_accounts_jid_for_display_role(self):
        self.accounts.__len__.return_value = 1
        index = self.model.index(0, parent=Qt.QModelIndex())
        self.assertEqual(
            self.model.data(index, Qt.Qt.DisplayRole),
            str(self.accounts[0].jid)
        )

    def test_data_returns_None_on_IndexError(self):
        self.accounts.__len__.return_value = 1
        self.accounts.__getitem__.side_effect = IndexError()
        index = self.model.index(0, parent=Qt.QModelIndex())
        self.assertIsNone(
            self.model.data(index, Qt.Qt.DisplayRole)
        )

    def test_headerData_returns_None_for_vertical_orientation(self):
        self.assertIsNone(
            self.model.headerData(0, Qt.Qt.Vertical, Qt.Qt.DisplayRole)
        )

    def test_headerData_returns_None_for_non_zero_section(self):
        self.assertIsNone(
            self.model.headerData(1, Qt.Qt.Horizontal, Qt.Qt.DisplayRole)
        )

    def test_headerData_returns_None_for_non_Display_role(self):
        self.assertIsNone(
            self.model.headerData(0, Qt.Qt.Horizontal, Qt.Qt.ToolTipRole)
        )

    def test_headerData_returns_JID_for_horizontal_section_0_display(self):
        self.assertEqual(
            "JID",
            self.model.headerData(0, Qt.Qt.Horizontal, Qt.Qt.DisplayRole)
        )

    def test_flags_returns_checkability(self):
        self.assertEqual(
            (Qt.Qt.ItemIsEnabled |
             Qt.Qt.ItemIsSelectable |
             Qt.Qt.ItemIsUserCheckable),
            self.model.flags(Qt.QModelIndex())
        )
        self.assertEqual(
            (Qt.Qt.ItemIsEnabled |
             Qt.Qt.ItemIsSelectable |
             Qt.Qt.ItemIsUserCheckable),
            self.model.flags(self.model.index(0, parent=Qt.QModelIndex()))
        )


class TestAccountManager(unittest.TestCase):
    def test_is_mlxc_account_manager(self):
        self.assertTrue(issubclass(
            client.AccountManager,
            mlxc.client.AccountManager
        ))

    def setUp(self):
        self.manager = client.AccountManager()

    def test_qmodel_is_AccountsModel(self):
        self.assertIsInstance(
            self.manager.qmodel,
            client.AccountsModel
        )


class TestClient(unittest.TestCase):
    def test_is_mlxc_client(self):
        self.assertTrue(issubclass(
            client.Client,
            mlxc.client.Client
        ))

    def test_uses_mlxcqt_AccountManager(self):
        self.assertIs(client.Client.AccountManager,
                      client.AccountManager)


# foo
