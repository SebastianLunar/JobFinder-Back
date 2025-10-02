# Usa una imagen base de Python (la que elegiste)
FROM python:3.11-slim-bullseye

# 1. Instalar dependencias de sistema necesarias para Chrome/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libnss3 \
    libasound2 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm-dev \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm-dev \
    # 🚨 Instalar Chromium y sus dependencias (puede llamarse 'chromium' o 'chromium-browser')
    chromium \
    # Limpiar el cache para reducir el tamaño de la imagen
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Crear Enlace Simbólico (Symlink)
# Esto es crucial: asegura que el binario se llame 'chromium' y esté en /usr/bin.
RUN ln -s /usr/bin/chromium-browser /usr/bin/chromium

# 3. Configurar el entorno
ENV PYTHONUNBUFFERED 1
# 🚨 Establece la variable que tu código usa para el binario
ENV CHROME_BIN /usr/bin/chromium

# 4. Copiar código e instalar dependencias de Python
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/

# 5. Comando de inicio (Ajusta esto a tu comando de Render/Gunicorn)
CMD ["gunicorn", "jobfinder.wsgi:application", "--bind", "0.0.0.0:$PORT"]