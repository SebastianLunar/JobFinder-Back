import json
import time
import os
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
    chrome_options.add_argument("--headless")  # ejecución sin UI
    chrome_options.add_argument("--no-sandbox")  # necesario en contenedores
    chrome_options.add_argument("--disable-dev-shm-usage")  # evita /dev/shm pequeño
    chrome_options.add_argument("--disable-gpu")  # seguro en headless
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")

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
                # Intentar con chromedriver en PATH
                driver = webdriver.Chrome(options=chrome_options)
            except Exception:
                # Último recurso: webdriver_manager (requiere red saliente)
                driver_path = ChromeDriverManager().install()
                driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)
    except Exception as e:
        return JsonResponse({
            "error": f"Error al inicializar Chrome: {e}",
            "chrome_bin": CHROME_BIN,
            "chromedriver_path": os.environ.get("CHROMEDRIVER_PATH"),
            "checked_candidates": checked_candidates,
        }, status=500)


    # --- LOGIN ---
    driver.get("https://www.linkedin.com/login")
    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "global-nav-search"))
    )

    # --- BÚSQUEDA ---
    url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}{filters}"
    driver.get(url)
    time.sleep(3)
    
    try:
        no_results_banner = driver.find_element(By.CLASS_NAME, "jobs-search-no-results-banner")
        if no_results_banner.is_displayed():
            driver.quit()
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