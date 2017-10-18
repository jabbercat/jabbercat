import asyncio
import code
import contextlib
import math
import pprint
import sys

import aioxmpp

import jclib

import jabbercat

from ..ui import dlg_python_console

from .. import Qt


@contextlib.contextmanager
def enable_pprint(width):
    prev = sys.displayhook

    def pprint_displayhook(v):
        if v is None:
            return
        pprint.pprint(v, width=width)

    sys.displayhook = pprint_displayhook

    yield
    sys.displayhook = prev


class TextDocumentFile:
    def __init__(self, document,
                 text_view=None,
                 character_style=None):
        super().__init__()
        self._document = document
        self._text_view = text_view
        self._character_style = character_style

    def write(self, data):
        cursor = Qt.QTextCursor(self._document)
        cursor.movePosition(Qt.QTextCursor.End)
        if self._character_style is not None:
            cursor.insertText(data, self._character_style)
        else:
            cursor.insertText(data)

    def flush(self):
        if self._text_view is not None:
            self._text_view.textCursor().movePosition(Qt.QTextCursor.End)
            self._text_view.ensureCursorVisible()


class PythonConsole(Qt.QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.ui = dlg_python_console.Ui_PythonConsole()
        self.ui.setupUi(self)

        self.ui.action_execute.triggered.connect(self._execute_triggered)
        self.ui.input_box.installEventFilter(self)

        self._history = [""]
        self._history_index = 0

        self._globals = {}
        self._locals = {}

        stdout_format = Qt.QTextCharFormat()
        self._stdout_file = TextDocumentFile(
            self.ui.output_box.document(),
            self.ui.output_box,
            stdout_format,
        )

        stderr_format = Qt.QTextCharFormat()
        stderr_format.setForeground(Qt.QColor(191, 63, 63))
        self._stderr_file = TextDocumentFile(
            self.ui.output_box.document(),
            self.ui.output_box,
            stderr_format,
        )

        stdin_format = Qt.QTextCharFormat()
        stdin_format.setForeground(Qt.QColor(63, 63, 191))
        self._stdin_file = TextDocumentFile(
            self.ui.output_box.document(),
            self.ui.output_box,
            stdin_format,
        )

        self._execute_single("import this")
        self._execute_single("import asyncio, aioxmpp, jclib, jabbercat")
        self._stdin_file.write(">>> main = {!r}\n".format(main))
        self._globals["main"] = main

        self.addAction(self.ui.action_execute)
        self.addAction(self.ui.action_cancel)

    def _restore_from_history(self, new_index: int):
        if new_index == self._history_index:
            return
        if not (0 <= new_index < len(self._history)):
            return
        if self._history_index == len(self._history) - 1:
            self._history[self._history_index] = self.ui.input_box.toPlainText()

        self._history_index = new_index
        self.ui.input_box.setPlainText(self._history[self._history_index])

    def eventFilter(self, obj: Qt.QObject, event: Qt.QEvent):
        if obj is not self.ui.input_box:
            return super().eventFilter(obj, event)
        if event.type() != Qt.QEvent.KeyPress:
            return super().eventFilter(obj, event)

        if (event.key() == Qt.Qt.Key_Up and
                event.modifiers() & Qt.Qt.ControlModifier == Qt.Qt.ControlModifier):
            self._restore_from_history(self._history_index - 1)
            return True

        if (event.key() == Qt.Qt.Key_Down and
                event.modifiers() & Qt.Qt.ControlModifier == Qt.Qt.ControlModifier):
            self._restore_from_history(self._history_index + 1)
            return True

        if ((event.key() == Qt.Qt.Key_Enter or event.key() == Qt.Qt.Key_Return)
                and event.modifiers() & Qt.Qt.ShiftModifier != Qt.Qt.ShiftModifier):
            try:
                result = code.compile_command(
                    self.ui.input_box.toPlainText(),
                    "<python console>", "single"
                )
            except SyntaxError:
                result = True
            print(result)
            if result:
                # force execution
                self._execute_triggered()
                return True

        return super().eventFilter(obj, event)

    def _execute_single(self, statement):
        prefix = ">>> "
        for line in statement.split("\n"):
            self._stdin_file.write(prefix)
            self._stdin_file.write(line)
            self._stdin_file.write("\n")
            prefix = "... "

        metrics = Qt.QFontMetrics(self.ui.output_box.font())
        nchars = math.floor(
            self.ui.output_box.width() * 0.9 / metrics.width("m")
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(self._stdout_file))
            stack.enter_context(contextlib.redirect_stderr(self._stderr_file))
            stack.enter_context(enable_pprint(nchars))
            try:
                code = compile(statement, "<python console>", "single")
                exec(code, self._locals, self._globals)
            except:  # NOQA
                import traceback
                traceback.print_exc()
        self._stdin_file.flush()

    def _execute(self, statements):
        for statement in statements.split("\n\n"):
            statement = statement.strip("\n")
            if "\n" in statement:
                statement += "\n\n"
            self._execute_single(statement)

    def _execute_triggered(self):
        code = self.ui.input_box.toPlainText().strip()
        self._history_index = len(self._history)
        self._history.insert(len(self._history) - 1, code)
        self.ui.input_box.clear()
        self._execute(code)

    def _cancel_triggered(self):
        pass
