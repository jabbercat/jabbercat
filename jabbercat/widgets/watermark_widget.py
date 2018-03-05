import asyncio

from .. import Qt


def aspect_scale(canvas_w, canvas_h,
                 img_w, img_h):
    canvas_aspect = canvas_w / canvas_h
    img_aspect = img_w / img_h
    if canvas_aspect < img_aspect:
        out_w = canvas_w
        out_h = out_w / img_aspect
    else:
        out_h = canvas_h
        out_w = img_aspect * out_h
    return out_w, out_h


class WatermarkWidget(Qt.QWidget):
    MIN_SIZE = 64
    PADDING = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watermark = None
        self._delayed_update_handle = None
        self._update_pending = True

    @property
    def watermark(self) -> Qt.QImage:
        return self._watermark

    @watermark.setter
    def watermark(self, img: Qt.QImage):
        self._watermark = img.convertToFormat(
            Qt.QImage.Format_Alpha8
        )
        self._update()

    def _dpr(self):
        if self.window().windowHandle() is not None:
            return self.window().windowHandle().devicePixelRatio()
        return 1

    def _scaled_size(self):
        dpr = self._dpr()
        size = self.size()
        size *= dpr
        return size, dpr

    def _calc_size(self):
        size, dpr = self._scaled_size()
        width = max(self.MIN_SIZE, size.width() - self.PADDING * 2)
        height = max(self.MIN_SIZE, size.height() - self.PADDING * 2)
        return width, height, dpr

    def event(self, event: Qt.QEvent):
        if event.type() in (Qt.QEvent.Resize,
                            Qt.QEvent.PaletteChange,
                            Qt.QEvent.StyleChange):
            self._delayed_update()
        return super().event(event)

    def _delayed_update(self):
        loop = asyncio.get_event_loop()
        if self._delayed_update_handle is not None:
            self._delayed_update_handle.cancel()
        self._update_pending = True
        self._delayed_update_handle = loop.call_later(
            0.05,  # 50 ms
            self._execute_delayed_update
        )

    def _execute_delayed_update(self):
        if not self._update_pending:
            return
        if self._delayed_update_handle is not None:
            self._delayed_update_handle.cancel()
        self._delayed_update_handle = None
        self._update()

    def _tint(self, image: Qt.QImage, color: Qt.QColor) -> Qt.QImage:
        image.save("/tmp/template.png")
        result = image.convertToFormat(Qt.QImage.Format_ARGB32_Premultiplied)
        result.save("/tmp/converted.png")
        painter = Qt.QPainter(result)
        painter.setCompositionMode(Qt.QPainter.CompositionMode_SourceIn)
        painter.fillRect(0, 0, result.width(), result.height(), color)
        painter.end()
        result.save("/tmp/tinted.png")
        return result

    def _update(self):
        self._update_pending = False
        if self._delayed_update_handle is not None:
            self._delayed_update_handle.cancel()
        if self._watermark is None:
            self._pixmap = Qt.QPixmap()
            return

        w, h, dpr = self._calc_size()
        # hidpi_scale = self.window().windowHandle().devicePixelRatio()
        # w = round(w*hidpi_scale)
        # h = round(h*hidpi_scale)
        tinted = self._tint(
            self._watermark,
            self.palette().color(Qt.QPalette.Light)
        )

        img_w, img_h = tinted.width(), tinted.height()

        out_w, out_h = aspect_scale(w, h, img_w, img_h)
        out_x = round((w - out_w) / 2)
        out_y = round((h - out_h) / 2)

        framebuffer = Qt.QImage(
            Qt.QSize(out_w, out_h),
            Qt.QImage.Format_ARGB32_Premultiplied
        )
        framebuffer.fill(self.palette().color(Qt.QPalette.Window))
        framebuffer_painter = Qt.QPainter(framebuffer)
        framebuffer_painter.drawImage(Qt.QRect(0, 0, out_w, out_h),
                                      tinted)
        framebuffer_painter.end()

        self._pixmap = Qt.QPixmap.fromImage(framebuffer)
        self._pixmap.setDevicePixelRatio(dpr)

        self.update()

    def paintEvent(self, event: Qt.QPaintEvent):
        if self._pixmap is None:
            self._update()

        painter = Qt.QPainter(self)
        pix_w = self._pixmap.width()
        pix_h = self._pixmap.height()
        size = self.size()
        dpr = self._dpr()
        pix_w = pix_w / dpr
        pix_h = pix_h / dpr

        inner_width = max(size.width() - self.PADDING * 2, 0)
        inner_height = max(size.height() - self.PADDING * 2, 0)

        out_w, out_h = aspect_scale(inner_width, inner_height,
                                    pix_w, pix_h)

        inner_rect = Qt.QRectF(
            self.PADDING + (inner_width - out_w) / 2,
            self.PADDING + (inner_height - out_h) / 2,
            out_w,
            out_h,
        )

        painter.drawPixmap(
            inner_rect,
            self._pixmap,
            Qt.QRectF(0, 0, self._pixmap.width(), self._pixmap.height())
        )
