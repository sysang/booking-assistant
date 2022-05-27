FROM python:3.8.10

WORKDIR /usr/src/app

RUN apt-get update && apt-get dist-upgrade -y --no-install-recommends

RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    tinydb \
    && rm -rf /pip_pkg \
    && rm -rf /tmp/* \
    && rm -rf /root/.cache

# COPY . .

CMD [ "gunicorn", "-b", "0.0.0.0:8000", "botfrontend.wsgi:application" ]









