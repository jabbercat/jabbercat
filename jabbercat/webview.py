import logging

from . import Qt

logger = logging.getLogger(__name__)
js_logger = logger.getChild("js")


class CustomWebPage(Qt.QWebEnginePage):
    def acceptNavigationRequest(self, url, type_, isMainFrame):
        print(url, type_, isMainFrame)
        return True

    def javaScriptConsoleMessage(self, level, message, lineno, sourceID):
        log_level = {
            Qt.QWebEngineView.InfoMessageLevel: logging.INFO,
            Qt.QWebEngineView.WarningMessageLevel: logging.WARNING,
            Qt.QWebEngineView.ErrorMessageLevel: logging.ERROR,
        }[level]
        js_logger.log(log_level, message)


class CustomWebView(Qt.QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.page = CustomWebPage()
        self.setPage(self.page)
