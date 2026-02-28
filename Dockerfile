ARG PYTHON_VERSION=3.10-slim
FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build deps AND runtime deps
RUN apt-get update && apt-get install -y \
    libpq-dev \
    libpq5 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /root/.cache/

COPY . /code

# Run collectstatic during build with a dummy Secret Key
# This ensures files are baked into the image
# RUN SECRET_KEY=dummy-key-for-build python manage.py collectstatic --noinput
# RUN python manage.py collectstatic --noinput || (python manage.py collectstatic --noinput 2>&1)

EXPOSE 8080
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:8080 --workers 2 semanticiq.wsgi"]