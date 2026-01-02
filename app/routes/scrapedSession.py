from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from app.database.database import getDb
from app.schemas import scraperSession as schema
from app.crud import scraperSession as crud
from typing import Optional


router = APIRouter(prefix="/scrapersession", tags=["Scraper Sessions"])


@router.get("/", response_model=List[schema.ScraperSession])
def get_all_sessions(db: Session = Depends(getDb)):
    return crud.get_all_sessions(db)


@router.post("/newsession", response_model=schema.ScraperSession)
def start_new_session(db: Session = Depends(getDb)):
    return crud.start_new_session(db)


@router.get("/latest", response_model=schema.ScraperSession)
def get_latest_running_session(db: Session = Depends(getDb)):
    session = crud.get_latest_running_session(db)
    if not session:
        raise HTTPException(status_code=404, detail="No running session found")
    return session


@router.put("/update/{session_id}", response_model=dict)
def update_session_status(
    session_id: int,
    status: str,
    error_log: Optional[str] = None,
    db: Session = Depends(getDb),
):
    try:
        crud.update_session_status(db, session_id, status, error_log)
        return {"message": f"Session {session_id} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
