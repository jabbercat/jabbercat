import asyncio

import jclib.tasks

from . import Qt

from .ui import tasks_status_widget, tasks_popup_frame


class TasksModel(Qt.QAbstractListModel):
    ROLE_ACTIONS = Qt.Qt.UserRole + 1

    ROLE_PROGRESS_RATIO = Qt.Qt.UserRole + 1001
    ROLE_ERROR = Qt.Qt.UserRole + 1002
    ROLE_IS_DONE = Qt.Qt.UserRole + 1003

    def __init__(self, clear_action=None, cancel_action=None):
        super().__init__()
        self._tasks = []
        self._clear_action = clear_action
        self._cancel_action = cancel_action
        jclib.tasks.manager.on_task_added.connect(
            self._add_task
        )
        jclib.tasks.manager.on_task_changed.connect(
            self._task_changed
        )

    def _remove_task(self, task):
        try:
            index = self._tasks.index(task)
        except ValueError:
            return

        self.beginRemoveRows(Qt.QModelIndex(), index, index)
        del self._tasks[index]
        self.endRemoveRows()

    def _add_task(self, task):
        if task.asyncio_task.done():
            return
        task.add_done_callback(self._task_done)
        self.beginInsertRows(Qt.QModelIndex(),
                             len(self._tasks),
                             len(self._tasks))
        self._tasks.append(task)
        self.endInsertRows()

    def _task_changed(self, task):
        raw_index = self._tasks.index(task)
        index = self.index(raw_index, 0)
        self.dataChanged.emit(index, index)

    def _task_done(self, task):
        exception = task.asyncio_task.exception()

        if (exception is not None and
                not isinstance(exception, asyncio.CancelledError)):
            # task failed!, we don’t remove it yet
            self._task_changed(task)
            return

        self._task_changed(task)

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self._tasks)

    def data(self, index, role):
        if not index.isValid():
            return

        task = self._tasks[index.row()]
        if role == Qt.Qt.DisplayRole:
            return task.text
        elif role == self.ROLE_PROGRESS_RATIO:
            return task.progress_ratio
        elif role == self.ROLE_ERROR:
            exception = (task.asyncio_task.done() and
                         task.asyncio_task.exception())
            if exception:
                return exception
        elif role == self.ROLE_IS_DONE:
            return task.asyncio_task.done()
        elif role == self.ROLE_ACTIONS:
            if task.asyncio_task.done():
                if self._clear_action:
                    return [self._clear_action]
                else:
                    return []
            else:
                if self._cancel_action:
                    return [self._cancel_action]
                else:
                    return []

    def clean(self):
        self.beginResetModel()
        self._tasks = [
            task for task in self._tasks
            if not task.asyncio_task.done() or
            task.asyncio_task.exception() is not None
        ]
        self.endResetModel()


class TaskDelegate(Qt.QStyledItemDelegate):
    PADDING = 2

    def sizeHint(self, option, index):
        font = option.font
        metrics = Qt.QFontMetrics(font)

        text_height = metrics.ascent() + metrics.descent()
        text_width = metrics.width(index.data(Qt.Qt.DisplayRole))
        percent_width = metrics.width("\u2007"*3 + "%")
        min_progress_bar = 24

        return Qt.QSize(
            self.PADDING*2 + max(percent_width + min_progress_bar, text_width),
            self.PADDING*2+text_height*2
        )

    def getAction(self, index, widget=None, cursor_pos=None):
        widget = widget or self.parent()
        cursor_pos = global_pos or Qt.QCursor.pos()

    def paint(self, painter, option, index):
        painter.setRenderHint(Qt.QPainter.Antialiasing, False)
        painter.setPen(Qt.Qt.NoPen)
        style = option.widget.style() or Qt.QApplication.style()
        style.drawControl(Qt.QStyle.CE_ItemViewItem, option, painter,
                          option.widget)

        if option.state & Qt.QStyle.State_Selected:
            text_color = option.palette.highlightedText().color()
        else:
            text_color = option.palette.text().color()

        painter.setPen(text_color)
        font = option.font
        metrics = Qt.QFontMetrics(font)

        text_height = metrics.ascent() + metrics.descent()

        top_left = option.rect.topLeft() + Qt.QPoint(
            self.PADDING,
            self.PADDING,
        )

        text_rect = Qt.QRectF(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING,
                text_height,
            )
        )

        text = metrics.elidedText(
            index.data(Qt.Qt.DisplayRole),
            Qt.Qt.ElideRight,
            text_rect.width()
        )

        painter.drawText(
            text_rect,
            Qt.Qt.TextSingleLine,
            text,
        )

        top_left += Qt.QPoint(0, text_height)

        progress_rect = Qt.QRect(
            top_left,
            top_left + Qt.QPoint(
                option.rect.width() - self.PADDING*2,
                option.rect.height() - self.PADDING -
                (top_left.y() - option.rect.top())
            )
        )

        error = index.data(TasksModel.ROLE_ERROR)
        if error is not None:
            error_text = metrics.elidedText(
                "Failed: {}: {}".format(type(error).__name__,
                                        str(error)),
                Qt.Qt.ElideRight,
                progress_rect.width()
            )
            color = Qt.QColor(text_color)
            color.setAlphaF(text_color.alphaF()*0.8)
            painter.setPen(color)
            painter.drawText(
                progress_rect,
                Qt.Qt.TextSingleLine,
                error_text,
            )
        else:
            is_done = index.data(TasksModel.ROLE_IS_DONE)
            if is_done:
                progress = 1.0
            else:
                progress = index.data(TasksModel.ROLE_PROGRESS_RATIO)
            if progress is None:
                progress_text = metrics.elidedText(
                    "(progress unknown)",
                    Qt.Qt.ElideRight,
                    progress_rect.width()
                )
                color = Qt.QColor(text_color)
                color.setAlphaF(text_color.alphaF()*0.8)
                painter.setPen(color)
                painter.drawText(
                    progress_rect,
                    Qt.Qt.TextSingleLine,
                    progress_text,
                )
            else:
                pg_options = Qt.QStyleOptionProgressBar()
                pg_options.fontMetrics = metrics
                pg_options.palette = option.palette
                pg_options.rect = progress_rect
                pg_options.type = Qt.QStyleOption.SO_ProgressBar
                pg_options.state = Qt.QStyle.State_Enabled
                pg_options.minimum = 0
                pg_options.maximum = 1000
                pg_options.progress = round(progress * 1000)
                if is_done:
                    pg_options.text = "done"
                else:
                    pg_options.text = "{:>3.0f}%".format(progress * 100)
                pg_options.textVisible = True

                style.drawControl(Qt.QStyle.CE_ProgressBar, pg_options,
                                  painter)


class TasksPopup(Qt.QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = tasks_popup_frame.Ui_TasksPopup()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Qt.Popup)

        self.__model = TasksModel()
        self.__delegate = TaskDelegate()
        self.ui.tasks.setModel(self.__model)
        self.ui.tasks.setItemDelegate(self.__delegate)

    def hideEvent(self, event):
        self.__model.clean()
        super().hideEvent(event)

    @property
    def has_tasks(self):
        return self.__model.rowCount(Qt.QModelIndex()) > 0


class TaskStatusWidget(Qt.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = tasks_status_widget.Ui_TaskStatusWidget()
        self.ui.setupUi(self)

        jclib.tasks.manager.on_task_added.connect(
            self._on_task_update,
        )
        jclib.tasks.manager.on_task_changed.connect(
            self._on_task_update,
        )
        jclib.tasks.manager.on_task_done.connect(
            self._on_task_update,
        )

        self.ui.show_task_manager.clicked.connect(
            self._show_task_manager_clicked
        )

        self._popup = TasksPopup(self)

        self._update()

    def _on_task_update(self, task):
        self._update()

    def _show_task_manager_clicked(self, *args, **kwargs):
        if self._popup.isVisible():
            self._popup.hide()
            return

        pos = self.ui.show_task_manager.mapToGlobal(
            Qt.QPoint(self.ui.show_task_manager.width(), 0)
        )
        pos.setX(pos.x() - self._popup.width())
        pos -= Qt.QPoint(0, self._popup.height())

        geometry = Qt.QApplication.desktop().screenGeometry(self)
        pos -= Qt.QPoint(
            min(0, pos.x() - geometry.left()),
            min(0, pos.y() - geometry.top()),
        )

        self._popup.move(pos)
        self._popup.show()

    def _update(self):
        all_tasks = list(jclib.tasks.manager.tasks)

        tasks_with_progress = [
            task for task in all_tasks
            if task.progress_ratio is not None
        ]

        progress_bar = self.ui.progress_bar
        button = self.ui.show_task_manager

        if tasks_with_progress:
            progress = sum(
                task.progress_ratio
                for task in tasks_with_progress
            ) / len(tasks_with_progress)

            progress_bar.show()
            progress_bar.setRange(0, 1000)
            progress_bar.setValue(round(progress * 1000))
        elif all_tasks:
            progress_bar.show()
            progress_bar.setRange(0, 0)
        else:
            progress_bar.hide()

        button.setEnabled(self._popup.has_tasks)
