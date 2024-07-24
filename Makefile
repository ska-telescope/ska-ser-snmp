#
# Project makefile for a ska-ser-snmp project. 
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.

PROJECT = ska-ser-snmp
include .make/base.mk

########################################################################
# DOCS
########################################################################
include .make/docs.mk

DOCS_SPHINXOPTS =-n  -W --keep-going

docs-pre-build:
	poetry config virtualenvs.create false
	poetry install --no-root --only docs

.PHONY: docs-pre-build

########################################################################
# PYTHON
########################################################################
include .make/python.mk

PYTHON_LINE_LENGTH = 88
PYTHON_LINT_TARGET = src tests  ## Paths containing python to be formatted and linted
PYTHON_VARS_AFTER_PYTEST = -v --forked 

PYTHON_TEST_FILE = tests

# CI tests run as root; snmpsim doesn't want to run as root
ifneq ($(CI_JOB_ID),)
	export SKA_SNMP_DEVICE_SIMULATOR_USER = tango:tango
endif

python-pre-test:
	echo "$(SKA_SNMP_DEVICE_SIMULATOR_USER)"

python-post-lint:
	mypy --config-file mypy.ini src/ tests

.PHONY: python-pre-test python-post-lint

########################################################################
# OCI
########################################################################
include .make/oci.mk

# Build context should be the root for all images
OCI_IMAGE_BUILD_CONTEXT = $(PWD)

########################################################################
# HELM
########################################################################
include .make/helm.mk

########################################################################
# K8S
########################################################################
include .make/k8s.mk

-include PrivateRules.mak
