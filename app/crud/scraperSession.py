from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime


def get_all_sessions(db: Session):
    sql = text("SELECT * FROM scraper_sessions")
    result = db.execute(sql).mappings().all()
    return list(result)


def get_latest_running_session(db: Session):
    sql = text(
        """
        SELECT *
        FROM scraper_sessions
        WHERE completion_status IN ('started')
        ORDER BY started_at DESC
        LIMIT 1
    """
    )
    result = db.execute(sql).mappings().first()
    return dict(result) if result else None


def update_session_status(
    db: Session, session_id: int, status: str, error_log: str = None
):
    now = datetime.utcnow()
    sql = text(
        """
        UPDATE scraper_sessions
        SET ended_at = :ended_at,
            completion_status = :status,
            error_log = :error_log
        WHERE session_id = :session_id
    """
    )
    db.execute(
        sql,
        {
            "ended_at": now,
            "status": status,
            "error_log": error_log,
            "session_id": session_id,
        },
    )
    db.commit()


def start_new_session(db: Session):
    now = datetime.utcnow()
    sql = text(
        """
        INSERT INTO scraper_sessions (started_at, completion_status)
        VALUES (:started_at, :status)
        RETURNING session_id, started_at, ended_at, completion_status, error_log
    """
    )
    result = db.execute(sql, {"started_at": now, "status": "started"}).mappings()
    db.commit()
    return dict(result.fetchone())
