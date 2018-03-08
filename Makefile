BUILDUI=./utils/buildui.py -5

UIC_SOURCE_FILES=$(wildcard data/*.ui)
UIC_PYTHON_FILES=$(patsubst data/%.ui,jabbercat/ui/%.py,$(UIC_SOURCE_FILES))

RESOURCE_SOURCES=$(addprefix data/,$(shell xpath -e 'RCC/qresource/file/text()' data/resources.qrc 2>/dev/null))

TS_FILES=$(wildcard translations/*.ts)

TESTS?=tests/

all: $(UIC_PYTHON_FILES) resources.rcc data/js/emoji.json

clean:
	rm -rf $(UIC_PYTHON_FILES)

lupdate:
	pylupdate5 -verbose mlxc-qt.pro

lrelease: $(TS_FILES)
	lrelease-qt5 mlxc-qt.pro

$(UIC_PYTHON_FILES): jabbercat/ui/%.py: data/%.ui
	$(BUILDUI) $< $@

resources.rcc: data/resources.qrc $(RESOURCE_SOURCES)
	cd data; qtchooser -run-tool=rcc -qt=5 --binary -o ../$@ resources.qrc

docs-html:
	cd docs; make html

debug-logs:
	mkdir -p debug-logs

data/emoji-java:
	test ! -d "$@" && git clone --depth 1 https://github.com/vdurmont/emoji-java "$@" || test -d "$@"
	cd "$@"; git pull

data/emoji-java/src/main/resources/emojis.json: data/emoji-java

data/gemoji:
	test ! -d "$@" && git clone --depth 1 https://github.com/github/gemoji "$@" || test -d "$@"
	cd "$@"; git pull

data/gemoji/db/emoji.json: data/gemoji

data/js/emoji.json: data/emoji-java/src/main/resources/emojis.json data/gemoji/db/emoji.json
	PYTHONPATH=. python3 utils/build-emojidb.py --emoji-java data/emoji-java/src/main/resources/emojis.json --gemoji data/gemoji/db/emoji.json "$@"

run-debug: logfile_name=debug-logs/jabbercat-$(shell date '+%Y-%m-%dT%H-%M-%S').log
run-debug: all debug-logs
	@echo
	@echo "=== logs will also be in $(logfile_name) ==="
	@echo "open http://localhost:1234 in a Chromium-like browser to debug message view issues"
	@echo
	python3 -m jabbercat --version | tee $(logfile_name)
	PYTHONUNBUFFERED=x QTWEBENGINE_REMOTE_DEBUGGING=1234 python3 -m jabbercat 2>&1 | tee -a $(logfile_name) || true
	@echo
	@echo "=== logs have been written to $(logfile_name) ==="
	@echo

test: all
	QTWEBENGINE_REMOTE_DEBUGGING=1234 LANG=C.UTF-8 LANGUAGE=C.UTF-8 LC_DATE=C.UTF-8 LC_TIME=C.UTF-8 TZ=Etc/UTC nosetests3 $(TESTS)


.PHONY: lupdate docs-html run-debug debug-logs data/emoji-java data/gemoji
