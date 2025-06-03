from sqlalchemy import create_engine, Column, Integer, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func, extract
import os
from datetime import datetime, timedelta, timezone
from loguru import logger

# Model definition
Base = declarative_base()

# Logging
logger.add("./logs/camera_stats.log", rotation="1 week")


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
    with open("/run/secrets/postgres_secrets", "r") as f:
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

    def get_confidence_stats(self):
        """Get average confidence by class"""
        return (
            self.session.query(
                CameraTrackingData.class_id,
                func.avg(CameraTrackingData.confidence).label("avg_confidence"),
                func.max(CameraTrackingData.confidence).label("max_confidence"),
                func.min(CameraTrackingData.confidence).label("min_confidence"),
            )
            .group_by(CameraTrackingData.class_id)
            .all()
        )

    def get_movement_stats(self, camera_id=None):
        """Get movement statistics (x/y center averages)"""
        query = self.session.query(
            func.avg(CameraTrackingData.x_center).label("avg_x"),
            func.avg(CameraTrackingData.y_center).label("avg_y"),
            func.stddev(CameraTrackingData.x_center).label("stddev_x"),
            func.stddev(CameraTrackingData.y_center).label("stddev_y"),
        )

        if camera_id:
            query = query.filter(CameraTrackingData.camera_id == camera_id)

        return query.first()

    def get_tracker_activity(self, tracker_id):
        """Get activity timeline for a specific tracker"""
        return (
            self.session.query(
                extract("hour", CameraTrackingData.timestamp).label("hour"),
                func.count(CameraTrackingData.id).label("detections"),
            )
            .filter(
                CameraTrackingData.tracker_id == tracker_id,
                CameraTrackingData.timestamp >= datetime.utcnow() - timedelta(days=1),
            )
            .group_by("hour")
            .order_by("hour")
            .all()
        )

    def get_bbox_stats(self):
        """Get statistics about bounding box sizes"""
        return self.session.query(
            func.avg(CameraTrackingData.bbox[2] - CameraTrackingData.bbox[0]).label(
                "avg_width"
            ),
            func.avg(CameraTrackingData.bbox[3] - CameraTrackingData.bbox[1]).label(
                "avg_height"
            ),
        ).first()

    def close(self):
        self.session.close()
