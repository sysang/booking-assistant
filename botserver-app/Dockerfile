ARG RASA_IMAGE

FROM ${RASA_IMAGE}

# Change back to root user to install dependencies
USER root

# To install system dependencies
RUN apt-get update -qq && apt-get dist-upgrade --yes --no-install-recommends

RUN pip install --no-cache-dir transformers \
    && rm -rf /pip_pkg \
    && rm -rf /tmp/* \
    && rm -rf /root/.cache

RUN apt-get autoremove --yes gcc \
    && apt-get clean --yes \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Use subdirectory as working directory
WORKDIR /app

# By best practices, don't run the code with root user
USER 1001
