FROM mcr.microsoft.com/playwright:v1.52.0-noble

USER root
RUN mkdir -p /opt/wiii-browser

WORKDIR /opt/wiii-browser

RUN npm init -y \
    && npm install playwright@1.52.0
