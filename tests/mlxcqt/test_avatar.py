import contextlib
import unittest
import unittest.mock

import aioxmpp

import mlxc.identity

import mlxcqt.avatar as avatar
import mlxcqt.Qt as Qt

from aioxmpp.testutils import (
    make_connected_client,
    make_listener,
    CoroutineMock,
    run_coroutine,
)


TEST_JID1 = aioxmpp.JID.fromstr("romeo@montague.lit")
TEST_JID2 = aioxmpp.JID.fromstr("juliet@capulet.lit")


class XMPPAvatarProvider(unittest.TestCase):
    def setUp(self):
        self.account = unittest.mock.Mock(spec=mlxc.identity.Account)
        self.avatar = unittest.mock.Mock(spec=aioxmpp.AvatarService)
        self.avatar.get_avatar_metadata = CoroutineMock()
        self.ap = avatar.XMPPAvatarProvider(self.account)
        self.listener = make_listener(self.ap)

    def _prep_client(self):
        client = make_connected_client()
        client.mock_services[aioxmpp.AvatarService] = self.avatar
        return client

    def test_prepare_client_summons_avatar_and_connects_signals(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        self.avatar.on_metadata_changed.connect.assert_called_once_with(
            self.ap._on_metadata_changed,
        )

    def test_shutdown_client_disconnects_signals(self):
        client = self._prep_client()

        self.ap.prepare_client(client)
        self.ap.shutdown_client(client)

        self.avatar.on_metadata_changed.disconnect.assert_called_once_with(
            self.avatar.on_metadata_changed.connect()
        )

    def test__on_metadata_changed_emits_signal(self):
        self.ap._on_metadata_changed(TEST_JID1, unittest.mock.sentinel.metadata)
        self.listener.on_avatar_changed.assert_called_once_with(TEST_JID1)

    def test__get_image_bytes_uses_data_from_first_image_png(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.mime_type = "image/jpeg"
        base.avatar1.nbytes = 4096
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.mime_type = "image/png"
        base.avatar2.nbytes = 4096
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.mime_type = "image/png"
        base.avatar3.nbytes = 4096
        base.avatar3.get_image_bytes = CoroutineMock()

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1, base.avatar2, base.avatar3,
        ]

        result = run_coroutine(
            self.ap._get_image_bytes(unittest.mock.sentinel.address)
        )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_not_called()

        self.assertEqual(result, unittest.mock.sentinel.image_bytes)

    def test__get_image_bytes_tries_next_if_one_is_not_implemented(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.mime_type = "image/jpeg"
        base.avatar1.nbytes = 4096
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.mime_type = "image/png"
        base.avatar2.nbytes = 4096
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = NotImplementedError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.mime_type = "image/png"
        base.avatar3.nbytes = 4096
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1, base.avatar2, base.avatar3,
        ]

        result = run_coroutine(
            self.ap._get_image_bytes(unittest.mock.sentinel.address)
        )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        self.assertEqual(result, unittest.mock.sentinel.image_bytes)

    def test__get_image_bytes_tries_next_if_one_fails(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.mime_type = "image/jpeg"
        base.avatar1.nbytes = 4096
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.mime_type = "image/png"
        base.avatar2.nbytes = 4096
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = RuntimeError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.mime_type = "image/png"
        base.avatar3.nbytes = 4096
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1, base.avatar2, base.avatar3,
        ]

        result = run_coroutine(
            self.ap._get_image_bytes(unittest.mock.sentinel.address)
        )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        self.assertEqual(result, unittest.mock.sentinel.image_bytes)

    def test__get_image_bytes_returns_none_if_all_fail(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.mime_type = "image/jpeg"
        base.avatar1.nbytes = 4096
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.mime_type = "image/png"
        base.avatar2.nbytes = 4096
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = RuntimeError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.mime_type = "image/png"
        base.avatar3.nbytes = 4096
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.side_effect = RuntimeError()

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1, base.avatar2, base.avatar3,
        ]

        result = run_coroutine(
            self.ap._get_image_bytes(unittest.mock.sentinel.address)
        )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        self.assertIsNone(result)

    def test_fetch_avatar_returns_None_if__get_image_bytes_returns_None(self):
        with contextlib.ExitStack() as stack:
            _get_image_bytes = stack.enter_context(unittest.mock.patch.object(
                self.ap, "_get_image_bytes",
                new=CoroutineMock()
            ))
            _get_image_bytes.return_value = None

            self.assertIsNone(
                run_coroutine(self.ap.fetch_avatar(
                    unittest.mock.sentinel.address,
                ))
            )

        _get_image_bytes.assert_called_once_with(
            unittest.mock.sentinel.address
        )

    def test_fetch_avatar_uses__get_image_bytes(self):
        with contextlib.ExitStack() as stack:
            _get_image_bytes = stack.enter_context(unittest.mock.patch.object(
                self.ap, "_get_image_bytes",
                new=CoroutineMock()
            ))
            _get_image_bytes.return_value = unittest.mock.sentinel.image_bytes

            QImage = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QImage"
            ))

            QPicture = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPicture"
            ))

            QPainter = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPainter"
            ))

            result = run_coroutine(self.ap.fetch_avatar(
                unittest.mock.sentinel.address
            ))

        _get_image_bytes.assert_called_once_with(
            unittest.mock.sentinel.address
        )

        QImage.fromData.assert_called_once_with(
            unittest.mock.sentinel.image_bytes,
            "PNG",
        )

        QPicture.assert_called_once_with()

        QPainter.assert_called_once_with(QPicture())
        QPainter().drawImage.assert_called_once_with(
            Qt.QRectF(0, 0, 48, 48),
            QImage.fromData(),
        )
        QPainter().end()

        self.assertEqual(result, QPicture())


class Testfirst_grapheme(unittest.TestCase):
    def test_simple_cases(self):
        self.assertEqual(
            avatar.first_grapheme("eris"),
            "e"
        )

        self.assertEqual(
            avatar.first_grapheme("!foo"),
            "!"
        )

        self.assertEqual(
            avatar.first_grapheme("100"),
            "1"
        )

        self.assertEqual(
            avatar.first_grapheme("#foo"),
            "#"
        )

        self.assertEqual(
            avatar.first_grapheme("éducation"),
            "é"
        )

    def test_decomposed(self):
        self.assertEqual(
            avatar.first_grapheme("éducation"),
            "é"
        )

    def test_emoji_simple(self):
        self.assertEqual(
            avatar.first_grapheme("💂🏾, right?"),
            "💂🏾"
        )

    @unittest.expectedFailure
    def test_emoji_human_skintone_occupation(self):
        self.assertEqual(
            avatar.first_grapheme("👩🏿‍🎓, tricky!"),
            "👩🏿‍🎓",
        )

    @unittest.expectedFailure
    def test_emoji_occupation_skintone_gender(self):
        self.assertEqual(
            avatar.first_grapheme("🕵️‍♀️, does it work?"),
            "🕵️‍♀️"
        )


class Testrender_dummy_avatar_base(unittest.TestCase):
    def test_renders_rect_with_proper_pen(self):
        painter = unittest.mock.Mock(spec=Qt.QPainter)

        with contextlib.ExitStack() as stack:
            QPen = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPen"
            ))

            QColor = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QColor"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QRectF"
            ))

            avatar.render_dummy_avatar_base(
                painter,
                unittest.mock.sentinel.colour,
                unittest.mock.sentinel.size,
            )

        QColor.assert_called_once_with(unittest.mock.sentinel.colour)
        QColor().setAlpha.assert_called_once_with(127)

        QPen.assert_called_once_with(QColor())
        painter.setPen.assert_called_once_with(QPen())
        painter.setBrush.assert_called_once_with(
            unittest.mock.sentinel.colour,
        )

        QRectF.assert_called_once_with(
            0, 0,
            unittest.mock.sentinel.size,
            unittest.mock.sentinel.size,
        )

        painter.drawRect.assert_called_once_with(QRectF())


class Testrender_dummy_avatar_grapheme(unittest.TestCase):
    def test_renders_with_antialias_and_proper_font_size(self):
        painter = unittest.mock.Mock(spec=Qt.QPainter)
        size = 32

        with contextlib.ExitStack() as stack:
            QFont = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QFont"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QRectF"
            ))

            QPen = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPen"
            ))

            QBrush = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QBrush"
            ))

            QColor = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QColor"
            ))

            avatar.render_dummy_avatar_grapheme(
                painter,
                unittest.mock.sentinel.grapheme,
                unittest.mock.sentinel.base_font,
                size,
            )

        painter.setRenderHint.assert_called_once_with(
            Qt.QPainter.Antialiasing, True,
        )

        QColor.assert_called_once_with(255, 255, 255, 255)
        QPen.assert_called_once_with(QColor())
        QBrush.assert_called_once_with()
        painter.setPen.assert_called_once_with(QPen())
        painter.setBrush.assert_called_once_with(QBrush())

        QFont.assert_called_once_with(unittest.mock.sentinel.base_font)
        QFont().setPixelSize.assert_called_once_with(
            size * 0.85 - 4
        )
        QFont().setWeight.assert_called_once_with(QFont.Thin)

        painter.setFont.assert_called_once_with(QFont())

        QRectF.assert_called_once_with(
            2, 2,
            size - 4,
            size - 4,
        )

        painter.drawText.assert_called_once_with(
            QRectF(),
            Qt.Qt.AlignHCenter | Qt.Qt.AlignVCenter | Qt.Qt.TextSingleLine,
            unittest.mock.sentinel.grapheme,
        )


class Testrender_dummy_avatar(unittest.TestCase):
    def test_uses_other_render_functions_on_new_picture(self):
        with contextlib.ExitStack() as stack:
            QPainter = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPainter"
            ))

            QPicture = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QPicture"
            ))

            first_grapheme = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.first_grapheme"
            ))

            render_dummy_avatar_base = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar_base"
            ))

            render_dummy_avatar_grapheme = stack.enter_context(
                unittest.mock.patch(
                    "mlxcqt.avatar.render_dummy_avatar_grapheme"
                )
            )

            text_to_qtcolor = stack.enter_context(unittest.mock.patch(
                "mlxcqt.utils.text_to_qtcolor"
            ))

            normalise_text_for_hash = stack.enter_context(unittest.mock.patch(
                "mlxc.utils.normalise_text_for_hash"
            ))

            result = avatar.render_dummy_avatar(
                unittest.mock.sentinel.font,
                unittest.mock.sentinel.name,
                unittest.mock.sentinel.size,
            )

        normalise_text_for_hash.assert_called_once_with(
            unittest.mock.sentinel.name
        )
        text_to_qtcolor.assert_called_once_with(normalise_text_for_hash())

        first_grapheme.assert_called_once_with(unittest.mock.sentinel.name)

        QPicture.assert_called_once_with()
        QPainter.assert_called_once_with(QPicture())

        render_dummy_avatar_base.assert_called_once_with(
            QPainter(),
            text_to_qtcolor(),
            unittest.mock.sentinel.size,
        )

        render_dummy_avatar_grapheme.assert_called_once_with(
            QPainter(),
            first_grapheme(),
            unittest.mock.sentinel.font,
            unittest.mock.sentinel.size,
        )

        self.assertEqual(result, QPicture())


class TestRosterNameAvatarProvider(unittest.TestCase):
    def setUp(self):
        self.roster = unittest.mock.Mock(spec=aioxmpp.RosterClient)
        self.roster.items = {}
        self.ag = avatar.RosterNameAvatarProvider()
        self.listener = make_listener(self.ag)

    def _prep_client(self):
        client = make_connected_client()
        client.mock_services[aioxmpp.RosterClient] = self.roster
        return client

    def test_prepare_client_summons_roster_and_connects_signals(self):
        client = self._prep_client()

        self.ag.prepare_client(client)

        self.roster.on_entry_added.connect.assert_called_once_with(
            self.ag._on_entry_updated,
        )

        self.roster.on_entry_name_changed.connect.assert_called_once_with(
            self.ag._on_entry_updated,
        )

        self.roster.on_entry_removed.connect.assert_called_once_with(
            self.ag._on_entry_updated,
        )

    def test_shutdown_client_disconnects_signals(self):
        client = self._prep_client()

        self.ag.prepare_client(client)
        self.ag.shutdown_client(client)

        self.roster.on_entry_added.disconnect.assert_called_once_with(
            self.roster.on_entry_added.connect()
        )

        self.roster.on_entry_name_changed.disconnect.assert_called_once_with(
            self.roster.on_entry_name_changed.connect()
        )

        self.roster.on_entry_removed.disconnect.assert_called_once_with(
            self.roster.on_entry_removed.connect()
        )

    def test_get_avatar_prefers_name_from_roster_service(self):
        client = self._prep_client()

        item = unittest.mock.Mock(spec=aioxmpp.roster.service.Item)
        item.name = unittest.mock.sentinel.name
        self.roster.items[TEST_JID1] = item

        self.ag.prepare_client(client)

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            result = self.ag.get_avatar(
                TEST_JID1,
                unittest.mock.sentinel.font,
            )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.font,
            unittest.mock.sentinel.name,
            48,
        )

        self.assertEqual(result, render_dummy_avatar())

    def test_get_avatar_returns_None_if_entry_not_available(self):
        client = self._prep_client()

        item = unittest.mock.Mock(spec=aioxmpp.roster.service.Item)
        item.name = unittest.mock.sentinel.name
        self.roster.items[TEST_JID1] = item

        self.ag.prepare_client(client)

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            result = self.ag.get_avatar(
                TEST_JID2,
                unittest.mock.sentinel.font,
            )

        render_dummy_avatar.assert_not_called()

        self.assertIsNone(result)

    def test_get_avatar_returns_None_if_name_not_available(self):
        client = self._prep_client()

        item = unittest.mock.Mock(spec=aioxmpp.roster.service.Item)
        item.name = None
        self.roster.items[TEST_JID1] = item

        self.ag.prepare_client(client)

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            result = self.ag.get_avatar(
                TEST_JID1,
                unittest.mock.sentinel.font,
            )

        render_dummy_avatar.assert_not_called()

        self.assertIsNone(result)

    def test_get_avatar_returns_None_if_client_not_set_up(self):
        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            result = self.ag.get_avatar(
                unittest.mock.sentinel.address,
                unittest.mock.sentinel.font,
            )

        render_dummy_avatar.assert_not_called()

        self.assertIsNone(result)

    def test__on_entry_updated_emits_on_avatar_changed(self):
        item = unittest.mock.Mock(spec=aioxmpp.roster.Item)
        item.jid = TEST_JID1
        self.ag._on_entry_updated(item)
        self.listener.on_avatar_changed.assert_called_once_with(item.jid)


class TestAvatarManager(unittest.TestCase):
    def setUp(self):
        self.client = unittest.mock.Mock(spec=mlxc.client.Client)
        self.writeman = unittest.mock.Mock(spec=mlxc.storage.WriteManager)
        self.am = avatar.AvatarManager(self.client, self.writeman)
        self.listener = make_listener(self.am)

    def test_get_avatar_font_uses_general_font(self):
        with contextlib.ExitStack() as stack:
            QFontDatabase = stack.enter_context(unittest.mock.patch(
                "mlxcqt.Qt.QFontDatabase",
            ))

            result = self.am.get_avatar_font()

        QFontDatabase.systemFont.assert_called_once_with(
            QFontDatabase.GeneralFont,
        )

        self.assertEqual(result, QFontDatabase.systemFont())

    def test_connects_to_client_signals(self):
        self.client.on_client_prepare.connect.assert_called_once_with(
            self.am._prepare_client,
        )

        self.client.on_client_stopped.connect.assert_called_once_with(
            self.am._shutdown_client,
        )

    def test__prepare_client_creates_RosterNameAvatarProvider_and_links_it(
            self):
        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.RosterNameAvatarProvider",
            ))

            _on_backend_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_backend_avatar_changed")
            )

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                unittest.mock.sentinel.client,
            )

        RosterNameAvatarProvider.assert_called_once_with()
        RosterNameAvatarProvider().prepare_client.assert_called_once_with(
            unittest.mock.sentinel.client
        )
        RosterNameAvatarProvider().on_avatar_changed.connect\
            .assert_called_once_with(
                unittest.mock.ANY)

        _, (cb, ), _ = \
            RosterNameAvatarProvider().on_avatar_changed.connect.mock_calls[0]

        _on_backend_avatar_changed.assert_not_called()
        cb(unittest.mock.sentinel.address)
        _on_backend_avatar_changed.assert_called_once_with(
            unittest.mock.sentinel.account,
            unittest.mock.sentinel.address,
        )

    def test__shutdown_client_unlinks_RosterNameAvatarProvider(self):
        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.RosterNameAvatarProvider",
            ))

            _on_backend_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_backend_avatar_changed")
            )

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                unittest.mock.sentinel.client,
            )

            RosterNameAvatarProvider().on_avatar_changed.disconnect\
                .assert_not_called()

            self.am._shutdown_client(
                unittest.mock.sentinel.account,
                unittest.mock.sentinel.client,
            )

        RosterNameAvatarProvider().on_avatar_changed.disconnect\
            .assert_called_once_with(
                RosterNameAvatarProvider().on_avatar_changed.connect())

    def test__on_backend_avatar_changed_emits_on_avatar_changed(self):
        self.am._on_backend_avatar_changed(
            unittest.mock.sentinel.account,
            unittest.mock.sentinel.address,
        )

        self.listener.on_avatar_changed.assert_called_once_with(
            unittest.mock.sentinel.account,
            unittest.mock.sentinel.address,
        )

    def test_get_avatar_falls_back_to_render_dummy_avatar_if_account_unknown(
            self):
        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
            )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.avatar_font,
            str(TEST_JID1),
            48,
        )

    def test_get_avatar_falls_back_to_render_dummy_avatar_others_failed(self):
        client = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = None

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
            )

        RosterNameAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
            unittest.mock.sentinel.avatar_font,
        )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.avatar_font,
            str(TEST_JID1),
            48,
        )

    def test_get_avatar_falls_passes_name_surrogate_to_render_dummy(self):
        client = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = None

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "mlxcqt.avatar.render_dummy_avatar"
            ))

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
                unittest.mock.sentinel.name_surrogate,
            )

        RosterNameAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
            unittest.mock.sentinel.avatar_font,
        )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.avatar_font,
            unittest.mock.sentinel.name_surrogate,
            48,
        )

    def test__fetch_avatar_and_emit_signal(self):
        fetch_func = CoroutineMock()
        fetch_func.return_value = unittest.mock.Mock(spec=Qt.QPicture)
