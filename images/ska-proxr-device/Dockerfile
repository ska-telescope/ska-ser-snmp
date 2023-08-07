ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.4.2"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.4.2"
FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE

USER root

RUN poetry config virtualenvs.create false

WORKDIR /app

COPY --chown=tango:tango ./pyproject.toml ./poetry.lock /app/
RUN poetry install --without=dev --no-root

COPY --chown=tango:tango . /app
RUN poetry install --without=dev

USER tango
