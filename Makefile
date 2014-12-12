BUILDUI=./utils/buildui.py

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,mlxc/ui/%.py,$(UIC_SOURCE_FILES))

all: $(UIC_PYTHON_FILES)

clean:
	rm -rf $(UIC_PYTHON_FILES)

$(UIC_PYTHON_FILES): mlxc/ui/%.py: data/%.ui mlxc/ui
	$(BUILDUI) $< $@

mlxc/ui:
	mkdir -p mlxc/ui
	touch mlxc/ui/__init__.py
