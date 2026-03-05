FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 9100
# HTTP-only mode (no ROS2 in container)
CMD ["python", "src/malle_controller/bridge_node.py"]