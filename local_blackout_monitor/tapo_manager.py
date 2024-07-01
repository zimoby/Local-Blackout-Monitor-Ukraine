import asyncio
from datetime import datetime
import logging
import json
from tapo import ApiClient
from tapo.requests import EnergyDataInterval
from config import TAPO_USERNAME, TAPO_PASSWORD, UPS_INFO

logger = logging.getLogger(__name__)

class TapoManager:
    def __init__(self):
        self.client = ApiClient(TAPO_USERNAME, TAPO_PASSWORD)

    async def get_energy_data(self):
        energy_data = {}
        for ups in UPS_INFO:
            ups_data = {
                "battery_Ah": ups["battery_Ah"],
                "smart_plugs": {}
            }
            for plug in ups["smart_plugs"]:
                try:
                    if not plug['ip']:
                        logger.error(f"IP address is None for plug: {plug}")
                        continue
                    device = await self.client.__getattribute__(plug['type'])(plug['ip'])
                    today = datetime.today()
                    energy_data_hourly = await device.get_energy_data(EnergyDataInterval.Hourly, today)
                    ups_data["smart_plugs"][plug['ip']] = energy_data_hourly.to_dict()
                    # logger.info(f"Collected energy data for plug {plug['ip']}: {json.dumps(energy_data_hourly.to_dict(), indent=2)}")
                except Exception as e:
                    logger.error(f"Error getting energy data for plug {plug['ip']}: {str(e)}")
                    ups_data["smart_plugs"][plug['ip']] = {"error": str(e)}
            energy_data[f"UPS_{UPS_INFO.index(ups)}"] = ups_data
        # logger.info(f"Collected energy data: {json.dumps(energy_data, indent=2)}")
        return energy_data

async def get_tapo_energy_data():
    try:
        manager = TapoManager()
        return await manager.get_energy_data()
    except Exception as e:
        logger.error(f"Error in get_tapo_energy_data: {str(e)}")
        return {}