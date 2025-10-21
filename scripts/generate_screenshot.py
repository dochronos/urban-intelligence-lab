# scripts/generate_screenshot.py
import argparse, time, base64
from pathlib import Path
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import chromedriver_autoinstaller
    chromedriver_autoinstaller.install()
except Exception:
    pass

DEFAULT_ALT = ("Urban Intelligence Lab – Week 2 dashboard showing calibrated headway analysis "
               "and AI-generated insights for Buenos Aires Subte and Premetro.")

def wait_for_streamlit(driver, timeout=30):
    # Contenedor principal de Streamlit
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="stAppViewContainer"]'))
    )

def wait_for_ai_summary(driver, timeout=60):
    # Busca el heading "AI Summary" o el texto "Insights (draft)"
    ai_locators = [
        (By.XPATH, "//h3[normalize-space()='AI Summary']"),
        (By.XPATH, "//*[contains(normalize-space(.), 'AI Summary')]"),
        (By.XPATH, "//*[contains(normalize-space(.), 'Insights (draft)')]"),
    ]
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in ai_locators:
            els = driver.find_elements(by, sel)
            if els:
                return True
        time.sleep(0.5)
    return False

def progressive_scroll(driver, steps=14, pause=0.7):
    height = driver.execute_script("return document.body.scrollHeight")
    step = max(int(height / steps), 400)
    y = 0
    for _ in range(steps + 2):
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(pause)
        y += step
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.6)

def wait_for_stability(driver, settle_seconds=4, poll=0.5, max_wait=45):
    stable_for = 0.0
    last_h = -1
    waited = 0.0
    while waited < max_wait:
        h = driver.execute_script(
            "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
        )
        if h == last_h:
            stable_for += poll
            if stable_for >= settle_seconds:
                return
        else:
            stable_for = 0.0
            last_h = h
        time.sleep(poll)
        waited += poll

def cdp_fullpage_png(driver):
    driver.set_window_size(1920, 1080)
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    cs = metrics["contentSize"]
    clip = {
        "x": 0, "y": 0,
        "width": float(min(int(cs["width"]), 5000)),
        "height": float(min(int(cs["height"]), 22000)),
        "scale": 1
    }
    res = driver.execute_cdp_cmd("Page.captureScreenshot",
        {"format": "png", "fromSurface": True, "clip": clip, "captureBeyondViewport": True})
    return Image.open(BytesIO(base64.b64decode(res["data"])))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--alt", default=DEFAULT_ALT)
    ap.add_argument("--wait", type=int, default=12)
    ap.add_argument("--settle", type=int, default=4)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--await-ai", action="store_true", help="Wait for AI Summary/Insights to appear")
    args = ap.parse_args()

    out_png = Path(args.output)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_alt = out_png.with_name(out_png.stem + "_alt.txt")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=opts)
    try:
        for attempt in range(1, args.retries + 2):
            print(f"🌐 Opening {args.url} (attempt {attempt})")
            driver.get(args.url)
            wait_for_streamlit(driver, timeout=45)
            time.sleep(max(args.wait - 2, 5))

            progressive_scroll(driver)
            if args.await_ai:
                print("⏳ Waiting for AI Summary…")
                wait_for_ai_summary(driver, timeout=60)
            wait_for_stability(driver, settle_seconds=args.settle, max_wait=60)

            img = cdp_fullpage_png(driver)
            if img.height >= 800:
                img.save(out_png.as_posix())
                out_alt.write_text(args.alt, encoding="utf-8")
                print(f"✅ Saved: {out_png.as_posix()}")
                print(f"📝 Alt text: {out_alt.as_posix()}")
                return
            print("⚠️ Capture looks short; retrying with longer waits…")
            time.sleep(8)
        raise SystemExit("❌ Could not capture a full page after retries.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
