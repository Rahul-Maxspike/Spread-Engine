# src/utils/path_config.py

import os


# Root directory
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
print(f"ROOT_DIR: {ROOT_DIR}")


# Base directory
BASE_DIR = os.path.join(ROOT_DIR, 'src')
print(f"BASE_DIR: {BASE_DIR}")

# Config paths
CONFIG_DIR = os.path.join(ROOT_DIR, 'config')
APPLICATION_CONFIG_PATH = os.path.join(CONFIG_DIR, 'application_config.ini')

# Data paths
DATA_DIR = os.path.join(ROOT_DIR, 'data')
MEMORY_FILES_DIR = ROOT_DIR

OPTIONS_PREMIUM_PATH = os.path.join(MEMORY_FILES_DIR, 'premium.csv')
OPTIONS_PREMIUM_AT_3PM_PATH = os.path.join(MEMORY_FILES_DIR, 'premiumAt3.csv')

PROCESSED_STOCK_DATA_PATH = os.path.join(MEMORY_FILES_DIR, 'processed_stock_data.json')
TRADE_EXECUTION_LOG_PATH = os.path.join(MEMORY_FILES_DIR, 'trade_execution_log.json')
IN_MEMORY_TRADE_SHEET_PATH = os.path.join(MEMORY_FILES_DIR, 'in_memory_trade_sheet.csv')

# Log paths
LOGS_DIR = os.path.join(ROOT_DIR, 'logs')
APPLICATION_LOG_PATH = os.path.join(LOGS_DIR, 'application.log')

# Scripts paths
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
START_SCRIPT_PATH = os.path.join(SCRIPTS_DIR, 'start_application.sh')
STOP_SCRIPT_PATH = os.path.join(SCRIPTS_DIR, 'stop_application.sh')
