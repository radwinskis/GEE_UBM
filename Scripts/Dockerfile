FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the Python scripts into the container
COPY . .

# Setting entry point to run the daily orchestrator script
ENTRYPOINT ["python", "daily_ubm_orchestrator.py"]