# City of Edmonton Database Construction

A Python application for constructing and populating a PostgreSQL database with traffic data from Miovision traffic monitoring systems. This project processes Miovision studies to extract directional traffic volumes, vehicle types, and granular traffic movement counts for the City of Edmonton.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Key Components](#key-components)

## Overview

This application automates the extraction and organization of traffic movement data from Miovision traffic counter Excel files. It:

- Reads traffic study data from Excel files
- Extracts directional traffic volumes (volumes by direction and movement type)
- Identifies and catalogs vehicle types from traffic counts
- Populates a PostgreSQL database with structured traffic data
- Maintains data integrity through transaction-based operations

**Data Sources:** Miovision traffic studies in Excel format (.xlsx)

**Target Database:** PostgreSQL

**Use Case:** Traffic analysis for the City of Edmonton, enabling traffic pattern analysis, vehicle classification, and movement tracking across multiple directions.

## Architecture

The application uses a **Provider Pattern** architecture with clear separation of concerns:

### Core Design Patterns

1. **Provider Pattern**: Specialized providers handle different aspects of data processing
   - `CoreDataProvider`: Base interface for data processing providers
   - Data extraction providers extract information from various sources
   - Type providers identify and manage categorical data (directions, movements, vehicles)

2. **Transaction Context**: Maintains state across multiple operations
   - Maps entities (directions, movements, vehicles) to database IDs
   - Enables hierarchical data insertion without requiring separate database queries

3. **Database Abstraction**: Protocol-based abstraction for database operations
   - `DatabaseConnection`: Interface for all database operations
   - `PostgresDatabaseConnection`: PostgreSQL implementation

### Data Flow

```
Excel Files (Miovision Studies)
         ↓
    [Validators]
         ↓
[Core Providers] → [Extractors] → [Database Writers]
         ↓
  Transaction Context (State Management)
         ↓
  PostgreSQL Database
```

## Project Structure

```
database_construction/
├── main.py                          # Application orchestrator
├── providers/                        # Core provider implementations
│   ├── __init__.py
│   ├── core_providers.py            # Data processing providers
│   ├── database_providers.py        # PostgreSQL connection and operations
│   ├── extraction_providers.py      # Data extraction from Excel/APIs
│   ├── tables_providers.py          # Database table definitions
│   └── types_providers.py           # Type and validation providers
├── tests/                           # Unit tests
│   ├── __init__.py
│   ├── test_database_provider.py
│   ├── test_in_out_volumes.py
│   ├── test_total_values.py
│   ├── test_volume_provider.py
│   ├── volume_provider.py           # Volume scraping implementation
│   └── database_provider.py
└── README.md                        # This file
```

## Database Schema

### Core Tables

#### **Studies** (`studies`)
Main table for traffic studies
- `miovision_id`: Study identifier from Miovision platform (Primary Key)
- `study_name`: Name/description of the study
- `study_duration`: Duration of the study in hours
- `study_type`: Type of study conducted
- `location_name`: Geographic location of the study
- `latitude`: Geographic latitude
- `longitude`: Geographic longitude
- `project_name`: Associated project name
- `study_date`: Date the study was conducted

#### **Studies Directions** (`studies_directions`)
Junction table linking studies to traffic directions
- `miovision_id`: References Studies table
- `direction_type_id`: References Direction Types table
- `study_direction_id`: Primary key

#### **Directions Movements** (`directions_movements`)
Junction table linking directions to traffic movements
- `study_direction_id`: References Studies Directions table
- `movement_type_id`: References Movement Types table
- `direction_movement_id`: Primary key

#### **Movement Vehicles** (`movement_vehicles`)
Junction table linking movements to vehicle types
- `direction_movement_id`: References Directions Movements table
- `vehicle_type_id`: References Vehicle Types table
- `movement_vehicle_id`: Primary key

#### **Granular Counts** (`granular_count`)
Detailed traffic counts
- `movement_vehicle_id`: References Movement Vehicles table
- Volume measurements and timestamp data

### Type Tables (Reference Data)

#### **Direction Types** (`direction_types`)
- `direction_type_name`: Cardinal directions (Northbound, Southbound, Eastbound, Westbound)

#### **Movement Types** (`movement_types`)
- `movement_type_name`: Types of traffic movements (Through, Right Turn, Left Turn, U-Turn, etc.)

#### **Vehicle Types** (`vehicle_types`)
- `vehicle_type_name`: Vehicle classifications (Car, Truck, Motorcycle, etc.)

### Table Hierarchy

```
Vehicle Types, Movement Types, Direction Types (Reference)
         ↓
    Studies → Studies Directions → Directions Movements → Movement Vehicles
                                                              ↓
                                                    Granular Counts
```

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

### Steps

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd database_construction
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   
   Using UV (recommended for faster dependency resolution):
   ```bash
   uv pip compile requirements.in -o requirements.out
   uv pip sync requirements.out
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# PostgreSQL connection string
LOCAL_DATABASE_URL=postgresql://username:password@localhost:5432/city_of_edmonton_traffic
```

### Application Configuration

The `ApplicationConfiguration` dataclass in `main.py` controls application behavior:

```python
ApplicationConfiguration(
    db_connection_string,              # PostgreSQL connection string (from env var)
    miovision_base_folder_name,        # Path to folder with Miovision Excel files
    vehicle_class_total_volume_sheet_name,  # Sheet name for vehicle classification
    validation_extension,              # Expected file extension (.xlsx)
    intitialize_tables,                # Create empty database tables
    intitialize_types                  # Populate reference type tables
)
```

**Default Configuration** (in `main.py`):
```python
app_configuration = ApplicationConfiguration(
    db_connection_string="LOCAL_DATABASE_URL",
    miovision_base_folder_name="Miovision 2025",
    vehicle_class_total_volume_sheet_name="Total Volume Class Breakdown",
    validation_extension=".xlsx",
    intitialize_tables=False,
    intitialize_types=False
)
```

## Usage

### Running the Application

```bash
python main.py
```

### Customizing the Run

Modify the configuration in `main.py` before running:

```python
# Enable database and type table initialization
app_configuration = ApplicationConfiguration(
    # ... other settings ...
    intitialize_tables=True,
    intitialize_types=True
)
```

### Application Flow

1. **Initialization Phase**:
   - Validates Miovision Excel files in the specified folder
   - Sets up database connection
   - Creates transaction context for state management

2. **Database Setup Phase** (if `intitialize_tables=True`):
   - Creates all required tables in PostgreSQL
   - Sets up table schemas and relationships

3. **Type Initialization Phase** (if `intitialize_types=True`):
   - Extracts and populates Direction Types from Excel sheet names
   - Extracts and populates Movement Types from Excel data
   - Extracts and populates Vehicle Types from classification sheet

4. **Data Population Phase**:
   - Processes each study in sequence using core providers:
     - **StudiesProvider**: Extracts and inserts study metadata
     - **StudiesDirectionsProvider**: Links studies to directions with volume data
     - **DirectionsMovementsProvider**: Maps movements to directions
     - **VehiclesAndGranularCountsProvider**: Associates vehicle types and detailed counts

### Core Providers

Each provider processes data in sequence:

1. **StudiesProvider**: Extracts study information from Excel file metadata
2. **StudiesDirectionsProvider**: Extracts directional traffic volumes
3. **DirectionsMovementsProvider**: Breaks down volumes by movement type
4. **VehiclesAndGranularCountsProvider**: Disaggregates by vehicle type (cars, trucks, etc.)

## Testing

### Running Tests

```bash
pytest tests/
```

### Running against the GCP database (Cloud SQL)

The tests connect to whatever `LOCAL_DATABASE_URL` points at. To run them
against the `coe-vista` Cloud SQL instance:

1. Start the Cloud SQL Auth Proxy (uses your `gcloud` login):

   ```bash
   cloud-sql-proxy --port 5433 coe-vista:northamerica-northeast2:city-edmonton-traffic-db
   ```

2. Put the following in `.env` (gitignored):

   ```
   LOCAL_DATABASE_URL=postgresql://pipeline_user:<password>@127.0.0.1:5433/miovision
   MIOVISION_USERNAME=<from Secret Manager: miovision-username>
   MIOVISION_PASSWORD=<from Secret Manager: miovision-password>
   MIOVISION_GCS_BUCKET=coe-vista-miovision-pipeline
   ```

3. Test Excel files are downloaded automatically from the bucket into
   `tests/fixtures/` (see `tests/fixture_files.py`; override the scraper run
   with `TEST_GCS_PREFIX`). The studies under that prefix must already be
   loaded into the database by the ETL.

The SQL functions the volume tests call (`get_in_volume`, `get_out_volume`,
`pedway_in/out_volume_calculation`) and the compass `directional_id` mapping
live in `sql/volume_functions.sql`. Re-apply that file after re-initializing
tables.

### Test Structure

- **`test_volume_provider.py`**: Tests for Miovision volume data extraction and web scraping
  - Authentication testing
  - HTML scraping validation
  - Volume data accuracy verification

- **`test_database_provider.py`**: Database connection and operations testing

- **`test_in_out_volumes.py`**: Validates directional volume calculations

- **`test_total_values.py`**: Verifies total volume calculations across directions

- **`volume_provider.py`**: Implementation of volume extraction from Miovision web interface
  - `HtmlVolumeProvider`: Scrapes volume data from Miovision DataLink
  - `HtmlAuthenticator`: Manages authentication with Miovision service
  - `LocalCredentialsProvider`: Loads credentials from local environment

## Key Components

### Providers Module (`providers/`)

#### `core_providers.py`
- **`TransactionContext`**: Maintains mappings between entity names and database IDs
- **`CoreDataProvider`**: Base protocol for all data providers
- **`StudiesProvider`**: Processes study-level data
- **`StudiesDirectionsProvider`**: Handles directional volume data
- **`DirectionsMovementsProvider`**: Maps movement data to directions
- **`VehiclesAndGranularCountsProvider`**: Processes vehicle-level granular counts
- **`CoreDataWriter`**: Coordinates multiple providers to write data to database

#### `database_providers.py`
- **`DatabaseConnection`**: Protocol defining database interface
- **`PostgresDatabaseConnection`**: PostgreSQL implementation
  - Connection management via context manager
  - SQL query execution
  - Data insertion and validation
  - Attribute existence checking
- **`DatabaseTableWriter`**: Creates database tables
- **`DatabaseTypesWriter`**: Populates reference type tables
- **`DatabaseUpdater`**: Updates existing records

#### `extraction_providers.py`
- **`StudiesExtractor`**: Extracts study metadata from Excel files
- **`DirectionsExtractor`**: Extracts directional data
- **`MovementsExtractor`**: Extracts movement classifications
- **`GranularExtractor`**: Extracts detailed count data
- **`StudiesFields`**: Data class for study information

#### `tables_providers.py`
- **`Table`**: Protocol for table definitions
- **`PredefinedTableNames`**: Enum of all table names
- **`PredefinedTableLabels`**: Enum of column labels
- Table column enums (StudiesTableColumns, StudiesDirectionsTableColumns, etc.)
- Concrete table implementations (StudiesTable, StudiesDirectionsTable, etc.)

#### `types_providers.py`
- **`BaseFolderValidator`**: Validates folder structure and file extensions
- **`DirectionsProvider`**: Extracts distinct direction types from Excel sheet names
- **`MovementsProvider`**: Extracts movement types from traffic data
- **`VehiclesProvider`**: Extracts vehicle classifications
- **`BaseTypeConfiguration`**: Configuration for type providers

### Validators

- **`BaseFolderValidator`**: Ensures all files in a directory have correct extension and valid structure

### Data Extraction

Data is extracted from:
- **Excel Files**: Miovision traffic study reports (.xlsx)
- **Web Scraping**: Miovision DataLink API (via `HtmlVolumeScraper`)
- **Metadata**: File names and sheet names contain study type and ID information

## Development Notes

### Code Style
- Type hints are used throughout for clarity
- Docstrings follow a structured format with Arguments, External Effects, and Returns sections
- Protocol-based interfaces enable flexibility and testability

### Error Handling
- Transaction context raises `ValueError` when required mappings are missing
- Database operations raise exceptions on constraint violations or missing tables
- Validation fails early with informative exception messages

### Design Considerations
- **Hierarchical Data**: The table structure enforces a hierarchy, requiring providers to run in sequence
- **State Management**: TransactionContext prevents redundant database queries during hierarchical insertion
- **Extensibility**: New provider types can be added by implementing the `CoreDataProvider` protocol
