import logging
from local_blackout_monitor.monitor import LocalBlackoutMonitor
from local_blackout_monitor.scheduler import setup_schedule
from config import LOG_LEVEL

def main():
    logging.basicConfig(level=LOG_LEVEL, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        filename='blackout_monitor.log')
    
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    try:
        monitor = LocalBlackoutMonitor()
        setup_schedule(monitor)
    except Exception as e:
        logging.error(f"Error in main: {e}")


if __name__ == "__main__":
    main()