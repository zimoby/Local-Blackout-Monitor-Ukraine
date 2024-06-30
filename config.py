import os
from dotenv import load_dotenv

load_dotenv()

GROUP_NUMBER = os.getenv('GROUP_NUMBER')
URL_HOUSE_STATE = os.getenv('URL_HOUSE_STATE')
DTEK_URL = os.getenv('DTEK_URL')
UPTIMEROBOT_API_KEY = os.getenv('UPTIMEROBOT_API_KEY')
CHECK_DTEK = True
CHECK_INTERVAL = 60  # minutes
SCHEDULE_FILE = 'schedule.json'
STABLE_OUTAGE_TIME_CHECK = "00:15"
STABLE_OUTAGE_TIME_2_CHECK = "12:15"
UPDATE_SCHEDULE_TIME = "00:20"
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

STATE_COLORS = {
    -1: "\033[90m",  # LIGHTBLACK_EX
    0: "\033[92m",   # GREEN
    1: "\033[93m",   # YELLOW
    2: "\033[91m"    # RED
}

STATE_NAMES = {
    0: "Світло є",
    1: "Можливо відключення",
    2: "Світла немає"
}