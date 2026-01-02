from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    Float,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database.database import Base


class ScrapedContent(Base):
    __tablename__ = "scraped_contents"

    scraped_id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.module_id"), nullable=False)
    session_id = Column(
        Integer, ForeignKey("scraper_sessions.session_id"), nullable=False
    )
    scraped_at = Column(DateTime)
    url_link = Column(Text)
    risk_category = Column(String)
    risk_score = Column(Float)
    content_location = Column(Text)
    is_paywall = Column(Boolean, default=False)
    apa7 = Column(Text)  # Legacy field for backward compatibility

    module = relationship("Module", back_populates="contents")
    session = relationship("ScraperSession", back_populates="contents")
