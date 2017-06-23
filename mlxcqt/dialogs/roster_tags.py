import asyncio

from ..ui import roster_tags

from .. import Qt


class RosterTagsPopup(Qt.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = roster_tags.Ui_RosterTagsPopup()
        self.ui.setupUi(self)
        self.ui.buttons.accepted.connect(
            self._accept,
        )
        self.ui.buttons.rejected.connect(
            self._reject,
        )

    def _accept(self):
        self._conclude(True)
        self.close()

    def _reject(self):
        self._conclude(False)
        self.close()

    @asyncio.coroutine
    def run(self, pos, all_groups, roster_items):
        assert not hasattr(self, "_future")
        self._future = asyncio.Future()
        try:
            self.ui.tags.setup(
                all_groups,
                [item.groups for item in roster_items],
            )
            self.setWindowFlags(Qt.Qt.Popup)
            self.move(pos)
            self.show()
            if not (yield from self._future):
                return None
            return self.ui.tags.get_diff()
        finally:
            try:
                del self.all_groups
                del self.model
                del self.proxied_model
            except AttributeError:
                pass
            del self._future

    def _conclude(self, code):
        if self._future.done():
            return
        self._future.set_result(code)

    def keyPressEvent(self, event):
        if event.key() == Qt.Qt.Key_Escape:
            self._conclude(False)
        return super().keyPressEvent(event)

    def closeEvent(self, event):
        self._conclude(True)
        return super().closeEvent(event)
