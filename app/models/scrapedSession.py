from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database.database import Base


class ScraperSession(Base):
    __tablename__ = "scraper_sessions"

    session_id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    completion_status = Column(String)
    error_log = Column(Text)

    # Reverse relationship to ScrapedContent
    contents = relationship("ScrapedContent", back_populates="session")
