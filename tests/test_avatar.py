import asyncio
import contextlib
import itertools
import unittest
import unittest.mock

import aioxmpp

import jclib.identity

import jabbercat.avatar as avatar
import jabbercat.Qt as Qt

from aioxmpp.testutils import (
    make_connected_client,
    make_listener,
    CoroutineMock,
    run_coroutine,
)


TEST_JID1 = aioxmpp.JID.fromstr("romeo@montague.lit")
TEST_JID2 = aioxmpp.JID.fromstr("juliet@capulet.lit")


class Testrender_avatar_image(unittest.TestCase):
    def test_paints_on_qpicture(self):
        image = unittest.mock.Mock(["isNull"])
        image.isNull.return_value = False

        with contextlib.ExitStack() as stack:
            QPicture = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPicture"
            ))

            QPainter = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPainter"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QRectF"
            ))

            result = avatar.render_avatar_image(
                image,
                unittest.mock.sentinel.size,
            )

        QRectF.assert_called_once_with(
            0, 0,
            unittest.mock.sentinel.size,
            unittest.mock.sentinel.size
        )

        QPicture.assert_called_once_with()

        QPainter.assert_called_once_with(QPicture())
        QPainter().drawImage.assert_called_once_with(
            QRectF(),
            image,
        )
        QPainter().end()

        self.assertEqual(result, QPicture())

    def test_returns_None_if_image_is_null(self):
        image = unittest.mock.Mock(["isNull"])
        image.isNull.return_value = True

        with contextlib.ExitStack() as stack:
            QPicture = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPicture"
            ))

            QPainter = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPainter"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QRectF"
            ))

            self.assertIsNone(avatar.render_avatar_image(
                image,
                unittest.mock.sentinel.size,
            ))

        QRectF.assert_not_called()
        QPicture.assert_not_called()
        QPainter.assert_not_called()


class XMPPAvatarProvider(unittest.TestCase):
    def setUp(self):
        self.account = unittest.mock.Mock(spec=jclib.identity.Account)
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

    def test__get_image_returns_none_if_metadata_fetch_fails(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        self.avatar.get_avatar_metadata.side_effect = \
            aioxmpp.errors.XMPPError(("foo", "bar"))

        result = run_coroutine(
            self.ap._get_image(unittest.mock.sentinel.address)
        )

        self.assertIsNone(result)

    def test__get_image_uses_QImage(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()
        base.avatar1.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar1_bytes

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar2_bytes

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar3_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1,
            base.avatar2,
            base.avatar3,
        ]

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            QImage.fromData.return_value.isNull.return_value = False

            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_called_once_with()
        base.avatar2.get_image_bytes.assert_not_called()
        base.avatar3.get_image_bytes.assert_not_called()

        QImage.fromData.assert_called_once_with(
            unittest.mock.sentinel.avatar1_bytes
        )

        self.assertEqual(result, QImage.fromData())

    def test__get_image_tries_next_if_get_image_bytes_not_implemented(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = NotImplementedError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar2,
            base.avatar3,
            base.avatar1,
        ]

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            QImage.fromData.return_value.isNull.return_value = False

            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        QImage.fromData.assert_called_once_with(
            unittest.mock.sentinel.image_bytes
        )

        self.assertEqual(result, QImage.fromData())

    def test__get_image_tries_next_if_image_bytes_not_available(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = \
            aioxmpp.errors.XMPPCancelError(("foo", "bar"))

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar2,
            base.avatar3,
            base.avatar1,
        ]

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            QImage.fromData.return_value.isNull.return_value = False

            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        QImage.fromData.assert_called_once_with(
            unittest.mock.sentinel.image_bytes
        )

        self.assertEqual(result, QImage.fromData())

    def test__get_image_tries_next_if_one_fails(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = \
            RuntimeError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.image_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar2,
            base.avatar3,
            base.avatar1,
        ]

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            QImage.fromData.return_value.isNull.return_value = False

            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_not_called()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        QImage.fromData.assert_called_once_with(
            unittest.mock.sentinel.image_bytes
        )

        self.assertEqual(result, QImage.fromData())

    def test__get_image_returns_none_if_all_fail(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()
        base.avatar1.get_image_bytes.side_effect = \
            aioxmpp.errors.XMPPCancelError(("foo", "bar"))

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.side_effect = RuntimeError()

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.side_effect = RuntimeError()

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1,
            base.avatar2,
            base.avatar3,
        ]

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_called_once_with()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        QImage.fromData.assert_not_called()

        self.assertIsNone(result)

    def test__get_image_tries_next_if_QImage_fails_to_load(self):
        client = self._prep_client()

        self.ap.prepare_client(client)

        base = unittest.mock.Mock()
        base.avatar1 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar1.get_image_bytes = CoroutineMock()
        base.avatar1.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar1_bytes

        base.avatar2 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar2.get_image_bytes = CoroutineMock()
        base.avatar2.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar2_bytes

        base.avatar3 = unittest.mock.Mock(
            spec=aioxmpp.avatar.service.AbstractAvatarDescriptor)
        base.avatar3.get_image_bytes = CoroutineMock()
        base.avatar3.get_image_bytes.return_value = \
            unittest.mock.sentinel.avatar3_bytes

        self.avatar.get_avatar_metadata.return_value = [
            base.avatar1,
            base.avatar2,
            base.avatar3,
        ]

        def images():
            for i in itertools.count():
                yield getattr(base, "image{}".format(i))

        base.image0.isNull.return_value = True
        base.image1.isNull.return_value = True
        base.image2.isNull.return_value = False

        with unittest.mock.patch("jabbercat.Qt.QImage") as QImage:
            QImage.fromData.side_effect = images()

            result = run_coroutine(
                self.ap._get_image(unittest.mock.sentinel.address)
            )

        self.avatar.get_avatar_metadata.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        base.avatar1.get_image_bytes.assert_called_once_with()
        base.avatar2.get_image_bytes.assert_called_once_with()
        base.avatar3.get_image_bytes.assert_called_once_with()

        self.assertSequenceEqual(
            QImage.fromData.mock_calls,
            [
                unittest.mock.call(unittest.mock.sentinel.avatar1_bytes),
                unittest.mock.call(unittest.mock.sentinel.avatar2_bytes),
                unittest.mock.call(unittest.mock.sentinel.avatar3_bytes),
            ]
        )

        base.image0.isNull.assert_called_once_with()
        base.image1.isNull.assert_called_once_with()
        base.image2.isNull.assert_called_once_with()

        self.assertEqual(result, base.image2)

    def test_fetch_avatar_returns_None_if__get_image_returns_None(self):
        with contextlib.ExitStack() as stack:
            _get_image = stack.enter_context(unittest.mock.patch.object(
                self.ap, "_get_image",
                new=CoroutineMock()
            ))
            _get_image.return_value = None

            self.assertIsNone(
                run_coroutine(self.ap.fetch_avatar(
                    unittest.mock.sentinel.address,
                ))
            )

        _get_image.assert_called_once_with(
            unittest.mock.sentinel.address
        )

    def test_fetch_avatar_uses__get_image_and_render_avatar_image(self):
        with contextlib.ExitStack() as stack:
            _get_image = stack.enter_context(unittest.mock.patch.object(
                self.ap, "_get_image",
                new=CoroutineMock()
            ))
            _get_image.return_value = unittest.mock.sentinel.image

            render_avatar_image = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_avatar_image"
            ))

            result = run_coroutine(self.ap.fetch_avatar(
                unittest.mock.sentinel.address
            ))

        _get_image.assert_called_once_with(
            unittest.mock.sentinel.address
        )

        render_avatar_image.assert_called_once_with(
            unittest.mock.sentinel.image,
            48
        )

        self.assertEqual(result, render_avatar_image())

    def test_get_avatar_raises_KeyError_when_cold(self):
        with self.assertRaises(KeyError):
            self.ap.get_avatar(unittest.mock.sentinel.address)

    def test_get_avatar_returns_result_from_fetch_avatar(self):
        def generate_images():
            for i in itertools.count():
                yield getattr(unittest.mock.sentinel, "image{}".format(i))

        def generate_bytes():
            for i in itertools.count():
                if i == 1:
                    yield None
                yield unittest.mock.sentinel.image_bytes

        with contextlib.ExitStack() as stack:
            _get_image = stack.enter_context(unittest.mock.patch.object(
                self.ap, "_get_image",
                new=CoroutineMock()
            ))
            _get_image.side_effect = generate_bytes()

            render_avatar_image = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_avatar_image"
            ))
            render_avatar_image.side_effect = generate_images()

            pic1 = run_coroutine(self.ap.fetch_avatar(
                unittest.mock.sentinel.address1,
            ))
            self.assertIsNotNone(pic1)

            pic2 = run_coroutine(self.ap.fetch_avatar(
                unittest.mock.sentinel.address2,
            ))
            self.assertIsNone(pic2)

        self.assertEqual(
            self.ap.get_avatar(unittest.mock.sentinel.address1),
            unittest.mock.sentinel.image0,
        )

        self.assertEqual(
            self.ap.get_avatar(unittest.mock.sentinel.address2),
            None,
        )

        with self.assertRaises(KeyError):
            self.ap.get_avatar(unittest.mock.sentinel.address)


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
                "jabbercat.Qt.QPen"
            ))

            QColor = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QColor"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QRectF"
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
                "jabbercat.Qt.QFont"
            ))

            QRectF = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QRectF"
            ))

            QPen = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPen"
            ))

            QBrush = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QBrush"
            ))

            QColor = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QColor"
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
                "jabbercat.Qt.QPainter"
            ))

            QPicture = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPicture"
            ))

            first_grapheme = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.first_grapheme"
            ))

            render_dummy_avatar_base = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar_base"
            ))

            render_dummy_avatar_grapheme = stack.enter_context(
                unittest.mock.patch(
                    "jabbercat.avatar.render_dummy_avatar_grapheme"
                )
            )

            text_to_qtcolor = stack.enter_context(unittest.mock.patch(
                "jabbercat.utils.text_to_qtcolor"
            ))

            normalise_text_for_hash = stack.enter_context(unittest.mock.patch(
                "jclib.utils.normalise_text_for_hash"
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

    def test_use_colour_text_over_text_for_colouring_if_given(self):
        with contextlib.ExitStack() as stack:
            QPainter = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPainter"
            ))

            QPicture = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QPicture"
            ))

            first_grapheme = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.first_grapheme"
            ))

            render_dummy_avatar_base = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar_base"
            ))

            render_dummy_avatar_grapheme = stack.enter_context(
                unittest.mock.patch(
                    "jabbercat.avatar.render_dummy_avatar_grapheme"
                )
            )

            text_to_qtcolor = stack.enter_context(unittest.mock.patch(
                "jabbercat.utils.text_to_qtcolor"
            ))

            normalise_text_for_hash = stack.enter_context(unittest.mock.patch(
                "jclib.utils.normalise_text_for_hash"
            ))

            result = avatar.render_dummy_avatar(
                unittest.mock.sentinel.font,
                unittest.mock.sentinel.name,
                unittest.mock.sentinel.size,
                colour_text=unittest.mock.sentinel.colour_text
            )

        normalise_text_for_hash.assert_called_once_with(
            unittest.mock.sentinel.colour_text
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
                "jabbercat.avatar.render_dummy_avatar"
            ))

            result = self.ag.get_avatar(
                TEST_JID1,
                unittest.mock.sentinel.font,
            )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.font,
            unittest.mock.sentinel.name,
            48,
            str(TEST_JID1),
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
                "jabbercat.avatar.render_dummy_avatar"
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
                "jabbercat.avatar.render_dummy_avatar"
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
                "jabbercat.avatar.render_dummy_avatar"
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
        self.client = unittest.mock.Mock(spec=jclib.client.Client)
        self.writeman = unittest.mock.Mock(spec=jclib.storage.WriteManager)
        self.am = avatar.AvatarManager(self.client, self.writeman)
        self.listener = make_listener(self.am)

    def tearDown(self):
        self.am.close()

    def test_get_avatar_font_uses_general_font(self):
        with contextlib.ExitStack() as stack:
            QFontDatabase = stack.enter_context(unittest.mock.patch(
                "jabbercat.Qt.QFontDatabase",
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
        client = unittest.mock.Mock()
        account = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))

            _on_backend_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_backend_avatar_changed")
            )

            self.am._prepare_client(
                account,
                client,
            )

        RosterNameAvatarProvider.assert_called_once_with()
        RosterNameAvatarProvider().prepare_client.assert_called_once_with(
            client
        )
        RosterNameAvatarProvider().on_avatar_changed.connect\
            .assert_called_once_with(
                unittest.mock.ANY)

        _, (cb, ), _ = \
            RosterNameAvatarProvider().on_avatar_changed.connect.mock_calls[0]

        _on_backend_avatar_changed.assert_not_called()
        cb(unittest.mock.sentinel.address)
        _on_backend_avatar_changed.assert_called_once_with(
            account,
            unittest.mock.sentinel.address,
        )

    def test__prepare_client_creates_XMPPAvatarProvider_and_links_it(self):
        client = unittest.mock.Mock()
        account = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))

            _on_xmpp_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_xmpp_avatar_changed")
            )

            self.am._prepare_client(
                account,
                client,
            )

        XMPPAvatarProvider.assert_called_once_with(account)
        XMPPAvatarProvider().prepare_client.assert_called_once_with(client)
        XMPPAvatarProvider().on_avatar_changed.connect\
            .assert_called_once_with(
                unittest.mock.ANY)

        _, (cb, ), _ = \
            XMPPAvatarProvider().on_avatar_changed.connect.mock_calls[0]

        _on_xmpp_avatar_changed.assert_not_called()
        cb(unittest.mock.sentinel.address)
        _on_xmpp_avatar_changed.assert_called_once_with(
            account,
            XMPPAvatarProvider(),
            unittest.mock.sentinel.address,
        )

    def test__shutdown_client_unlinks_RosterNameAvatarProvider(self):
        client = unittest.mock.Mock()
        account = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))

            _on_backend_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_backend_avatar_changed")
            )

            self.am._prepare_client(
                account,
                client,
            )

            RosterNameAvatarProvider().on_avatar_changed.disconnect\
                .assert_not_called()

            self.am._shutdown_client(
                account,
                client,
            )

        RosterNameAvatarProvider().on_avatar_changed.disconnect\
            .assert_called_once_with(
                RosterNameAvatarProvider().on_avatar_changed.connect())

    def test__shutdown_client_unlinks_XMPPAvatarProvider(self):
        client = unittest.mock.Mock()
        account = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))

            _on_backend_avatar_changed = stack.enter_context(
                unittest.mock.patch.object(self.am,
                                           "_on_backend_avatar_changed")
            )

            self.am._prepare_client(
                account,
                client,
            )

            XMPPAvatarProvider().on_avatar_changed.disconnect\
                .assert_not_called()

            self.am._shutdown_client(
                account,
                client,
            )

        XMPPAvatarProvider().on_avatar_changed.disconnect\
            .assert_called_once_with(
                XMPPAvatarProvider().on_avatar_changed.connect())

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
                "jabbercat.avatar.render_dummy_avatar"
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
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = None

            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))
            XMPPAvatarProvider().get_avatar.return_value = None

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar"
            ))

            _fetch_in_background = stack.enter_context(
                unittest.mock.patch.object(
                    self.am,
                    "_fetch_in_background",
                )
            )

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
            )

        XMPPAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
        )
        _fetch_in_background.assert_not_called()

        RosterNameAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
            unittest.mock.sentinel.avatar_font,
        )

        render_dummy_avatar.assert_called_once_with(
            unittest.mock.sentinel.avatar_font,
            str(TEST_JID1),
            48,
        )

        self.assertEqual(result, render_dummy_avatar())

    def test_get_avatar_spawns_lookup_on_KeyError_from_xmpp_avatar_and_falls_back(self):  # NOQA
        client = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = \
                unittest.mock.sentinel.image

            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))
            XMPPAvatarProvider().get_avatar.side_effect = KeyError

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar"
            ))

            _fetch_in_background = stack.enter_context(
                unittest.mock.patch.object(
                    self.am,
                    "_fetch_in_background",
                )
            )

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
            )

        XMPPAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
        )

        _fetch_in_background.assert_called_once_with(
            unittest.mock.sentinel.account,
            XMPPAvatarProvider(),
            TEST_JID1,
        )

        RosterNameAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
            unittest.mock.sentinel.avatar_font,
        )

        self.assertEqual(result, RosterNameAvatarProvider().get_avatar())

    def test_get_avatar_returns_xmpp_avatar_if_available(self):
        client = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = \
                unittest.mock.sentinel.rn_image

            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))
            XMPPAvatarProvider().get_avatar.return_value = \
                unittest.mock.sentinel.xmpp_image

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar"
            ))

            _fetch_in_background = stack.enter_context(
                unittest.mock.patch.object(
                    self.am,
                    "_fetch_in_background",
                )
            )

            get_avatar_font = stack.enter_context(unittest.mock.patch.object(
                self.am,
                "get_avatar_font",
            ))
            get_avatar_font.return_value = unittest.mock.sentinel.avatar_font

            result = self.am.get_avatar(
                unittest.mock.sentinel.account,
                TEST_JID1,
            )

        XMPPAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
        )

        _fetch_in_background.assert_not_called()

        RosterNameAvatarProvider().get_avatar.assert_not_called()
        render_dummy_avatar.assert_not_called()

        self.assertEqual(result, XMPPAvatarProvider().get_avatar())

    def test_get_avatar_falls_passes_name_surrogate_to_render_dummy(self):
        client = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            RosterNameAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.RosterNameAvatarProvider",
            ))
            RosterNameAvatarProvider().get_avatar.return_value = None

            XMPPAvatarProvider = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.XMPPAvatarProvider",
            ))
            XMPPAvatarProvider().get_avatar.return_value = None

            self.am._prepare_client(
                unittest.mock.sentinel.account,
                client,
            )

        with contextlib.ExitStack() as stack:
            render_dummy_avatar = stack.enter_context(unittest.mock.patch(
                "jabbercat.avatar.render_dummy_avatar"
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

        XMPPAvatarProvider().get_avatar.assert_called_once_with(
            TEST_JID1,
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

        self.assertEqual(result, render_dummy_avatar())

    def test__fetch_avatar_and_emit_signal(self):
        fetch_func = CoroutineMock()
        fetch_func.return_value = unittest.mock.Mock(spec=Qt.QPicture)

    def test__fetch_in_background_makes_lookup_in_background(self):
        provider = unittest.mock.Mock(spec=avatar.XMPPAvatarProvider)
        provider.fetch_avatar = CoroutineMock()

        self.am._fetch_in_background(unittest.mock.sentinel.account,
                                     provider,
                                     unittest.mock.sentinel.address)

        run_coroutine(asyncio.sleep(0.01))

        provider.fetch_avatar.assert_called_once_with(
            unittest.mock.sentinel.address,
        )
        self.listener.on_avatar_changed.assert_called_once_with(
            unittest.mock.sentinel.account,
            unittest.mock.sentinel.address,
        )

    def test__on_xmpp_avatar_changed_causes_lookup(self):
        provider = unittest.mock.Mock(spec=avatar.XMPPAvatarProvider)
        provider.get_avatar.return_value = unittest.mock.sentinel.value

        with contextlib.ExitStack() as stack:
            _fetch_in_background = stack.enter_context(
                unittest.mock.patch.object(
                    self.am,
                    "_fetch_in_background",
                )
            )

            self.am._on_xmpp_avatar_changed(
                unittest.mock.sentinel.account,
                provider,
                unittest.mock.sentinel.address
            )

        provider.get_avatar.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        _fetch_in_background.assert_called_once_with(
            unittest.mock.sentinel.account,
            provider,
            unittest.mock.sentinel.address
        )

        self.listener.on_avatar_changed.assert_not_called()
        provider.fetch_avatar.assert_not_called()

    def test__on_xmpp_avatar_changed_does_not_cause_lookup_if_not_in_cache(
            self):
        provider = unittest.mock.Mock(spec=avatar.XMPPAvatarProvider)
        provider.get_avatar.side_effect = KeyError

        with contextlib.ExitStack() as stack:
            _fetch_in_background = stack.enter_context(
                unittest.mock.patch.object(
                    self.am,
                    "_fetch_in_background",
                )
            )

            self.am._on_xmpp_avatar_changed(
                unittest.mock.sentinel.account,
                provider,
                unittest.mock.sentinel.address
            )

        provider.get_avatar.assert_called_once_with(
            unittest.mock.sentinel.address,
        )

        self.listener.on_avatar_changed.assert_not_called()
        provider.fetch_avatar.assert_not_called()
        _fetch_in_background.assert_not_called()
