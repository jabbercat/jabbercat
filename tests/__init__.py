import sys

from jabbercat import Qt


def setup_package():
    global app
    app = Qt.QApplication(sys.argv[:1])


def teardown_package():
    app = None
