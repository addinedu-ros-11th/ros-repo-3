FROM python:3.12-slim

WORKDIR /app

# Install service deps
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service/ ./service/
COPY ui/mobile/dist ./ui/mobile/dist/
COPY ui/robot/dist  ./ui/robot/dist/
COPY ui/admin/dist  ./ui/admin/dist/

EXPOSE 8001
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8001"]
