ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.3.35"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.3.22"
FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE

USER root

# Uncomment this when your python package temporarily installs from git.
# RUN apt-get update && apt-get install -y git

RUN poetry config virtualenvs.create false

WORKDIR /app
COPY --chown=tango:tango . /app

# RUN poetry install
# hangs on: • Installing untokenize (0.1.1)
# so use pip instead
RUN poetry export --format requirements.txt --output poetry-requirements.txt --without-hashes && \
    pip install -r poetry-requirements.txt && \
    rm poetry-requirements.txt && pip install .

USER tango
