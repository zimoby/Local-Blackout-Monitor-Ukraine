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

init(autoreset=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LocalBlackoutMonitor:
    def __init__(self):
        self.schedule = {}
        self.todays_limits = {"start": "none", "end": "none"}
        self.driver = self.setup_driver()
        self.current_actual_state = None

