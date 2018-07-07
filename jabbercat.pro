lupdate_only {
    SOURCES += jabbercat/client.py
    SOURCES += jabbercat/conversation.py
    SOURCES += jabbercat/main.py
    SOURCES += jabbercat/model_adaptor.py
    SOURCES += jabbercat/models.py
    SOURCES += jabbercat/utils.py
}

FORMS += data/dlg_account_manager.ui \
         data/roster.ui \
         data/dlg_check_certificate.ui

TRANSLATIONS += qttranslations/jabbercat_de.ts
