FROM python:3.11.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV NACOS_SERVER_ADDR=nacos:8848
ENV NACOS_NAMESPACE=dev
ENV NACOS_USERNAME=nacos
ENV NACOS_PASSWORD=nacos

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]