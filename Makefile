PROJECT = ska-low-itf-devices

#### PYTHON CUSTOM VARS
DOCS_SPHINXOPTS=-n -W --keep-going

# better be verbose for debugging
PYTHON_VARS_AFTER_PYTEST ?= -v

-include PrivateRules.mak

include .make/base.mk

include .make/python.mk

PYTHON_LINE_LENGTH = 88
PYTHON_VARS_AFTER_PYTEST = --forked

include .make/oci.mk

# Build context should be the root for all images
OCI_IMAGE_BUILD_CONTEXT = $(PWD)

include .make/helm.mk

include .make/k8s.mk

docs-pre-build:
	poetry config virtualenvs.create false
	poetry install --no-root --only docs

python-post-lint:
	mypy src/ tests/

### PYTHON END

.PHONY: docs-pre-build python-post-lint
