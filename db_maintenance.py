import argparse
import logging
from local_blackout_monitor.database import DatabaseManager
import sqlite3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_row_count(db_manager, table_name):
    cursor = db_manager.conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]

def cleanup_database(days_to_keep, vacuum=False):
    db_manager = DatabaseManager()
    
    # Get row count before cleanup
    before_count = get_row_count(db_manager, 'energy_consumption')
    
    db_manager.cleanup_duplicates(days_to_keep)
    
    # Get row count after cleanup
    after_count = get_row_count(db_manager, 'energy_consumption')
    
    rows_removed = before_count - after_count
    logger.info(f"Database cleanup completed for the last {days_to_keep} days.")
    logger.info(f"Rows before cleanup: {before_count}")
    logger.info(f"Rows after cleanup: {after_count}")
    logger.info(f"Rows removed: {rows_removed}")
    
    if vacuum:
        logger.info("Performing VACUUM operation...")
        db_manager.conn.execute("VACUUM")
        logger.info("VACUUM operation completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database maintenance for Local Blackout Monitor")
    parser.add_argument("--cleanup", type=int, help="Clean up duplicates, keeping data for the specified number of days")
    parser.add_argument("--vacuum", action="store_true", help="Perform VACUUM operation after cleanup to optimize database size")
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_database(args.cleanup, args.vacuum)
    else:
        parser.print_help()