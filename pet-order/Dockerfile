FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV MONGO_URI="mongodb://mongodb:27017"
ENV DB_NAME="petstore"

EXPOSE 8080

CMD ["python", "pet_order.py"]
