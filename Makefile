BUILDUI=./utils/buildui.py -5

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,mlxcqt/ui/%.py,$(UIC_SOURCE_FILES))

all: $(UIC_PYTHON_FILES)

clean:
	rm -rf $(UIC_PYTHON_FILES)

$(UIC_PYTHON_FILES): mlxcqt/ui/%.py: data/%.ui
	$(BUILDUI) $< $@
