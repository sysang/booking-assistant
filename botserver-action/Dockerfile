# Extend the official Rasa SDK image
FROM rasa/rasa-sdk:2.8.4

# Change back to root user to install dependencies
USER root

# To install system dependencies
RUN apt-get update -qq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# To install packages from PyPI
# RUN pip install -U --no-cache-dir mailchimp3~=3.0.2 \
#                             oauth2client~=4.1.2 \
#                             gspread~=3.0.0 \
#                             beautifulsoup4~=4.6.3 \
#                             requests~=2.21.0 \
#                             geopy~=1.18.1 \
#                             pandas~=0.24.1 \
#                             algoliasearch>=2.0,<3.0 \
#                             spacy~=2.1.9

# RUN python -m spacy download en

# Use subdirectory as working directory
WORKDIR /app

# Copy any additional custom requirements, if necessary (uncomment next line)
# COPY actions/requirements-actions.txt ./

# Install extra requirements for actions code, if necessary (uncomment next line)
# RUN pip install -r requirements-actions.txt

# Copy actions folder to working directory
COPY . /app/actions

# By best practices, don't run the code with root user
USER 1001
