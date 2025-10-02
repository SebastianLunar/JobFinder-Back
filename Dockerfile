# Usa una imagen base de Python que sea compatible con Debian/Ubuntu
# Usamos Bullseye para compatibilidad con las últimas librerías
FROM python:3.11-slim-bullseye

# 1. Instalar dependencias de sistema necesarias para Chrome
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
    libgbm-dev

# 2. Instalar Chromium
# La ruta de este binario es /usr/bin/chromium.
# Esto es más seguro que instalar 'google-chrome' en contenedores.
RUN apt-get install -y chromium

# 3. Configurar el entorno (Render por defecto)
ENV PYTHONUNBUFFERED 1
ENV CHROME_BIN /usr/bin/chromium  # <-- ¡ESTO ES CRUCIAL!

# 4. Copiar código e instalar dependencias de Python
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/

# 5. Comando de inicio (Ajusta esto a tu comando de Render/Gunicorn)
CMD ["gunicorn", "jobfinder.wsgi:application", "--bind", "0.0.0.0:$PORT"]