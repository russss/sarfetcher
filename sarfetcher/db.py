from sqlalchemy import Table, Column, String, MetaData, DateTime, Integer, create_engine
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry


def get_db(url):
    engine = create_engine("postgresql://russ@localhost/sentinel1")
    metadata.create_all(engine)
    return engine.connect()


metadata = MetaData()

images = Table(
    "images",
    metadata,
    Column("uuid", UUID, primary_key=True),
    Column("title", String, unique=True, nullable=False),
    Column("start_date", DateTime, nullable=False),
    Column("geom", Geometry("MULTIPOLYGON", 4326)),
)

search_area = Table(
    "search_area",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("geom", Geometry("POLYGON", 4326)),
)
