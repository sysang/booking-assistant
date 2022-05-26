ARG RASA_IMAGE

FROM rasa/rasa:2.8.25

# Use subdirectory as working directory
WORKDIR /app

# Change to root user to install dependencies
# USER root

CMD ["/bin/bash"]

# RUN pip install poetry
# RUN poetry config virtualenvs.create false
# RUN poetry install

COPY . /app

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Don't use root user to run code
USER 1001
