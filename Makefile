BUILDUI=./utils/buildui.py -5

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,jabbercat/ui/%.py,$(UIC_SOURCE_FILES))

RESOURCE_SOURCES=$(addprefix data/,$(shell xpath -e 'RCC/qresource/file/text()' data/resources.qrc 2>/dev/null))

TS_FILES=$(wildcard translations/*.ts)

all: $(UIC_PYTHON_FILES) resources.rcc

clean:
	rm -rf $(UIC_PYTHON_FILES)

lupdate:
	pylupdate5 -verbose mlxc-qt.pro

lrelease: $(TS_FILES)
	lrelease-qt5 mlxc-qt.pro

$(UIC_PYTHON_FILES): jabbercat/ui/%.py: data/%.ui
	$(BUILDUI) $< $@

resources.rcc: data/resources.qrc $(RESOURCE_SOURCES)
	cd data; rcc --binary -o ../$@ resources.qrc

docs-html:
	cd docs; make html

run-debug: logfile_name=jabbercat-$(shell date '+%Y-%m-%dT%H-%M-%S').log
run-debug: all
	@echo
	@echo "=== logs will also be in $(logfile_name) ==="
	@echo "open http://localhost:1234 in a Chromium-like browser to debug message view issues"
	@echo
	python3 -m jabbercat --version | tee $(logfile_name)
	QTWEBENGINE_REMOTE_DEBUGGING=1234 python3 -m jabbercat 2>&1 | tee -a $(logfile_name) || true
	@echo
	@echo "=== logs have been written to $(logfile_name) ==="
	@echo

.PHONY: lupdate docs-html run-debug
