-- Database objects the ETL does not create but the tests and api/ depend on.
-- Apply after any INITIALIZE_TABLES=true run (and re-apply after INITIALIZE_TYPES
-- introduces new direction rows): psql "$LOCAL_DATABASE_URL" -f sql/volume_functions.sql
--
-- directional_id follows Miovision's data-direction attribute (see
-- HtmlVolumeProvider in tests/volume_provider.py): compass order in 45-degree
-- steps, so opposite direction = +4 (mod 8, over the 1..8 range).
-- get_out_volume's offset arithmetic is only correct with these exact values.

ALTER TABLE direction_types ADD COLUMN IF NOT EXISTS directional_id INTEGER;

-- Seed all 8 compass directions so rows discovered later by the ETL's type
-- writer already exist with a correct directional_id instead of NULL.
INSERT INTO direction_types (direction_type_name)
SELECT v.name
FROM (VALUES
    ('Southbound'), ('Southwestbound'), ('Westbound'), ('Northwestbound'),
    ('Northbound'), ('Northeastbound'), ('Eastbound'), ('Southeastbound')
) AS v(name)
WHERE NOT EXISTS (
    SELECT 1 FROM direction_types dt WHERE dt.direction_type_name = v.name
);

UPDATE direction_types dt
SET directional_id = v.directional_id
FROM (VALUES
    ('Southbound', 1),
    ('Southwestbound', 2),
    ('Westbound', 3),
    ('Northwestbound', 4),
    ('Northbound', 5),
    ('Northeastbound', 6),
    ('Eastbound', 7),
    ('Southeastbound', 8)
) AS v(direction_type_name, directional_id)
WHERE dt.direction_type_name = v.direction_type_name;

-- Supports the existence check update_db() runs before every granular_count
-- insert; without it each check is a sequential scan of the whole table.
CREATE INDEX IF NOT EXISTS idx_granular_count_dedup
    ON granular_count (movement_vehicle_id, time_stamp, traffic_count);

-- Volume entering the intersection from the leg where <directional_id>-bound
-- traffic arrives: every vehicle movement made from that approach.
CREATE OR REPLACE FUNCTION public.get_in_volume(miovision_id integer, directional_id integer)
RETURNS integer
LANGUAGE sql
AS $function$
    SELECT COALESCE(SUM(counts.traffic_count), 0)
    FROM studies s
    JOIN studies_directions sd ON s.miovision_id = sd.miovision_id
    JOIN direction_types dt ON dt.id = sd.direction_type_id
    JOIN directions_movements dm ON sd.id = dm.study_direction_id
    JOIN movement_types mt ON mt.id = dm.movement_type_id
    JOIN movements_vehicles mv ON dm.id = mv.direction_movement_id
    JOIN granular_count counts ON mv.id = counts.movement_vehicle_id
    WHERE
        s.miovision_id = get_in_volume.miovision_id
        AND dt.directional_id = get_in_volume.directional_id
        AND mt.movement_type_name IN ('U-Turn','Hard right','Right','Bear right','Thru','Bear left','Left','Hard left')
$function$;

-- Volume exiting through that same leg: contributed by other approaches whose
-- movement lands there (Thru from the opposite direction, Left/Right from the
-- cross streets, ...). Offsets are +45-degree steps; the (x - 1) % 8 + 1 form
-- keeps results in the 1..8 range (a plain (x + k) % 8 can never equal 8, which
-- silently dropped every Southeastbound contribution).
CREATE OR REPLACE FUNCTION public.get_out_volume(miovision_id integer, directional_id integer)
RETURNS integer
LANGUAGE sql
AS $function$
    WITH aggregate_volumes AS (
        SELECT dt.directional_id AS directional_id,
               mt.movement_type_name AS movement_name,
               SUM(counts.traffic_count) AS vehicle_count
        FROM studies s
        JOIN studies_directions sd ON s.miovision_id = sd.miovision_id
        JOIN direction_types dt ON dt.id = sd.direction_type_id
        JOIN directions_movements dm ON sd.id = dm.study_direction_id
        JOIN movement_types mt ON mt.id = dm.movement_type_id
        JOIN movements_vehicles mv ON dm.id = mv.direction_movement_id
        JOIN granular_count counts ON mv.id = counts.movement_vehicle_id
        WHERE s.miovision_id = get_out_volume.miovision_id
        GROUP BY dt.directional_id, mt.movement_type_name
    )
    SELECT COALESCE(SUM(
        CASE
            WHEN directional_id = get_out_volume.directional_id AND movement_name = 'U-Turn' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 0) % 8 + 1 AND movement_name = 'Hard right' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 1) % 8 + 1 AND movement_name = 'Right' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 2) % 8 + 1 AND movement_name = 'Bear right' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 3) % 8 + 1 AND movement_name = 'Thru' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 4) % 8 + 1 AND movement_name = 'Bear left' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 5) % 8 + 1 AND movement_name = 'Left' THEN vehicle_count
            WHEN directional_id = (get_out_volume.directional_id + 6) % 8 + 1 AND movement_name = 'Hard left' THEN vehicle_count
            ELSE 0
        END
    ), 0)
    FROM aggregate_volumes
$function$;

-- Pedway (crosswalk/shared-use path) studies have exactly two opposing
-- directions and a single Thru movement. Volume "in" for a direction is its
-- own count; "out" is the opposing direction's count.
CREATE OR REPLACE FUNCTION public.pedway_in_volume_calculation(miovision_id integer, directional_id integer)
RETURNS integer
LANGUAGE sql
AS $function$
    SELECT COALESCE(SUM(counts.traffic_count), 0)
    FROM studies s
    JOIN studies_directions sd ON s.miovision_id = sd.miovision_id
    JOIN direction_types dt ON dt.id = sd.direction_type_id
    JOIN directions_movements dm ON sd.id = dm.study_direction_id
    JOIN movements_vehicles mv ON dm.id = mv.direction_movement_id
    JOIN granular_count counts ON mv.id = counts.movement_vehicle_id
    WHERE
        s.miovision_id = pedway_in_volume_calculation.miovision_id
        AND dt.directional_id = pedway_in_volume_calculation.directional_id
$function$;

CREATE OR REPLACE FUNCTION public.pedway_out_volume_calculation(miovision_id integer, directional_id integer)
RETURNS integer
LANGUAGE sql
AS $function$
    SELECT COALESCE(SUM(counts.traffic_count), 0)
    FROM studies s
    JOIN studies_directions sd ON s.miovision_id = sd.miovision_id
    JOIN direction_types dt ON dt.id = sd.direction_type_id
    JOIN directions_movements dm ON sd.id = dm.study_direction_id
    JOIN movements_vehicles mv ON dm.id = mv.direction_movement_id
    JOIN granular_count counts ON mv.id = counts.movement_vehicle_id
    WHERE
        s.miovision_id = pedway_out_volume_calculation.miovision_id
        -- opposite direction, kept in the 1..8 range
        AND dt.directional_id = (pedway_out_volume_calculation.directional_id + 3) % 8 + 1
$function$;
