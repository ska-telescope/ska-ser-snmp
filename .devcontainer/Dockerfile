FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.35 AS buildenv
RUN apt-get update && apt-get install gnupg2 python3-venv -y
ENV TZ="United_Kingdom/London"
ENV DEBIAN_FRONTEND=noninteractive
RUN sudo apt-get install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get install -y python3.11 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2
