from datetime import datetime
from .database import DatabaseManager
from .scraper import Scraper
from .utils import get_expected_state, compare_states, display_today_schedule
from config import STATE_COLORS, STATE_NAMES, SCHEDULE_FILE, GROUP_NUMBER
import json
from colorama import Fore
import logging

logger = logging.getLogger(__name__)

class LocalBlackoutMonitor:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.scraper = Scraper()
        self.schedule = {}
        self.todays_limits = {"start": "none", "end": "none"}
        self.current_actual_state = None

    def update_schedule(self):
        try:
            with open(SCHEDULE_FILE, 'r') as file:
                schedule_data = json.load(file)
                self.schedule = {int(k): v for k, v in schedule_data[str(GROUP_NUMBER)].items()}
            logger.info("Schedule updated successfully for the new day.")
        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")

    def get_stable_outage_state(self):
        self.todays_limits = self.scraper.get_stable_outage_state()
        logger.info(f"Updated today's limits: {self.todays_limits}")

    def check_and_record(self, check_only=False):
        current_time = datetime.now()
        hours = current_time.hour
        logging.info(f"Checking at {current_time}")
        expected_state = get_expected_state(self.schedule, current_time)
        self.current_actual_state = self.scraper.get_actual_state()
        logger.info(f"Очікувано: {expected_state}, Фактично: {self.current_actual_state}")
        today_state = int(self.scraper.time_in_range(hours, self.todays_limits))
        comparison = compare_states(expected_state, self.current_actual_state, today_state)
        
        print(f"\n{Fore.CYAN}Час: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Очікувано: {STATE_COLORS[expected_state]}{STATE_NAMES[expected_state]}")
        print(f"Фактично: {STATE_COLORS[self.current_actual_state]}{STATE_NAMES[self.current_actual_state]}")
        print(f"Результат: {Fore.MAGENTA}{comparison}")

        display_today_schedule(self.schedule, current_time, self.current_actual_state, 
                               lambda hour: self.scraper.time_in_range(hour, self.todays_limits))
        self.db_manager.display_daily_energy_summary(current_time.date())

        if not check_only:
            self.db_manager.record_results(current_time, expected_state, self.current_actual_state, today_state, comparison)

    def __del__(self):
        if hasattr(self, 'scraper'):
            self.scraper.__del__()