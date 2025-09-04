FROM python:3.12-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apk add --no-cache \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
        build-base

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create static and media directories
RUN mkdir -p /app/staticfiles /app/media

# Expose port
EXPOSE 8000

# Run migrations and collect static files
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && python manage.py runserver 0.0.0.0:8000"]
