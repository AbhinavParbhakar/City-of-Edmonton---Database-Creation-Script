from typing import Protocol, Any
from itertools import groupby
from .types_providers import BaseFolderValidator
from .tables_providers import PredefinedTableNames, StudiesTableColumns, StudiesDirectionsTableColumns, PredefinedTableLabels, MovementsDirectionsTableColumns
from .tables_providers import GranularCountsTableColumns, MovementVehiclesTableColumns
from .database_providers import DatabaseConnection, DatabaseUpdater
from .extraction_providers import StudiesExtractor, DirectionsExtractor, MovementsExtractor, GranularExtractor, MiovisionExtractor
import tqdm
import logging

logger = logging.getLogger(__name__)


class DatabaseIdResolver:
    """Resolves entity names to database ids with direct queries.

    Stateless: every call reads the database, so providers can run (or
    resume) independently without sharing in-process state.
    """
    def __init__(self, db_connection : DatabaseConnection) -> None:
        self._db_connection = db_connection

    def _get_single_value(self, table_name : str, query_attr : str, labels : list[str], values : list[Any])->Any:
        query_result = self._db_connection.select_existing_attributes(
            table_name=table_name,
            query_attr=[query_attr],
            where_labels=labels,
            where_values=values
        )
        if len(query_result) != 1:
            raise Exception(f"Non-singular result ({len(query_result)} rows) returned when querying {query_attr} of {table_name} for {labels}={values}")

        return query_result[0][0]

    def _get_single_id(self, table_name : str, labels : list[str], values : list[Any])->int:
        return self._get_single_value(table_name=table_name, query_attr='id', labels=labels, values=values)

    def get_direction_type_id(self, direction_name : str)->int:
        return self._get_single_id(
            table_name=PredefinedTableNames.direction_types.value,
            labels=[PredefinedTableLabels.direction_types.value],
            values=[direction_name]
        )

    def get_movement_type_id(self, movement_name : str)->int:
        return self._get_single_id(
            table_name=PredefinedTableNames.movement_types.value,
            labels=[PredefinedTableLabels.movement_types.value],
            values=[movement_name]
        )

    def get_vehicle_type_id(self, vehicle_name : str)->int:
        return self._get_single_id(
            table_name=PredefinedTableNames.vehicles_types.value,
            labels=[PredefinedTableLabels.vehicles_types.value],
            values=[vehicle_name]
        )

    def get_study_direction_id(self, miovision_id : int, direction_name : str)->int:
        return self._get_single_id(
            table_name=PredefinedTableNames.studies_directions.value,
            labels=[
                StudiesDirectionsTableColumns.miovision_id.value,
                StudiesDirectionsTableColumns.direction_type_id.value
            ],
            values=[
                miovision_id,
                self.get_direction_type_id(direction_name)
            ]
        )

    def get_direction_movement_id(self, miovision_id : int, direction_name : str, movement_name : str)->int:
        return self._get_single_id(
            table_name=PredefinedTableNames.directions_movements.value,
            labels=[
                MovementsDirectionsTableColumns.study_direction_id.value,
                MovementsDirectionsTableColumns.movement_type_id.value
            ],
            values=[
                self.get_study_direction_id(miovision_id, direction_name),
                self.get_movement_type_id(movement_name)
            ]
        )

    def get_direction_names_for_study(self, miovision_id : int)->list[str]:
        query_result = self._db_connection.select_existing_attributes(
            table_name=PredefinedTableNames.studies_directions.value,
            query_attr=[StudiesDirectionsTableColumns.direction_type_id.value],
            where_labels=[StudiesDirectionsTableColumns.miovision_id.value],
            where_values=[miovision_id]
        )
        if len(query_result) == 0:
            raise Exception(f"No directions recorded in {PredefinedTableNames.studies_directions.value} for study {miovision_id}")

        return [
            self._get_single_value(
                table_name=PredefinedTableNames.direction_types.value,
                query_attr=PredefinedTableLabels.direction_types.value,
                labels=['id'],
                values=[direction_type_id]
            )
            for (direction_type_id,) in query_result
        ]

    def get_movement_names_for_study(self, miovision_id : int)->list[str]:
        study_direction_rows = self._db_connection.select_existing_attributes(
            table_name=PredefinedTableNames.studies_directions.value,
            query_attr=['id'],
            where_labels=[StudiesDirectionsTableColumns.miovision_id.value],
            where_values=[miovision_id]
        )
        if len(study_direction_rows) == 0:
            raise Exception(f"No directions recorded in {PredefinedTableNames.studies_directions.value} for study {miovision_id}")

        movement_type_ids : list[int] = []
        for (study_direction_id,) in study_direction_rows:
            movement_rows = self._db_connection.select_existing_attributes(
                table_name=PredefinedTableNames.directions_movements.value,
                query_attr=[MovementsDirectionsTableColumns.movement_type_id.value],
                where_labels=[MovementsDirectionsTableColumns.study_direction_id.value],
                where_values=[study_direction_id]
            )
            for (movement_type_id,) in movement_rows:
                if movement_type_id not in movement_type_ids:
                    movement_type_ids.append(movement_type_id)

        if len(movement_type_ids) == 0:
            raise Exception(f"No movements recorded in {PredefinedTableNames.directions_movements.value} for study {miovision_id}")

        return [
            self._get_single_value(
                table_name=PredefinedTableNames.movement_types.value,
                query_attr=PredefinedTableLabels.movement_types.value,
                labels=['id'],
                values=[movement_type_id]
            )
            for movement_type_id in movement_type_ids
        ]

    def get_all_vehicle_names(self)->list[str]:
        query_result = self._db_connection.select_existing_attributes(
            table_name=PredefinedTableNames.vehicles_types.value,
            query_attr=[PredefinedTableLabels.vehicles_types.value]
        )

        if len(query_result) == 0:
            raise RuntimeError("No Vehicles returned from get_all_vehicle_names() inside of DatabaseIdResolver")

        return [query[0] for query in query_result]

class CoreDataProvider(Protocol):
    def write_data(self)->None:...
    """
    Write data into database
    """

class CoreDataWriter:
    def __init__(self, core_providers:list[CoreDataProvider]) -> None:
        self._providers = core_providers

    def write_data(self)->None:
        for provider in self._providers:
            provider.write_data()

class StudiesDirectionsProvider:
    def __init__(self, base_validator: BaseFolderValidator, resolver: DatabaseIdResolver, database_connection : DatabaseUpdater, directions_extractor : DirectionsExtractor) -> None:
        self._paths = base_validator.get_files()
        self._resolver = resolver
        self._db_connection = database_connection
        self._extractor = directions_extractor

    def write_data(self)->None:
        logger.info("Populating %s", PredefinedTableNames.studies_directions.value)
        for path in tqdm.tqdm(self._paths, disable=None):
            try:
                directions = self._extractor.extract_fields(path=path)
                for direction in directions:
                    self._db_connection.update_db(
                        table_name=PredefinedTableNames.studies_directions.value,
                        labels=[
                            StudiesDirectionsTableColumns.direction_type_id.value,
                            StudiesDirectionsTableColumns.miovision_id.value
                        ],
                        values=[
                            self._resolver.get_direction_type_id(direction.direction_name),
                            direction.miovision_id
                        ]
                    )
            except Exception:
                logger.exception("studies_directions failed while processing %s", path)
                raise

class DirectionsMovementsProvider:
    def __init__(self, base_validator: BaseFolderValidator, db_connection: DatabaseUpdater, extractor: MovementsExtractor, resolver: DatabaseIdResolver) -> None:
        self._paths = base_validator.get_files()
        self._db_connection = db_connection
        self._extractor = extractor
        self._resolver = resolver

    def write_data(self)->None:
        logger.info("Populating %s", PredefinedTableNames.directions_movements.value)
        for path in tqdm.tqdm(self._paths, disable=None):
            miovision_id = int(MiovisionExtractor.get_miovision_id_string(path))
            extracted_data = self._extractor.extract_fields(
                path,
                self._resolver.get_direction_names_for_study(miovision_id)
            )

            for direction_movement in extracted_data:
                try:
                    self._db_connection.update_db(
                        table_name=PredefinedTableNames.directions_movements.value,
                        labels=[
                            MovementsDirectionsTableColumns.movement_type_id.value,
                            MovementsDirectionsTableColumns.study_direction_id.value
                        ],
                        values=[
                            self._resolver.get_movement_type_id(direction_movement.movement_name),
                            self._resolver.get_study_direction_id(direction_movement.miovision_id,direction_movement.direction_name)
                        ]
                    )
                except Exception as e:
                    logger.exception("directions_movements failed while processing %s", path)
                    raise Exception(f"Exception raised for {direction_movement.miovision_id} ({path}): {e}") from e


class VehiclesAndGranularCountsProvider:
    def __init__(self, resolver: DatabaseIdResolver, db_connection: DatabaseUpdater, base_validator: BaseFolderValidator, extractor: GranularExtractor) -> None:
        self._paths = base_validator.get_files()
        self._resolver = resolver
        self._db_connection = db_connection
        self._extractor = extractor

    def write_data(self)->None:
        logger.info("Populating %s and %s", PredefinedTableNames.movements_vehicles.value, PredefinedTableNames.granular_count.value)
        for path in tqdm.tqdm(self._paths, disable=None):
            logger.info("Processing granular counts for %s", path.name)
            miovision_id = int(MiovisionExtractor.get_miovision_id_string(path))
            vehicle_granular_counts = self._extractor.extract_fields(
                path=path,
                directions=self._resolver.get_direction_names_for_study(miovision_id),
                movements=self._resolver.get_movement_names_for_study(miovision_id),
                vehicles=self._resolver.get_all_vehicle_names()
            )

            # The extractor emits rows in consecutive (direction, movement,
            # vehicle) runs, so the movements_vehicles id is resolved once per
            # run rather than once per timestamp row; the id never outlives
            # the group it was fetched for.
            for (direction_name, movement_name, vehicle_name), granular_rows in groupby(
                vehicle_granular_counts,
                key=lambda row: (row.direction_name, row.movement_name, row.vehicle_name)
            ):
                movement_vehicle_id = self._db_connection.update_db_and_return_id(
                    table_name=PredefinedTableNames.movements_vehicles.value,
                    labels=[
                        MovementVehiclesTableColumns.direction_movement_id.value,
                        MovementVehiclesTableColumns.vehicle_type_id.value
                    ],
                    values=[
                        self._resolver.get_direction_movement_id(miovision_id=miovision_id,
                                                                 direction_name=direction_name,
                                                                 movement_name=movement_name),
                        self._resolver.get_vehicle_type_id(vehicle_name)
                    ]
                )

                for vehicle_granular_count in granular_rows:
                    # Full datetime, not .time(): multi-day studies repeat the same
                    # time-of-day on different days, and update_db's existence check
                    # would drop those rows as duplicates.
                    self._db_connection.update_db(
                            table_name=PredefinedTableNames.granular_count.value,
                            labels=[
                                GranularCountsTableColumns.movement_vehicle_id.value,
                                GranularCountsTableColumns.time_stamp.value,
                                GranularCountsTableColumns.traffic_count.value
                            ],
                            values=[
                                movement_vehicle_id,
                                vehicle_granular_count.time,
                                vehicle_granular_count.traffic_count
                            ]
                        )

class StudiesProvider:
    def __init__(self, base_validator: BaseFolderValidator, database_connection : DatabaseConnection, studies_extractor : StudiesExtractor) -> None:
        self._paths = base_validator.get_files()
        self._db_connection = database_connection
        self._studies_extractor = studies_extractor

    def write_data(self)->None:
        logger.info("Populating %s", PredefinedTableNames.studies.value)
        with self._db_connection as connection:
            for path in tqdm.tqdm(self._paths, disable=None):
                try:
                    study_fields = self._studies_extractor.extract_fields(path)
                except Exception:
                    logger.exception("studies extraction failed for %s", path)
                    raise

                table_name=PredefinedTableNames.studies.value
                labels = [
                    StudiesTableColumns.miovision_id.value,
                    StudiesTableColumns.latitude.value,
                    StudiesTableColumns.longitude.value,
                    StudiesTableColumns.location_name.value,
                    StudiesTableColumns.study_date.value,
                    StudiesTableColumns.study_duration.value,
                    StudiesTableColumns.study_type.value,
                    StudiesTableColumns.study_name.value
                ]
                values = [
                    study_fields.miovision_id,
                    study_fields.latitude,
                    study_fields.longitude,
                    study_fields.location_name,
                    study_fields.study_date.date(),
                    study_fields.study_duration,
                    study_fields.study_type,
                    study_fields.study_name
                ]

                if study_fields.project_name != None:
                    labels.append(StudiesTableColumns.project_name.value)
                    values.append(study_fields.project_name)

                is_existing_row = connection.are_existing_attributes_in_table(attr_labels = labels,
                                                                              attr_values = values,
                                                                              table_name = table_name)

                if not is_existing_row:
                    connection.insert_new_information(
                        table_name= table_name,
                        labels= labels,
                        values= values
                    )

