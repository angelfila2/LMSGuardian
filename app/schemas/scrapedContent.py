from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HighRiskLink(BaseModel):
    url: str
    category: Optional[str]
    score: Optional[float]
    date: datetime
    scrapeID: int

    model_config = {"from_attributes": True}


class ScrapedContentBase(BaseModel):
    module_id: int
    session_id: int
    scraped_at: Optional[datetime] = None
    url_link: str
    risk_category: Optional[str] = None
    risk_score: Optional[float] = None
    content_location: Optional[str] = None
    is_paywall: Optional[bool] = False
    apa7: Optional[str] = None  # Legacy field
    localurl: Optional[str] = None


class ScrapedContentCreate(ScrapedContentBase):
    pass


class ScrapedContent(ScrapedContentBase):
    scraped_id: int  # This is returned by the DB

    class Config:
        orm_mode = True
