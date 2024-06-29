import os
import schedule
import time
import csv
import json
import re
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from colorama import init, Fore, Back, Style
import logging
from dotenv import load_dotenv
import requests
import sqlite3

load_dotenv()

init(autoreset=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GROUP_NUMBER = os.getenv('GROUP_NUMBER')
URL_HOUSE_STATE = os.getenv('URL_HOUSE_STATE')
DTEK_URL = os.getenv('DTEK_URL')
UPTIMEROBOT_API_KEY = os.getenv('UPTIMEROBOT_API_KEY')
CHECK_DTEK = True
CHECK_INTERVAL = 60  # minutes
SCHEDULE_FILE = 'schedule.json'
RESULTS_FILE = 'electricity_comparison.csv'
STABLE_OUTAGE_TIME_CHECK = "00:15"
STABLE_OUTAGE_TIME_2_CHECK = "12:15"
UPDATE_SCHEDULE_TIME = "00:20"

STATE_COLORS = {
    -1: Fore.LIGHTBLACK_EX,
    0: Fore.GREEN,
    1: Fore.YELLOW,
    2: Fore.RED
}

STATE_NAMES = {
    0: "Світло є",
    1: "Можливо відключення",
    2: "Світла немає"
}

class LocalBlackoutMonitor:
    def __init__(self):
        self.schedule = {}
        self.todays_limits = {"start": "none", "end": "none"}
        self.driver = self.setup_driver()
        self.current_actual_state = None
        self.check_dtek = CHECK_DTEK
        self.db_connection = self.setup_database()

    @staticmethod
    def setup_database():
        db_path = os.path.join(os.path.dirname(__file__), 'Data', 'electricity_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS electricity_status (
                timestamp TEXT PRIMARY KEY,
                expected_state INTEGER,
                actual_state INTEGER,
                today_state INTEGER,
                comparison TEXT
            )
        ''')
        conn.commit()
        return conn


    def record_results(self, current_time, expected_state, actual_state, today_state, comparison):
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO electricity_status
            (timestamp, expected_state, actual_state, today_state, comparison)
            VALUES (?, ?, ?, ?, ?)
        ''', (current_time.strftime("%Y-%m-%d %H:%M:%S"), expected_state, actual_state, today_state, comparison))
        self.db_connection.commit()

    def get_daily_energy_summary(self, date=None):
        if date is None:
            date = datetime.now().date()
        
        cursor = self.db_connection.cursor()
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN actual_state = 0 THEN 1 ELSE 0 END) as on_hours,
                SUM(CASE WHEN actual_state = 2 THEN 1 ELSE 0 END) as off_hours,
                SUM(CASE WHEN actual_state IN (-1, 1) OR actual_state IS NULL THEN 1 ELSE 0 END) as unknown_hours
            FROM electricity_status
            WHERE DATE(timestamp) = ?
        ''', (date.strftime("%Y-%m-%d"),))
        
        result = cursor.fetchone()
        return {
            "on_hours": result[0] or 0,
            "off_hours": result[1] or 0,
            "unknown_hours": result[2] or 0
        }

    def display_daily_energy_summary(self, date=None):
        summary = self.get_daily_energy_summary(date)
        
        print("\nЩоденний підсумок енергопостачання:")
        print(f"{Fore.GREEN}Електроенергія увімкнена: {summary['on_hours']} годин")
        print(f"{Fore.RED}Електроенергія вимкнена: {summary['off_hours']} годин")
        print(f"{Fore.YELLOW}Невідомий стан: {summary['unknown_hours']} годин")

    @staticmethod
    def setup_driver():
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        return webdriver.Chrome(options=chrome_options)
    
    def restart_driver(self):
        logger.info("Restarting WebDriver...")
        if self.driver:
            self.driver.quit()
        self.driver = self.setup_driver()
        logger.info("WebDriver restarted successfully")

    def update_schedule(self):
        try:
            with open(SCHEDULE_FILE, 'r') as file:
                schedule_data = json.load(file)
                self.schedule = {int(k): v for k, v in schedule_data[str(GROUP_NUMBER)].items()}
            logger.info("Schedule updated successfully for the new day.")
        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")

    def get_expected_state(self, current_time):
        day = current_time.weekday()
        hour = current_time.hour
        try:
            return self.schedule[day][hour]
        except KeyError:
            logger.warning(f"No schedule data available for day {day}, hour {hour}.")
            return -1

    def get_stable_outage_state(self):
        if not DTEK_URL or not self.check_dtek:
            logger.warning("DTEK_URL not provided. Skipping stable outage state check.")
            return

        try:
            self.driver.get(DTEK_URL)
            status_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.m-attention__text"))
            )

            if status_element:
                time_pattern = r'\b(\d{2}:\d{2})\b'
                times = re.findall(time_pattern, status_element.text)
                if len(times) >= 2:
                    self.todays_limits["start"], self.todays_limits["end"] = times[0], times[1]
                    logger.info(f"Outage from: {self.todays_limits['start']} to: {self.todays_limits['end']}")
                else:
                    logger.warning("Could not find enough time entries in the text.")
                    self.todays_limits["start"], self.todays_limits["end"] = "00", "24"
            else:
                logger.warning("Status element not found or has no text.")
        except Exception as e:
            logger.error(f"Failed to get stable outage state: {e}")
            self.todays_limits["start"], self.todays_limits["end"] = "none", "none"

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
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.driver.get(URL_HOUSE_STATE)
                
                try:
                    down_element = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.uk-text-danger"))
                    )
                    if "down" in down_element.text.lower():
                        return 2  # Світла немає
                except TimeoutException:
                    pass
                
                try:
                    operational_element = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.uk-text-primary"))
                    )
                    if "operational" in operational_element.text.lower():
                        return 0  # Світло є
                except TimeoutException:
                    pass
                
                logger.warning("Could not determine clear state from scraping. Defaulting to possible outage.")
                return -1
            
            except WebDriverException as e:
                logger.error(f"WebDriver error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    self.restart_driver()
                else:
                    logger.error("Max retries reached. Unable to scrape.")
                    return -1
            except Exception as e:
                logger.error(f"Unexpected error while getting actual state from scraping: {str(e)}")
                return -1

    @staticmethod
    def compare_states(expected, actual, today_state):
        if today_state == -1 or expected == -1 or actual == -1:
            return "Немає доступних даних"
        
        if not today_state:
            if actual == 0:
                return "Співпадіння"
            
        if expected == actual:
            return "Співпадіння"
        
        return "Можливе неспівпадіння" if expected == 1 else "Неспівпадіння"
    
    def time_in_range(self, current_time):
        start_hour = int(self.todays_limits["start"].split(":")[0]) if self.todays_limits["start"] != "none" else None
        end_hour = int(self.todays_limits["end"].split(":")[0]) if self.todays_limits["end"] != "none" else None
        return start_hour <= current_time < end_hour if start_hour is not None and end_hour is not None else False

    def display_today_schedule(self, current_time):
        day = current_time.weekday()
        next_day = (day + 1) % 7
        today_schedule = self.schedule.get(day, [])
        next_day_schedule = self.schedule.get(next_day, [])

        print("\nРозклад електропостачання на сьогодні:")
        for hour, state in enumerate(today_schedule):
            time_style = f"{Back.WHITE}{Fore.BLACK}" if hour == current_time.hour else ""

            limit_indicator = "[+]"
            state_color = STATE_COLORS[state]
            if self.check_dtek:
                limit_indicator = "[+]" if self.time_in_range(hour) else "[-]"
                state_color = STATE_COLORS[state] if self.time_in_range(hour) else STATE_COLORS[-1]

            current_hour = f"({STATE_COLORS[self.current_actual_state]}{STATE_NAMES[self.current_actual_state]}{Style.RESET_ALL})" if hour == current_time.hour else ""
            print(f"{time_style}{hour:02d}:00 {limit_indicator} {state_color}{STATE_NAMES[state]}{Style.RESET_ALL} {current_hour}")

        print("\nПерші 5 годин наступного дня:")
        for hour, state in enumerate(next_day_schedule[:5]):
            print(f"{hour:02d}:00 {STATE_COLORS[state]}{STATE_NAMES[state]}{Style.RESET_ALL}")

    def check_and_record(self, check_only=False):
        current_time = datetime.now()
        hours = current_time.hour
        logging.info(f"Checking at {current_time}")
        expected_state = self.get_expected_state(current_time)
        self.current_actual_state = self.get_actual_state()
        logger.info(f"Очікувано: {expected_state}, Фактично: {self.current_actual_state}")
        today_state = int(self.time_in_range(hours))
        comparison = self.compare_states(expected_state, self.current_actual_state, today_state)
        
        print(f"\n{Fore.CYAN}Час: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Очікувано: {STATE_COLORS[expected_state]}{STATE_NAMES[expected_state]}")
        print(f"Фактично: {STATE_COLORS[self.current_actual_state]}{STATE_NAMES[self.current_actual_state]}")
        print(f"Результат: {Fore.MAGENTA}{comparison}")

        self.display_today_schedule(current_time)
        self.display_daily_energy_summary(current_time.date())

        if not check_only:
            self.record_results(current_time, expected_state, self.current_actual_state, today_state, comparison)


    def __del__(self):
        if hasattr(self, 'db_connection'):
            self.db_connection.close()

def main():
    monitor = LocalBlackoutMonitor()
    
    def scheduled_check():
        try:
            monitor.check_and_record()
            log_next_run()
        except Exception as e:
            logger.error(f"Error during scheduled check: {str(e)}")

    def log_next_run():
        next_run = schedule.next_run()
        if next_run:
            logger.info(f"Next check scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.warning("No future checks scheduled. This shouldn't happen.")

    try:
        logger.info("Starting Electricity Status Monitor...")
        monitor.update_schedule()
        monitor.get_stable_outage_state()
        
        logger.info("Creating initial record...")
        monitor.check_and_record()
        
        for hour in range(24):
            schedule.every().day.at(f"{hour:02d}:30").do(scheduled_check)

        schedule.every().day.at(UPDATE_SCHEDULE_TIME).do(monitor.update_schedule)
        schedule.every().day.at(STABLE_OUTAGE_TIME_CHECK).do(monitor.get_stable_outage_state)
        schedule.every().day.at(STABLE_OUTAGE_TIME_2_CHECK).do(monitor.get_stable_outage_state)

        logger.info("Daily schedule update task has been set.")

        log_next_run()

        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.warning("Monitoring stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {str(e)}")
    finally:
        if monitor.driver:
            monitor.driver.quit()


if __name__ == "__main__":
    main()
