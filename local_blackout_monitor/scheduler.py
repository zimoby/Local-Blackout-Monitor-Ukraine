import schedule
import time
from config import STATE_COLORS, STATE_NAMES, UPDATE_SCHEDULE_TIME, STABLE_OUTAGE_TIME_CHECK, STABLE_OUTAGE_TIME_2_CHECK, GROUP_NUMBER, SCHEDULE_FILE
from colorama import Fore, Back, Style
import json
import logging

logger = logging.getLogger(__name__)


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
            state_color = STATE_COLORS[state] if self.time_in_range(
                hour) else STATE_COLORS[-1]

        current_hour = f"({STATE_COLORS[self.current_actual_state]}{STATE_NAMES[self.current_actual_state]}{Style.RESET_ALL})" if hour == current_time.hour else ""
        print(
            f"{time_style}{hour:02d}:00 {limit_indicator} {state_color}{STATE_NAMES[state]}{Style.RESET_ALL} {current_hour}")

    print("\nПерші 5 годин наступного дня:")
    for hour, state in enumerate(next_day_schedule[:5]):
        print(
            f"{hour:02d}:00 {STATE_COLORS[state]}{STATE_NAMES[state]}{Style.RESET_ALL}")


def update_schedule(self):
    try:
        with open(SCHEDULE_FILE, 'r') as file:
            schedule_data = json.load(file)
            self.schedule = {
                int(k): v for k, v in schedule_data[str(GROUP_NUMBER)].items()}
        logger.info("Schedule updated successfully for the new day.")
    except Exception as e:
        logger.error(f"Failed to update schedule: {e}")

def setup_schedule(monitor):
    def scheduled_check():
        try:
            monitor.check_and_record()
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
