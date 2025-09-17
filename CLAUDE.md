# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Build and Run
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database and load indicators
python main.py init

# Run different types of data updates
python main.py update                        # Smart incremental update (default - recommended)
python main.py update --update-type smart    # Smart update: new indicators get full data, existing get incremental
python main.py update --update-type incremental  # Traditional incremental update
python main.py update --update-type full     # Full historical data (2000-present)
python main.py update --update-type retry    # Retry failed indicators only

# Start API server (port 8000)
python main.py server

# Start scheduler for automated updates
python main.py scheduler

# Check system status
python main.py status
```

### Testing and Data Validation
```bash
# Check data coverage and completeness
python check_data_coverage_v2.py

# Check migration status
python check_migration_status.py

# Update all indicators to latest (testing utility)
python update_all_indicators_to_latest.py

# Show field analysis and multi-field indicators
python main.py fields
```

### Database Operations
```bash
# Direct SQLite access
sqlite3 data/financial_data.db

# Check database status
python -c "from src.database.models import DatabaseManager; db = DatabaseManager(); print('Database OK')"
```

## Architecture Overview

This is a Chinese financial data management system for multi-asset investment portfolios, built with:

- **Data Sources**: Wind API (WSD for market data, EDB for economic data) via WindPy library
- **Database**: SQLite with 3 main tables - indicators, time_series_data, update_logs
- **API Layer**: FastAPI REST server with batch data endpoints
- **Scheduler**: Automated daily/weekly data updates using Python schedule library
- **Configuration**: 380 financial indicators across 10 categories (bonds 67.9%, macro 8.7%, equity 8.4%)

### Key Components

**src/database/models_v2.py**: Core DatabaseManager class handling SQLite operations, indicator loading from Excel, multi-field support, time series data management

**src/data_fetcher/wind_client_v2.py**: WindDataFetcher class for Wind API integration using WindPy direct connection with MCP fallback

**src/scheduler/data_updater_v2.py**: DataUpdater class managing smart incremental updates, multi-field indicators, and intelligent retry logic

**src/api/main.py**: FastAPI application with endpoints for indicator queries, time series data retrieval, and batch operations

**config/config.py**: Centralized settings using Pydantic including Wind MCP configuration, database paths, API settings, and scheduler timing

### Data Flow
1. Indicators loaded from `data/数据指标.xlsx` (380 indicators with Wind codes and multi-field mappings)
2. Smart update logic: new indicators get full historical data (2000-present), existing indicators get incremental updates
3. Wind API data fetched based on wind_field (empty = EDB economic data, populated = WSD market data)
4. Multi-field indicators stored with separate field mappings in indicator_fields table
5. Data stored in time_series_data table with wind_code + field_name + date uniqueness
6. REST API serves data with optional date filtering and batch retrieval
7. Scheduler runs daily incremental updates (18:00) and weekly full updates (02:00)

### Current Data Status
- 202/380 indicators successfully retrieved (53.2% completion)
- 178 indicators available for retry due to API limitations or temporary failures
- Database size: ~112MB with historical data from 2000-present
- Retry mechanism specifically targets failed/missing indicators to avoid redundant downloads

## Wind API Requirements

This system requires:
- Wind Terminal client installation and login
- WindPy library: `pip install WindPy`
- Valid Wind API subscription and permissions
- Wind MCP server running on localhost:8889 (configurable in config.py)

The system uses direct WindPy connection rather than MCP to avoid token consumption overhead.

## Key Files for Debugging

- `logs/main.log` - Main application logs
- `logs/wind_data_fetcher.log` - Wind API interaction logs  
- `data_coverage_report_v2.csv` - Data completeness analysis
- `insufficient_data_indicators.csv` - Failed indicators list
- `DATABASE_SCHEMA.md` - Detailed database structure
- `DATA_RETRY_GUIDE.md` - Retry strategy documentation