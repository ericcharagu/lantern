import pytest
from faker import Faker
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from db.base import Base, execute_insert_query, CameraTraffic
import time
import docker
import os

# --- Test Setup ---
fake = Faker()


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up a PostgreSQL Docker container for tests."""
    client = docker.from_env()
    container = client.containers.run(
        "postgres:13",
        environment={
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test",
        },
        ports={"5432/tcp": 5432},
        detach=True,
        remove=True,
    )
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_USER"] = "test"
    os.environ["POSTGRES_PASSWORD"] = "test"
    os.environ["POSTGRES_DB"] = "test"

    # Wait for DB to start
    time.sleep(5)
    yield
    container.stop()


@pytest.fixture(scope="function")
def test_db(postgres_container):
    """Create fresh tables for each test."""
    engine = create_async_engine("postgresql://test:test@localhost:5432/test")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db):
    """Transactional session that rolls back after each test."""
    connection = test_db.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# --- Test Data Generation ---
def generate_camera_data(num_rows=1):
    return [
        {
            "timestamp": datetime.now(timezone.utc),
            "camera_name": f"Cam_{fake.unique.random_number()}",
            "count": fake.random_int(min=1, max=100),
            "location": fake.city(),
            "direction": fake.random_element(["N", "S", "E", "W"]),
            "day_of_week": fake.day_of_week(),
            "is_holiday": fake.boolean(),
        }
        for _ in range(num_rows)
    ]


# --- Tests ---
def test_single_insert(test_db, db_session):
    data = generate_camera_data(1)[0]
    execute_insert_query(CameraTraffic, data)

    result = db_session.execute(
        text(f"SELECT * FROM camera_traffic WHERE camera_name = :name"),
        {"name": data["camera_name"]},
    ).fetchone()

    assert result.count == data["count"]


def test_bulk_insert_1000_rows(test_db, db_session):
    data = generate_camera_data(1000)
    start_time = time.time()

    execute_insert_query(CameraTraffic, data, batch_size=500)

    duration = time.time() - start_time
    print(f"\nInserted 1000 rows in {duration:.2f} seconds")

    count = db_session.execute(text("SELECT COUNT(*) FROM camera_traffic")).scalar()
    assert count == 1000


def test_empty_insert(test_db):
    execute_insert_query(CameraTraffic, [])


def test_data_integrity(test_db, db_session):
    data = {
        "timestamp": datetime.now(timezone.utc),
        "camera_name": "Integrity_Test",
        "count": 42,
        "is_holiday": False,
    }
    execute_insert_query(CameraTraffic, data)

    row = db_session.execute(
        text("SELECT * FROM camera_traffic WHERE camera_name = 'Integrity_Test'")
    ).fetchone()

    assert not row.is_holiday
    assert isinstance(row.timestamp, datetime)
