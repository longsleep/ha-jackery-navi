# Packages the integration for copying into Home Assistant.
#
#   make            dist/jackery_navi-<version>-<offset>.tar.gz   (commits since the last tag)
#                   dist/jackery_navi-<version>-g<short ref>.tar.gz  (when there is no tag)
#   make version    print the build id
#   make clean
#
# The archive holds custom_components/jackery_navi/, owned by 0:0, so it unpacks in place with
#   tar -xzf jackery_navi-….tar.gz -C /config

COMPONENT := jackery_navi
SRC_DIR   := custom_components/$(COMPONENT)
DIST_DIR  := dist

VERSION := $(shell sed -n 's/^[[:space:]]*"version":[[:space:]]*"\([^"]*\)".*/\1/p' $(SRC_DIR)/manifest.json)
TAG_OFFSET := $(shell git describe --tags --long 2>/dev/null | sed -E 's/^.*-([0-9]+)-g[0-9a-f]+$$/\1/')
SHORT_REF := $(shell git rev-parse --short HEAD 2>/dev/null)
COMMIT_TIME := $(shell git log -1 --format=%ct 2>/dev/null)

ifneq ($(TAG_OFFSET),)
BUILD_ID := $(VERSION)-$(TAG_OFFSET)
else
BUILD_ID := $(VERSION)-g$(SHORT_REF)
endif

ARCHIVE := $(DIST_DIR)/$(COMPONENT)-$(BUILD_ID).tar.gz
SOURCES := $(shell find $(SRC_DIR) -type f ! -path '*/__pycache__/*' ! -name '*.pyc')

.PHONY: all version clean

all: $(ARCHIVE)

$(ARCHIVE): $(SOURCES) Makefile
	@test -n "$(VERSION)" || { echo "no version in $(SRC_DIR)/manifest.json" >&2; exit 1; }
	@test -n "$(SHORT_REF)" || { echo "no git commit yet: commit first, the archive name needs a ref" >&2; exit 1; }
	@mkdir -p $(DIST_DIR)
	tar --create --owner=0 --group=0 --numeric-owner --sort=name --mtime=@$(COMMIT_TIME) \
		--exclude=__pycache__ --exclude='*.pyc' $(SRC_DIR) | gzip -9n > $@.tmp
	@mv $@.tmp $@
	@echo "$@"

version:
	@echo $(BUILD_ID)

clean:
	rm -rf $(DIST_DIR)
