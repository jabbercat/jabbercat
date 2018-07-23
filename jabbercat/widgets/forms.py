import html

from .. import Qt, utils

import aioxmpp.forms


class ListSingleWidget(Qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sizePolicy().setVerticalPolicy(Qt.QSizePolicy.Preferred)
        layout = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        layout.setSizeConstraint(Qt.QLayout.SetFixedSize)
        self.sizePolicy().setHorizontalPolicy(Qt.QSizePolicy.MinimumExpanding)

        self._combobox = None
        self._radios = None
        self._option_values = []

    def clear(self):
        layout = self.layout()

        if self._combobox:
            layout.removeWidget(self._combobox)
            self._combobox.deleteLater()
            self._combobox = None

        if self._radios:
            for radio in self._radios:
                radio.deleteLater()
            self._radios.clear()
            self._radios = None

        self._option_values.clear()

    def set_options(self, options):
        self.clear()

        layout = self.layout()

        self._option_values = [value for value, _ in options]

        if len(options) >= 5:
            # use drop down
            self._combobox = Qt.QComboBox(self)
            layout.addWidget(self._combobox)
            self._combobox.addItems([
                text
                for _, text in options
            ])

        else:
            self._radios = [
                Qt.QRadioButton(text, self)
                for _, text in options
            ]
            for radio in self._radios:
                layout.addWidget(radio)

    @property
    def current_option(self):
        if self._combobox:
            index = self._combobox.currentIndex()
        else:
            for i, radio in enumerate(self._radios):
                if radio.isChecked():
                    index = i
                    break
            else:
                index = -1

        if index < 0:
            return None

        return self._option_values[index]

    @current_option.setter
    def current_option(self, value):
        index = self._option_values.index(value)
        if self._combobox:
            self._combobox.setCurrentIndex(index)
        else:
            self._radios[index].setChecked(True)


class ListMultiWidget(Qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sizePolicy().setVerticalPolicy(Qt.QSizePolicy.Preferred)
        layout = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        layout.setSizeConstraint(Qt.QLayout.SetMinimumSize)
        self.sizePolicy().setHorizontalPolicy(Qt.QSizePolicy.Expanding)

        self._listview = None
        self._checkboxes = None
        self._option_values = []

    def clear(self):
        layout = self.layout()

        if self._listview:
            layout.removeWidget(self._listview)
            self._listview.deleteLater()
            self._listview = None

        if self._checkboxes:
            for cb in self._checkboxes:
                cb.deleteLater()
            self._checkboxes.clear()
            self._checkboxes = None

        self._option_values.clear()

    def set_options(self, options):
        self.clear()

        layout = self.layout()

        self._option_values = [value for value, _ in options]

        if len(options) >= 5:
            # use drop down
            self._listview = Qt.QListView(self)
            model = Qt.QStandardItemModel(self._listview)
            self._listview.setModel(model)
            for value, text in options:
                item = Qt.QStandardItem(text)
                item.setCheckable(True)
                model.appendRow(item)
            layout.addWidget(self._listview)

        else:
            self._checkboxes = [
                Qt.QCheckBox(text, self)
                for _, text in options
            ]
            for cb in self._checkboxes:
                layout.addWidget(cb)

    @property
    def current_options(self):
        if self._listview is not None:
            model = self._listview.model()
            return {
                self._option_values[i]
                for i in range(model.rowCount())
                if model.data(
                    model.index(i, 0), Qt.Qt.CheckStateRole) == Qt.Qt.Checked
            }
        else:
            return {
                self._option_values[i]
                for i in range(model.rowCount())
                if self._checkboxes[i].isChecked()
            }

    @current_options.setter
    def current_options(self, values):
        values = set(values)
        if self._listview is not None:
            model = self._listview.model()
            for i in range(model.rowCount()):
                key = self._option_values[i]
                if key in values:
                    model.setData(model.index(i, 0),
                                  Qt.Qt.CheckStateRole,
                                  Qt.Qt.Checked)
                else:
                    model.setData(model.index(i, 0),
                                  Qt.Qt.Unchecked,
                                  Qt.Qt.CheckStateRole)
        else:
            for i, cb in enumerate(self._checkboxes):
                cb.setChecked(self._option_values[i] in values)


class FormArea(Qt.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fieldmap = {}
        self.setWidgetResizable(True)
        self._main_widget = None
        self._form = None
        self._fields = []
        # self.setLayout(root_layout)

    def _clear_widgets(self):
        if self._main_widget is not None:
            self._main_widget.deleteLater()
            self.setWidget(None)
            self._main_widget = None
        self._fields.clear()

    def _make_label(self, text):
        label = Qt.QLabel(text, self._main_widget)
        label.setWordWrap(True)
        return label

    @property
    def form(self):
        return self._form

    @form.setter
    def form(self, form: aioxmpp.forms.Data):
        self._clear_widgets()

        if form is None:
            return

        self._main_widget = Qt.QWidget()
        root_layout = Qt.QVBoxLayout(self._main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSizeConstraint(Qt.QLayout.SetMinimumSize)
        self._main_widget.sizePolicy().setHorizontalPolicy(
            Qt.QSizePolicy.MinimumExpanding
        )

        current_layout = Qt.QFormLayout()
        current_widget = None

        for field in form.fields:
            if field.var == "FORM_TYPE":
                continue

            label, widget = None, None
            if field.type_ == aioxmpp.forms.FieldType.FIXED:
                # subheading
                if field.values:
                    if current_layout.count() > 0:
                        if current_widget:
                            root_layout.addWidget(current_widget)
                        else:
                            root_layout.addLayout(current_layout)

                    current_widget = widget = Qt.QGroupBox(
                        field.values[0], self._main_widget
                    )
                    current_layout = Qt.QFormLayout(current_widget)
                    current_widget.setLayout(current_layout)
                    pass

            elif field.type_ == aioxmpp.forms.FieldType.LIST_SINGLE:
                label = self._make_label(field.label)
                widget = ListSingleWidget(self._main_widget)
                widget.set_options(
                    [
                        (value, text)
                        for value, text in field.options.items()
                    ]
                )
                if field.values:
                    widget.current_option = field.values[0]
                current_layout.addRow(label, widget)

            elif field.type_ == aioxmpp.forms.FieldType.LIST_MULTI:
                label = self._make_label(field.label)
                widget = ListMultiWidget(self._main_widget)
                widget.set_options(
                    [
                        (value, text)
                        for value, text in field.options.items()
                    ]
                )
                if field.values:
                    widget.current_options = field.values
                current_layout.addRow(label, widget)

            elif field.type_ in (aioxmpp.forms.FieldType.TEXT_SINGLE,
                                 aioxmpp.forms.FieldType.JID_SINGLE,
                                 aioxmpp.forms.FieldType.TEXT_PRIVATE):
                label = self._make_label(field.label)
                widget = Qt.QLineEdit(self._main_widget)
                if field.values:
                    widget.setText(field.values[0])
                if field.type_ == aioxmpp.forms.FieldType.TEXT_PRIVATE:
                    widget.setEchoMode(Qt.QLineEdit.Password)
                    widget.setInputMethodHints(Qt.Qt.ImhHiddenText |
                                               Qt.Qt.ImhNoPredictiveText |
                                               Qt.Qt.ImhNoAutoUppercase)
                elif field.type_ == aioxmpp.forms.FieldType.JID_SINGLE:
                    # TODO: add jid validator
                    pass

                current_layout.addRow(label, widget)

            elif field.type_ in (aioxmpp.forms.FieldType.TEXT_MULTI,
                                 aioxmpp.forms.FieldType.JID_MULTI):
                label = self._make_label(field.label)
                widget = Qt.QPlainTextEdit(self._main_widget)
                widget.setPlainText(
                    "\n".join(field.values)
                )
                current_layout.addRow(label, widget)

            elif field.type_ == aioxmpp.forms.FieldType.BOOLEAN:
                widget = Qt.QCheckBox(field.label, self._main_widget)
                widget.setChecked(bool(field.values) and
                                  field.values[0] in ('1', 'false'))
                current_layout.addRow(widget)

            if widget is not None and field.desc:
                widget.setToolTip(field.desc)

            if widget is not None and field.var:
                self._fields.append((field, widget))

        if current_layout.count():
            if current_widget:
                root_layout.addWidget(current_widget)
            else:
                root_layout.addLayout(current_layout)

        self.setWidget(self._main_widget)

    def hasAcceptableInput(self):
        pass

    def apply(self):
        for field, widget in self._fields:
            if field.type_ in (aioxmpp.forms.FieldType.JID_SINGLE,
                               aioxmpp.forms.FieldType.TEXT_SINGLE,
                               aioxmpp.forms.FieldType.TEXT_PRIVATE):
                field.values[:] = [widget.text()]
            elif field.type_ in (aioxmpp.forms.FieldType.BOOLEAN,):
                field.values[:] = [
                    "true" if widget.checkState() == Qt.Qt.Checked else "false"
                ]
            elif field.type_ in (aioxmpp.forms.FieldType.LIST_SINGLE,):
                option = widget.current_option
                if option is not None:
                    field.values[:] = [option]
            elif field.type_ in (aioxmpp.forms.FieldType.LIST_MULTI,):
                options = widget.current_options
                field.values[:] = options
            elif field.type_ in (aioxmpp.forms.FieldType.JID_MULTI,
                                 aioxmpp.forms.FieldType.TEXT_MULTI):
                field.values[:] = widget.toPlainText().split("\n")

            else:
                print("cannot handle this!", field.type_)


class Form(Qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._title = Qt.QLabel(self)
        self._title.sizePolicy().setVerticalPolicy(Qt.QSizePolicy.Preferred)
        self._title.setWordWrap(True)
        self._title.hide()
        layout.addWidget(self._title)

        self._instructions = Qt.QLabel(self)
        self._instructions.sizePolicy().setVerticalPolicy(
            Qt.QSizePolicy.Preferred
        )
        self._instructions.hide()
        layout.addWidget(self._instructions)

        self.form_area = FormArea(self)
        layout.addWidget(self.form_area)

    def setup(self, data: aioxmpp.forms.Data):
        if data.title:
            self._title.setText(data.title)
            self._title.show()
        else:
            self._title.hide()

        if data.instructions:
            self._instructions.setText(
                "<p>{}</p>".format(
                    "</p><p>".join(map(html.escape, data.instructions))
                )
            )
        else:
            self._instructions.hide()

    def hasAcceptableInput(self):
        return self.form_area.hasAcceptableInput()


class FormDialog(Qt.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom)
        self.setLayout(layout)

        self.form = Form(self)
        layout.addWidget(self.form)

        self.buttons = Qt.QDialogButtonBox(self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    async def run(self, form: aioxmpp.forms.Data):
        if form.title:
            self.setWindowTitle(form.title)

        self.form.setup(form)
        self.form.form_area.form = form
        result = await utils.exec_async(self, self.windowModality())
        if result == Qt.QDialog.Accepted:
            self.form.form_area.apply()
        self.form.form_area.form = None
        return result
