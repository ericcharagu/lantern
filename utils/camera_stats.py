# utils/camera_stats.py

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from datetime import datetime, timedelta
from loguru import logger
from utils.timezone import nairobi_tz
from .db.base import DetectionLog  

# Logging
logger.add("./logs/camera_stats.log", rotation="1 week")

Base = declarative_base()


class CameraTrackingData(Base):
    __tablename__ = "camera_tracking_data"
    id = Column(Integer, primary_key=True)
    tracker_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    x_center = Column(Float, nullable=False)
    y_center = Column(Float, nullable=False)
    bbox = Column(JSON, nullable=False)
    class_id = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    camera_id = Column(Integer, nullable=False)


# Connection setup
def get_connection_string():
    with open("./secrets/postgres_secrets.txt", "r") as f:
        password = f.read().strip()

    return f"postgresql://{os.getenv('DB_USER', 'postgres')}:{password}@{os.getenv('DB_HOST', 'postgres')}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME', 'postgres')}"


engine = create_engine(get_connection_string(), pool_pre_ping=True, pool_recycle=300)
Session = sessionmaker(bind=engine)


# Statistics functions
class CameraStats:
    def __init__(self):
        self.session = Session()

    def get_detection_counts(self, hours=24):
        """Get detection counts per camera for last N hours"""
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.session.query(
                CameraTrackingData.camera_id,
                func.count(CameraTrackingData.id).label("detection_count"),
            )
            .filter(CameraTrackingData.timestamp >= time_threshold)
            .group_by(CameraTrackingData.camera_id)
            .all()
        )
        .where(DetectionLog.timestamp >= time_threshold)
        .group_by(DetectionLog.camera_name)
    )
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_confidence_stats(session: AsyncSession) -> list:
    """Get average confidence by class."""
    stmt = select(
        DetectionLog.class_id,
        func.avg(DetectionLog.confidence).label("avg_confidence"),
        func.max(DetectionLog.confidence).label("max_confidence"),
        func.min(DetectionLog.confidence).label("min_confidence"),
    ).group_by(DetectionLog.class_id)
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_movement_stats(session: AsyncSession, camera_name: str):
    """Get movement statistics (x/y center averages)."""
    x_center:float=DetectionLog.box_x1+((DetectionLog.box_x2-DetectionLog.box_x1)/2)
    y_center:float=DetectionLog.box_y1+((DetectionLog.box_y2-DetectionLog.box_y1)/2)
    stmt = select(
        func.avg(x_center).label("avg_x"),
        func.avg(y_center).label("avg_y"),
        func.stddev(x_center).label("stddev_x"),
        func.stddev(y_center).label("stddev_y"),
    )
    if camera_name:
        stmt = stmt.where(DetectionLog.camera_name == camera_name)

    result = await session.execute(stmt)
    return result.mappings().first()

def close(session: AsyncSession):
    session.close()
