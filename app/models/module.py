from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class Module(Base):
    __tablename__ = "modules"

    module_id = Column(Integer, primary_key=True, index=True)
    uc_id = Column(Integer, ForeignKey("unit_coordinators.uc_id"), nullable=False)
    module_name = Column(String, nullable=False)
    teaching_period = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    module_description = Column(String, nullable=False)
    unit_code = Column(String, nullable=False)

    # Reverse relationship to scraped contents
    contents = relationship("ScrapedContent", back_populates="module")
    # Forward relationship to unit coordinator
    coordinator = relationship("UnitCoordinator", back_populates="modules")
