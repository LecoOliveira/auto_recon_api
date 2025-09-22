FROM python:3.13-slim
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app/

RUN pip install poetry

RUN poetry config installer.max-workers 10

EXPOSE 8000
COPY . .
RUN poetry install --no-interaction --no-ansi --without dev
CMD poetry run uvicorn --host 0.0.0.0 auto_recon_api.app:app