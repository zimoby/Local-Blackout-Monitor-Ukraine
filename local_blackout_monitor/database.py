import sqlite3
import os
from datetime import datetime
from colorama import Fore
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'electricity_data.db')
        self.conn = self.setup_database()

    def setup_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS energy_consumption (
                    timestamp TEXT,
                    ups_id TEXT,
                    battery_Ah REAL,
                    smart_plug_ip TEXT,
                    hourly_data TEXT,
                    PRIMARY KEY (timestamp, ups_id, smart_plug_ip)
                )
            ''')
            conn.commit()
            logger.info("Database setup successful")
            return conn
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            return None

    def record_results(self, current_time, expected_state, actual_state, today_state, comparison):
        if not self.conn:
            logger.error("Database connection not established")
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO electricity_status
                (timestamp, expected_state, actual_state, today_state, comparison)
                VALUES (?, ?, ?, ?, ?)
            ''', (current_time.strftime("%Y-%m-%d %H:%M:%S"), expected_state, actual_state, today_state, comparison))
            self.conn.commit()
            logger.info("Results recorded successfully")
        except Exception as e:
            logger.error(f"Error recording results: {e}")

    def get_daily_energy_summary(self, date=None):
        if not self.conn:
            logger.error("Database connection not established")
            return {"on_hours": 0, "off_hours": 0, "unknown_hours": 0}

        if date is None:
            date = datetime.now().date()
        
        try:
            cursor = self.conn.cursor()
            
            # Get the last record for each hour of the day
            cursor.execute('''
                WITH hourly_data AS (
                    SELECT 
                        strftime('%H', timestamp) as hour,
                        actual_state,
                        ROW_NUMBER() OVER (PARTITION BY strftime('%H', timestamp) ORDER BY timestamp DESC) as rn
                    FROM electricity_status
                    WHERE DATE(timestamp) = ?
                )
                SELECT hour, actual_state
                FROM hourly_data
                WHERE rn = 1
                ORDER BY hour
            ''', (date.strftime("%Y-%m-%d"),))
            
            results = cursor.fetchall()
            
            on_hours = 0
            off_hours = 0
            unknown_hours = 0
            
            hours_set = set(r[0] for r in results)
            for hour in range(24):
                hour_str = f"{hour:02d}"
                if hour_str in hours_set:
                    state = next(r[1] for r in results if r[0] == hour_str)
                    if state == 0:
                        on_hours += 1
                    elif state == 2:
                        off_hours += 1
                    else:
                        unknown_hours += 1
                else:
                    unknown_hours += 1
            
            return {
                "on_hours": on_hours,
                "off_hours": off_hours,
                "unknown_hours": unknown_hours
            }
        except Exception as e:
            logger.error(f"Error getting daily energy summary: {e}")
            return {"on_hours": 0, "off_hours": 0, "unknown_hours": 0}
        
    def record_energy_consumption(self, timestamp, energy_data):
        if not self.conn:
            logger.error("Database connection not established")
            return

        try:
            cursor = self.conn.cursor()
            # logger.info(f"Received energy data: {json.dumps(energy_data, indent=2)}")
            for ups_id, ups_data in energy_data.items():
                battery_Ah = ups_data["battery_Ah"]
                for smart_plug_ip, plug_data in ups_data["smart_plugs"].items():
                    logger.info(f"Inserting data for UPS {ups_id}, plug {smart_plug_ip}")
                    cursor.execute('''
                        INSERT OR REPLACE INTO energy_consumption
                        (timestamp, ups_id, battery_Ah, smart_plug_ip, hourly_data)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (timestamp.strftime("%Y-%m-%d %H:%M:%S"), ups_id, battery_Ah, smart_plug_ip, json.dumps(plug_data)))
            self.conn.commit()
            logger.info("Energy consumption data recorded successfully")
            
            # Verify the inserted data
            cursor.execute('''
                SELECT * FROM energy_consumption
                WHERE timestamp = ?
            ''', (timestamp.strftime("%Y-%m-%d %H:%M:%S"),))
            inserted_data = cursor.fetchall()
            # logger.info(f"Verified inserted data: {inserted_data}")
        except Exception as e:
            logger.error(f"Error recording energy consumption data: {e}")

    def get_hourly_energy_consumption(self, date=None):
        if not self.conn:
            logger.error("Database connection not established")
            return {}

        if date is None:
            date = datetime.now().date()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT ups_id, smart_plug_ip, hourly_data, timestamp
                FROM energy_consumption
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp DESC
            ''', (date.strftime("%Y-%m-%d"),))
            
            results = cursor.fetchall()
            hourly_consumption = defaultdict(lambda: defaultdict(dict))
            
            for ups_id, smart_plug_ip, hourly_data, timestamp in results:
                data = json.loads(hourly_data)
                for hour, consumption in enumerate(data.get('data', [])):
                    if smart_plug_ip not in hourly_consumption[hour][ups_id]:
                        hourly_consumption[hour][ups_id][smart_plug_ip] = consumption

            # Sum up the consumption for each UPS
            final_consumption = defaultdict(dict)
            for hour in hourly_consumption:
                for ups_id in hourly_consumption[hour]:
                    final_consumption[hour][ups_id] = sum(hourly_consumption[hour][ups_id].values())
            
            return dict(final_consumption)
        except Exception as e:
            logger.error(f"Error getting hourly energy consumption: {e}")
            return {}

    def get_actual_states(self, date=None):
        if not self.conn:
            logger.error("Database connection not established")
            return {}

        if date is None:
            date = datetime.now().date()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT strftime('%H', timestamp) as hour, actual_state
                FROM electricity_status
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp DESC
            ''', (date.strftime("%Y-%m-%d"),))
            
            results = cursor.fetchall()
            actual_states = {}
            
            for hour, state in results:
                hour = int(hour)
                if hour not in actual_states:
                    actual_states[hour] = state
            
            return actual_states
        except Exception as e:
            logger.error(f"Error getting actual states: {e}")
            return {}


    def display_daily_energy_summary(self, date=None):
        summary = self.get_daily_energy_summary(date)
        
        print("\nЩоденний підсумок енергопостачання:")
        print(f"{Fore.GREEN}Електроенергія увімкнена: {summary['on_hours']} годин")
        print(f"{Fore.RED}Електроенергія вимкнена: {summary['off_hours']} годин")
        print(f"{Fore.YELLOW}Невідомий стан: {summary['unknown_hours']} годин")

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info("Database connection closed")
