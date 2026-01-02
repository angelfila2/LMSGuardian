from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ScraperSessionBase(BaseModel):
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    completion_status: Optional[str] = None
    error_log: Optional[str] = None


class ScraperSessionCreate(ScraperSessionBase):
    pass


class ScraperSession(ScraperSessionBase):
    session_id: int

    class Config:
        orm_mode = True
