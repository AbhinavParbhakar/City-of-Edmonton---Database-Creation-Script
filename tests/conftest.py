from dotenv import load_dotenv

# Tests read LOCAL_DATABASE_URL, MIOVISION_USERNAME/PASSWORD and the GCS
# settings from the environment. Load .env before any module-level
# parametrization (excel_files()) runs at collection time.
load_dotenv()
