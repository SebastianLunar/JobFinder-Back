# Usa la imagen base que ya tienes
FROM python:3.11-bullseye

# 1. Instalar dependencias del sistema necesarias y Chrome estable (vía .deb directo)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    fonts-liberation \
    xdg-utils \
    libnss3 \
    libasound2 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libu2f-udev \
    ca-certificates \
&& rm -rf /var/lib/apt/lists/*

# Descargar e instalar Google Chrome estable directamente
RUN set -eux; \
    curl -fsSL -o /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb; \
    apt-get update; \
    apt-get install -y /tmp/google-chrome.deb || apt-get -f install -y; \
    rm -f /tmp/google-chrome.deb; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# 2. Configurar el entorno
ENV PYTHONUNBUFFERED 1
# Establecer variable usada por la app para el binario de Chrome
ENV CHROME_BIN=/usr/bin/google-chrome-stable
# Alias para mayor compatibilidad
RUN ln -sf /usr/bin/google-chrome-stable /usr/bin/google-chrome

# 4. Copiar código e instalar dependencias de Python
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/

# 5. Comando de inicio (Ajusta esto a tu comando de Render/Gunicorn)
CMD ["gunicorn", "jobfinder.wsgi:application", "--bind", "0.0.0.0:$PORT"]