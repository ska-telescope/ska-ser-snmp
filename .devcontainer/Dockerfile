FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.35 AS buildenv
RUN apt-get update && apt-get install gnupg2 python3-venv -y
RUN sudo apt-get install -y python3.11 && sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 2
