import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from config import URL_HOUSE_STATE, UPTIMEROBOT_API_KEY, DTEK_URL, CHECK_DTEK
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
        self.driver = None
        self.check_dtek = CHECK_DTEK

    def setup_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")

            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_page_load_timeout(30)
                logger.info("WebDriver initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize WebDriver: {e}")
                self.driver = None

    def restart_driver(self):
        logger.info("Restarting WebDriver...")
        if self.driver:
            self.driver.quit()
        self.driver = self.setup_driver()
        logger.info("WebDriver restarted successfully")

    def get_actual_state(self):
        logger.info(f"UPTIMEROBOT_API_KEY: {'Set' if UPTIMEROBOT_API_KEY and UPTIMEROBOT_API_KEY.lower() != 'none' else 'Not set'}")
        logger.info(f"URL_HOUSE_STATE: {URL_HOUSE_STATE}")

        if UPTIMEROBOT_API_KEY and UPTIMEROBOT_API_KEY.lower() != 'none':
            logger.info("Using UptimeRobot API to get state")
            return self.get_actual_state_api()
        elif URL_HOUSE_STATE:
            logger.info("Using web scraping to get state")
            return self.get_actual_state_scrape()
        else:
            logger.error("No method available to get actual state. Please provide UPTIMEROBOT_API_KEY or URL_HOUSE_STATE.")
            return -1
        

    def get_stable_outage_state(self):
        if not DTEK_URL or not self.check_dtek:
            logger.warning("DTEK_URL not provided or CHECK_DTEK is False. Skipping stable outage state check.")
            return {"start": "none", "end": "none"}

        self.setup_driver()
        if self.driver is None:
            logger.error("WebDriver not available. Cannot get stable outage state.")
            return {"start": "none", "end": "none"}

        try:
            self.driver.get(DTEK_URL)
            status_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.m-attention__text"))
            )

            if status_element:
                time_pattern = r'\b(\d{2}:\d{2})\b'
                times = re.findall(time_pattern, status_element.text)
                if len(times) >= 2:
                    return {"start": times[0], "end": times[1]}
                else:
                    logger.warning("Could not find enough time entries in the text.")
                    return {"start": "00", "end": "24"}
            else:
                logger.warning("Status element not found or has no text.")
        except Exception as e:
            logger.error(f"Failed to get stable outage state: {e}")
        
        return {"start": "none", "end": "none"}

        
    def get_actual_state_api(self):
        logger.info("Getting actual state from UptimeRobot API...")
        try:
            response = requests.get(
                "https://api.uptimerobot.com/v2/getMonitors",
                params={"api_key": UPTIMEROBOT_API_KEY, "format": "json", "monitors": URL_HOUSE_STATE},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if data["stat"] == "ok":
                status = data["monitors"][0]["status"]
                return 0 if status == 2 else 2
            else:
                logger.error(f"Failed to get status from UptimeRobot API: {data.get('error', 'Unknown error')}")
                return -1
        except Exception as e:
            logger.error(f"Error while getting actual state from API: {str(e)}")
            return -1


    def get_actual_state_scrape(self):
        logger.info("Getting actual state from scraping...")
        self.setup_driver()
        if self.driver is None:
            logger.error("WebDriver not available. Cannot scrape for actual state.")
            return -1

        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.driver.get(URL_HOUSE_STATE)
                
                try:
                    down_element = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.uk-text-danger"))
                    )
                    if "down" in down_element.text.lower():
                        return 2  # Світла немає
                except TimeoutException:
                    pass
                
                try:
                    operational_element = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.uk-text-primary"))
                    )
                    if "operational" in operational_element.text.lower():
                        return 0  # Світло є
                except TimeoutException:
                    pass
                
                logger.warning("Could not determine clear state from scraping. Defaulting to possible outage.")
                return 1
            
            except WebDriverException as e:
                logger.error(f"WebDriver error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(10) 
                    self.quit_driver()
                    self.setup_driver()
                else:
                    logger.error("Max retries reached. Unable to scrape.")
                    return -1
            except Exception as e:
                logger.error(f"Unexpected error while getting actual state from scraping: {str(e)}")
                return -1
            
    def quit_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error while quitting WebDriver: {e}")
            finally:
                self.driver = None

    def time_in_range(self, current_hour, todays_limits):
        start_hour = int(todays_limits["start"].split(":")[0]) if todays_limits["start"] != "none" else None
        end_hour = int(todays_limits["end"].split(":")[0]) if todays_limits["end"] != "none" else None
        return start_hour <= current_hour < end_hour if start_hour is not None and end_hour is not None else False

    def __del__(self):
        self.quit_driver()