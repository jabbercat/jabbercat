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

.PHONY: lupdate
