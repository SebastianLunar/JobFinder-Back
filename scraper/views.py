import json
import time
import os
import tempfile
import shutil
from uuid import uuid4
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

load_dotenv()

email = os.getenv('LINKEDIN_EMAIL')
password = os.getenv('LINKEDIN_PASSWORD')

HOURS_TO_SECONDS = {
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
    "72h": 259200,
}

@csrf_exempt
def scrape_linkedin(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    keyword = body.get("keyword", "python developer")
    location = body.get("location", "remote")
    exclude_words = body.get("exclude", [])
    modality = body.get("modality")
    time_filter = body.get("time_filter")

    # --- FILTROS ---
    filters = ""

    if modality:
        modality_map = {"remoto": "2", "hibrido": "3", "presencial": "1"}
        if modality in modality_map:
            filters += f"&f_WT={modality_map[modality]}"
    if time_filter in HOURS_TO_SECONDS:
        seconds = HOURS_TO_SECONDS[time_filter]
        filters += f"&f_TPR=r{seconds}"

    # --- INICIALIZACIÓN DEL WEBDRIVER PARA RAILWAY ---
    
    # 1. Configurar Opciones de Chrome Headless (necesarias en Render/Docker)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # ejecución sin UI en servidor (modo moderno)
    chrome_options.add_argument("--no-sandbox")  # necesario en contenedores
    chrome_options.add_argument("--disable-dev-shm-usage")  # evita /dev/shm pequeño
    chrome_options.add_argument("--disable-gpu")  # seguro en headless
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    # User-Agent fijo tipo Chrome estable en Linux
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    # Reducir bloqueos por detección de automatización (compat. Selenium 3)
    try:
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_prefs = {"profile.managed_default_content_settings.images": 2}
        chrome_options.add_experimental_option("prefs", chrome_prefs)
    except Exception:
        pass
    # Estrategia de carga más rápida
    try:
        chrome_options.page_load_strategy = 'eager'
    except Exception:
        pass

    # Usar SIEMPRE un directorio de datos único por request para evitar bloqueos
    user_data_dir = tempfile.mkdtemp(prefix="chrome-user-data-")
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    # 2. Detectar binario de Chrome/Chromium (validando ruta)
    checked_candidates = []
    CHROME_BIN = os.environ.get("CHROME_BIN")
    # si viene desde env pero no existe, ignorarlo
    if CHROME_BIN and not os.path.exists(CHROME_BIN):
        checked_candidates.append((CHROME_BIN, False))
        CHROME_BIN = None
    if not CHROME_BIN:
        for candidate in [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]:
            exists = os.path.exists(candidate)
            checked_candidates.append((candidate, exists))
            if exists:
                CHROME_BIN = candidate
                break
    if CHROME_BIN:
        chrome_options.binary_location = CHROME_BIN

    # 3. Inicializar el driver (probar chromedriver del sistema, luego PATH, luego webdriver_manager)
    try:
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if chromedriver_path and os.path.exists(chromedriver_path):
            driver = webdriver.Chrome(executable_path=chromedriver_path, options=chrome_options)
        else:
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception:
                driver_path = ChromeDriverManager().install()
                driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)
    except Exception as e:
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass
        return JsonResponse({
            "error": f"Error al inicializar Chrome: {e}",
            "chrome_bin": CHROME_BIN,
            "chromedriver_path": os.environ.get("CHROMEDRIVER_PATH"),
            "checked_candidates": checked_candidates,
        }, status=500)


    # --- LOGIN ---
    driver.set_page_load_timeout(90)
    driver.get("https://www.linkedin.com/login")
    # Esperar campos de login
    try:
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "username")))
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "password")))
    except Exception as e:
        driver.quit()
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass
        return JsonResponse({"error": f"Timeout esperando formulario de login: {e}"}, status=504)

    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    # Esperar a que cargue la navegación post-login o al menos la barra de búsqueda (compat. Selenium 3)
    try:
        WebDriverWait(driver, 60).until(
            lambda d: (d.find_elements(By.ID, "global-nav-search") or ("/feed/" in d.current_url))
        )
    except Exception as e:
        # Puede haber desafíos/captcha; devolvemos diagnóstico
        driver.quit()
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass
        # Agregar contexto útil para diagnosticar
        return JsonResponse({
            "error": f"Timeout post-login, posible bloqueo/captcha: {e}",
            "current_url": getattr(driver, "current_url", None),
            "title": None  # no podemos leer title si driver ya fue quit
        }, status=504)

    # --- BÚSQUEDA ---
    url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}{filters}"
    driver.get(url)
    # Espera a que aparezca la lista de empleos (mejor que sleep fijo)
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "job-card-container"))
        )
    except Exception:
        pass
    
    try:
        no_results_banner = driver.find_element(By.CLASS_NAME, "jobs-search-no-results-banner")
        if no_results_banner.is_displayed():
            driver.quit()
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
            except Exception:
                pass
            return JsonResponse({
                "results": [],
                "message": "No se encontraron resultados para la búsqueda."
            }, status=200)
    except Exception:
        pass

    jobs_data = []
    job_cards = driver.find_elements(By.CLASS_NAME, "job-card-container")

    for i, job in enumerate(job_cards[:5]):
        try:
            job.click()
            time.sleep(2)

            title = driver.find_element(By.CLASS_NAME, "job-details-jobs-unified-top-card__job-title").text
            company = driver.find_element(By.CLASS_NAME, "job-details-jobs-unified-top-card__company-name").text
            description = driver.find_element(By.ID, "job-details").text
            link = driver.current_url

            content_to_check = f"{title} {description}".lower()
            if any(word.lower() in content_to_check for word in exclude_words):
                continue

            jobs_data.append({
                "title": title,
                "company": company,
                "description": description,
                "link": link,
            })

        except Exception as e:
            print(f"Error en oferta {i}: {e}")
            continue

    driver.quit()

    return JsonResponse({"results": jobs_data}, safe=False)