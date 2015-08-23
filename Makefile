BUILDUI=./utils/buildui.py -5

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,mlxcqt/ui/%.py,$(UIC_SOURCE_FILES))

TS_FILES=$(wildcard translations/*.ts)

all: $(UIC_PYTHON_FILES)

clean:
	rm -rf $(UIC_PYTHON_FILES)

lupdate:
	pylupdate5 -verbose mlxc-qt.pro

lrelease: $(TS_FILES)
	lrelease-qt5 mlxc-qt.pro

$(UIC_PYTHON_FILES): mlxcqt/ui/%.py: data/%.ui
	$(BUILDUI) $< $@


.PHONY: lupdate
