FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y permitir logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Configurar el directorio de trabajo
WORKDIR /app

# Instalar paquetes del sistema necesarios para algunas dependencias (OpenCV, compilación)
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	ca-certificates \
	wget \
	curl \
	libgl1 \
	libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias PyPI (excepto PyTorch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar PyTorch CPU build (especificar versión + índice oficial)
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.10.0+cpu

# Copiar el resto del código y configurar el PYTHONPATH
COPY . .
ENV PYTHONPATH=/app

# Default command (se puede sobrescribir desde docker-compose)
CMD ["python", "-m", "sim.runner"]