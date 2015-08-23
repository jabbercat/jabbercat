lupdate_only {
    SOURCES += mlxc-qt.py
    SOURCES += mlxcqt/client.py
    SOURCES += mlxcqt/main.py
    SOURCES += mlxcqt/model_adaptor.py
    SOURCES += mlxcqt/utils.py
}

FORMS += data/dlg_account_manager.ui \
         data/roster.ui \
         data/dlg_check_certificate.ui

TRANSLATIONS += qttranslations/mlxcqt_de.ts
