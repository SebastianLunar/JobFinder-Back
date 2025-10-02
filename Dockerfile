# Usa la imagen base que ya tienes
FROM python:3.11-bullseye

# 1. Instalar dependencias de sistema y clave GPG para Google Chrome
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

# 2. Descargar e instalar Google Chrome directamente (método más robusto)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-archive.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-archive.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Instalar el paquete de Google Chrome (estable)
RUN apt-get update && apt-get install -y google-chrome-stable \
    # Limpiar el cache para reducir el tamaño de la imagen
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Configurar el entorno (Render por defecto)
ENV PYTHONUNBUFFERED 1
# 🚨 Establece la variable que tu código usa para el binario de Google Chrome
ENV CHROME_BIN /usr/bin/google-chrome

# 4. Copiar código e instalar dependencias de Python
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/

# 5. Comando de inicio (Ajusta esto a tu comando de Render/Gunicorn)
CMD ["gunicorn", "jobfinder.wsgi:application", "--bind", "0.0.0.0:$PORT"]