import PyQt5.Qt as Qt


class PlaceholderTreeView(Qt.QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__placeholder_text = ""

    @property
    def placeholder_text(self):
        return self.__placeholder_text

    @placeholder_text.setter
    def placeholder_text(self, value):
        self.__placeholder_text = value
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.placeholder_text:
            return

        model = self.model()
        if model is not None and model.rowCount(self.rootIndex()) > 0:
            return

        p = Qt.QPainter(self.viewport())
        p.drawText(self.rect(), Qt.Qt.AlignCenter, self.placeholder_text)
