FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY deploy/streamlit-entrypoint.py /usr/local/bin/cocoa-streamlit-entrypoint.py
EXPOSE 8501
ENTRYPOINT ["python", "/usr/local/bin/cocoa-streamlit-entrypoint.py"]