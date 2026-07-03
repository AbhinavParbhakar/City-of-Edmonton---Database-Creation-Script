import pytest
from .database_provider import DatabaseVolumeProvider, ConnectionStringProvider, VolumeQueryProvider
from .database_provider import MiovisionDBVolumeProvider, LocalConnectionStringProvider, MiovisionDBQueryProvider
from pathlib import Path
from .volume_provider import DirectionalVolumeAttr
from .fixture_files import fixtures_folder

@pytest.fixture(scope='module')
def env_key()->str:
    return "LOCAL_DATABASE_URL"

@pytest.fixture(scope='module')
def connection_string_provider(env_key)->ConnectionStringProvider:
    return LocalConnectionStringProvider(env_key)

@pytest.fixture(scope='module')
def query_provider()->VolumeQueryProvider:
    return MiovisionDBQueryProvider()

@pytest.fixture(scope='module')
def volume_provider(query_provider,connection_string_provider)->DatabaseVolumeProvider:
    return MiovisionDBVolumeProvider(connection_string_provider,query_provider)

# Golden values below were captured from the live Miovision study pages
# (datalink.miovision.com/studies/<id>) for two studies from the July 2026
# scraper run; the studies must be loaded in the database under test.

@pytest.fixture(scope='module')
def dummy_path()->Path:
    return fixtures_folder() / 'TMC-1413040.xlsx'

@pytest.fixture(scope='module')
def pedway_path()->Path:
    return fixtures_folder() / 'way-1413018.xlsx'

@pytest.fixture(scope='module')
def pedway_expected_result()->dict[str,DirectionalVolumeAttr]:
    return {
        "Southbound":{
            'total_volume':7685,
            'in_volume':4257,
            'out_volume':3428
        },
        "Northbound":{
            'total_volume':7685,
            'in_volume':3428,
            'out_volume':4257
        }
    }

@pytest.fixture(scope='module')
def expected_result()->dict[str,DirectionalVolumeAttr]:
    return {
        "Southbound":{
            'total_volume':32275,
            'in_volume':17495,
            'out_volume':14780
        },
        "Westbound":{
            'total_volume':17745,
            'in_volume':8587,
            'out_volume':9158
        },
        "Northbound":{
            'total_volume':29354,
            'in_volume':13568,
            'out_volume':15786
        },
        "Eastbound":{
            'total_volume':16390,
            'in_volume':8232,
            'out_volume':8158
        }
    }

def test_db_volume_roadway(dummy_path, volume_provider, expected_result):
    result = volume_provider.return_volumes(dummy_path)
    assert result == expected_result, f"{result} does not match {expected_result}"

def test_db_volume_pedway(pedway_path,pedway_expected_result,volume_provider):
    pedway_result = volume_provider.return_volumes(pedway_path)
    assert pedway_result == pedway_expected_result, f"{pedway_result} does not match {pedway_expected_result}"