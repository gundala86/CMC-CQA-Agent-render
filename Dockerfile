
FROM python:3.10-slim

RUN apt-get update && apt-get install -y poppler-utils gcc libglib2.0-0 libgl1-mesa-glx

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
