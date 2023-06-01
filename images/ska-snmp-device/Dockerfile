ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.4.1"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.4.1"
FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE

USER root

WORKDIR /app
COPY --chown=tango:tango . /app

RUN poetry config virtualenvs.create false
RUN poetry install --only main

USER tango
