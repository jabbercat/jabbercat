import math

from .. import Qt


def easing_func(t):
    # return (math.cos(t * math.pi + math.pi) + 1) / 2
    return ((math.cos(t * math.pi + math.pi) + 1) / 2) * 0.8 + t * 0.2
    # return t


class ProgressIndicator(Qt.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._internal_value = 0
        self._p1 = 0
        self._animation = Qt.QPropertyAnimation(
            self,
            "internalValue".encode("utf-8"),
        )
        self._animation.setStartValue(0)
        self._animation.setEndValue(1)
        self._animation.setDuration(3000)
        self._animation.setLoopCount(-1)

        self._min = 0
        self._max = 0
        self._value = 0

    @Qt.pyqtProperty(float)
    def internalValue(self):
        return self._internal_value

    @internalValue.setter
    def internalValue(self, value: float):
        STEPS = 180
        STEPS_TO_ARC_MAX = 32

        self._internal_value = value
        new_p1 = int(
            ((easing_func(self._internal_value % 1) * 2) % 1) * STEPS
        ) * STEPS_TO_ARC_MAX
        if new_p1 != self._p1:
            self._p1 = new_p1
            self.update()

    @Qt.pyqtProperty(bool)
    def isIndeterminate(self):
        return self._max <= self._min

    def event(self, event: Qt.QEvent):
        if event.type() == Qt.QEvent.WindowActivate:
            if self._animation.state() == Qt.QAbstractAnimation.Paused:
                self._animation.resume()
        elif event.type() == Qt.QEvent.WindowDeactivate:
            if self._animation.state() == Qt.QAbstractAnimation.Running:
                self._animation.pause()
        return super().event(event)

    def sizeHint(self):
        return Qt.QSize(16, 16)

    def minimumSizeHint(self):
        return Qt.QSize(8, 8)

    def paintEvent(self, event: Qt.QPaintEvent):
        ARC_MAX = 5760

        painter = Qt.QPainter(self)
        painter.setRenderHint(Qt.QPainter.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h)
        x0 = w / 2 - size / 2
        y0 = h / 2 - size / 2

        outer_rect = Qt.QRectF(x0, y0, w, h)
        pen_width = max(outer_rect.width() / 8, 1)

        margins = Qt.QMarginsF(pen_width/2,
                               pen_width/2,
                               pen_width/2,
                               pen_width/2)

        ring_rect = outer_rect.marginsRemoved(margins)

        painter.setPen(Qt.QPen(
            self.palette().highlight(),
            pen_width,
            Qt.Qt.SolidLine,
            Qt.Qt.FlatCap,
        ))

        if self.isIndeterminate:
            v = self._internal_value % 1

            p1_a = self._p1
            p1 = p1_a / ARC_MAX
            p2 = (easing_func((v - 0.15) % 1) * 2) % 1

            painter.drawArc(
                ring_rect,
                p1_a,
                -((p1 - p2) % 1) * ARC_MAX,
            )
        else:
            inner_rect = ring_rect.marginsRemoved(margins)

            v = (self._value - self._min) / (self._max - self._min)
            v = max(min(v, 1), 0)
            painter.drawArc(
                ring_rect,
                ARC_MAX / 4,
                -v * ARC_MAX,
            )

            font_size = int(inner_rect.height() * 0.45)
            if font_size < 10:
                return

            font = Qt.QFont(self.font())
            font.setPixelSize(font_size)

            text = "{:.0f}%".format(v*100)
            if v < 1:
                painter.setPen(
                    Qt.QPen(self.palette().color(Qt.QPalette.WindowText))
                )
                painter.setFont(font)
                painter.drawText(inner_rect,
                                 Qt.Qt.AlignHCenter | Qt.Qt.AlignVCenter,
                                 text)

    def setRange(self, min: int, max: int):
        self._min = min
        self._max = max
        if min >= max:
            self._animation.start()
        else:
            self._animation.stop()

    def setValue(self, value: int):
        self._value = value
        self.update()
