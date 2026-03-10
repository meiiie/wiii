FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir \
    matplotlib \
    openpyxl \
    pandas \
    python-docx \
    xlsxwriter

WORKDIR /workspace
