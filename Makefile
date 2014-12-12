BUILDUI=./utils/buildui.py

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,mlxc/qt/ui/%.py,$(UIC_SOURCE_FILES))

all: $(UIC_PYTHON_FILES)

clean:
	rm -rf $(UIC_PYTHON_FILES)

$(UIC_PYTHON_FILES): mlxc/qt/ui/%.py: data/%.ui
	$(BUILDUI) $< $@
