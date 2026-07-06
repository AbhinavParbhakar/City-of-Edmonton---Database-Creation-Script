import os
import io
import csv
from datetime import date
from typing import Literal

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

load_dotenv()

app = FastAPI()

COLUMNS = [
    "miovision_id", "study_name", "study_duration", "study_type",
    "location_name", "latitude", "longitude", "project_name", "study_date",
    "direction_name", "in_volume", "out_volume", "volume",
]

# Two-level CTE:
#   base    - joins studies + directions, flags pedway rows (study_type ILIKE '%way%')
#   volumes - calls the roadway volume functions once per row; CASE guard ensures
#             the missing pedway siblings are never called (returns NULL instead)
# %% escapes the literal % signs needed by ILIKE inside a psycopg2 parameterised query.
QUERY = """
WITH base AS (
    SELECT s.miovision_id, s.study_name, s.study_duration, s.study_type,
           s.location_name, s.latitude, s.longitude, s.project_name, s.study_date,
           dt.direction_type_name AS direction_name,
           dt.directional_id,
           s.study_type ILIKE '%%way%%' AS is_pedway
    FROM studies s
    JOIN studies_directions sd ON s.miovision_id = sd.miovision_id
    JOIN direction_types dt ON dt.id = sd.direction_type_id
    WHERE s.study_date >= %s AND s.study_date <= %s
), volumes AS (
    SELECT *,
           CASE WHEN is_pedway THEN NULL
                ELSE get_in_volume(miovision_id, directional_id) END AS in_volume,
           CASE WHEN is_pedway THEN NULL
                ELSE get_out_volume(miovision_id, directional_id) END AS out_volume
    FROM base
)
SELECT miovision_id, study_name, study_duration, study_type,
       location_name, latitude, longitude, project_name, study_date,
       direction_name, in_volume, out_volume,
       CASE WHEN in_volume IS NULL THEN NULL
            ELSE in_volume + out_volume END AS volume
FROM volumes
ORDER BY study_date, miovision_id, direction_name;
"""


def _connect():
    conn_str = os.environ.get("LOCAL_DATABASE_URL")
    if not conn_str:
        raise HTTPException(status_code=500, detail="LOCAL_DATABASE_URL not set")
    return psycopg2.connect(conn_str)


@app.get("/api/v1/get_studies")
def get_studies(
    start_date: date = Query(...),
    end_date: date = Query(...),
    file_type: Literal["json", "csv"] = Query("json"),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(QUERY, (start_date, end_date))
        rows = cur.fetchall()
    finally:
        conn.close()

    if file_type == "json":
        result = []
        for row in rows:
            d = dict(zip(COLUMNS, row))
            d["study_date"] = d["study_date"].isoformat() if d["study_date"] else None
            for k in ("study_duration", "latitude", "longitude"):
                if d[k] is not None:
                    d[k] = float(d[k])
            result.append(d)
        return JSONResponse(content=result)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for row in rows:
        w.writerow([r.isoformat() if isinstance(r, date) else r for r in row])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=studies.csv"},
    )
