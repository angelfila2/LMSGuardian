from sqlalchemy import Column, Integer, String
from app.database.database import Base
from sqlalchemy.orm import relationship


class UnitCoordinator(Base):
    __tablename__ = "unit_coordinators"

    uc_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)

    # Reverse relationship to modules
    modules = relationship("Module", back_populates="coordinator")
