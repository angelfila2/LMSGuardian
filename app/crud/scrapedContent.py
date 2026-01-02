from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from app.schemas.scrapedContent import ScrapedContentCreate


def create_scraped_content(db: Session, item: ScrapedContentCreate):
    data = item.dict()
    if not data.get("scraped_at"):
        data["scraped_at"] = datetime.utcnow()

    sql = text(
        """
        INSERT INTO scraped_contents (
            module_id, session_id, scraped_at, url_link,
            risk_category, risk_score, content_location,
            is_paywall, apa7, localurl
        )
        VALUES (
            :module_id, :session_id, :scraped_at, :url_link,
            :risk_category, :risk_score, :content_location,
            :is_paywall, :apa7, :localurl
        )
        RETURNING *
        """
    )

    result = db.execute(sql, data).mappings()
    db.commit()
    return dict(result.fetchone())


def update_risk_info(db: Session, link_id: int, score: float, category: str):
    sql = text(
        """
        UPDATE scraped_contents
        SET risk_score = :score,
            risk_category = :category
        WHERE scraped_id = :id
    """
    )

    result = db.execute(sql, {"score": score, "category": category, "id": link_id})
    db.commit()
    return result.rowcount


def updatePaywallStatus(db: Session, link_id: int, paywallstatus: bool):
    sql = text(
        """
        UPDATE scraped_contents
        SET is_paywall = :paywallstatus
        WHERE scraped_id = :id
        """
    )
    result = db.execute(sql, {"paywallstatus": paywallstatus, "id": link_id})
    db.commit()
    return result.rowcount


def updateAPA7citation(db: Session, link_id: int, citation: str):
    sql = text(
        """
        UPDATE scraped_contents
        SET apa7 = :citation
        WHERE scraped_id = :id
        """
    )
    result = db.execute(sql, {"citation": citation, "id": link_id})
    db.commit()
    return result.rowcount


def update_localurl(db: Session, scraped_id: int, localurl: str):
    sql = text(
        """
        UPDATE scraped_contents
        SET localurl = :localurl
        WHERE scraped_id = :scraped_id
    """
    )
    result = db.execute(sql, {"localurl": localurl, "scraped_id": scraped_id})
    db.commit()
    return result.rowcount


def getRecentScan(db: Session):
    sql = text(
        """
        SELECT *
        FROM scraped_contents
        WHERE session_id = (SELECT MAX(session_id) FROM scraper_sessions)
    """
    )
    result = db.execute(sql).mappings().all()
    return list(result)


def getDangerousLinks(db: Session):
    sql = text(
        """
        SELECT *
        FROM scraped_contents
        WHERE session_id = (SELECT MAX(session_id) FROM scraper_sessions)
        AND risk_score < 0
    """
    )
    result = db.execute(sql).mappings().all()
    return list(result)


def getAll(db: Session):
    sql = text("SELECT * FROM scraped_contents")
    result = db.execute(sql).mappings().all()
    return [dict(row) for row in result]


def getById(db: Session, coordinatorId: int):
    sql = text(
        "SELECT uc_id, full_name, email FROM unit_coordinators WHERE uc_id = :id"
    )
    result = db.execute(sql, {"id": coordinatorId}).fetchone()
    return dict(result) if result else None


def get_safe_to_download(db: Session):
    sql = text(
        """
        SELECT scraped_id,
               module_id,
               session_id,
               url_link,
               risk_score,
               risk_category,
               scraped_at,
               content_location,
               is_paywall,
               apa7,
               localurl
        FROM scraped_contents
        WHERE session_id = (SELECT MAX(session_id) FROM scraper_sessions)
          AND risk_score >= 0
          AND is_paywall = false
          AND localurl IS NULL
          AND (risk_category IS NULL OR risk_category NOT LIKE '%porn%')
          AND (risk_category IS NULL OR risk_category NOT LIKE '%adult%')
          AND (risk_category IS NULL OR risk_category NOT LIKE '%explicit%')
          AND (url_link NOT LIKE '%xvideos%' AND url_link NOT LIKE '%pornhub%' 
               AND url_link NOT LIKE '%xnxx%' AND url_link NOT LIKE '%redtube%'
               AND url_link NOT LIKE '%youporn%' AND url_link NOT LIKE '%adult%')
    """
    )
    result = db.execute(sql).mappings().all()

    # Additional filtering using content filter
    try:
        import sys
        import os

        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from content_filter import content_filter

        filtered_results = []
        for item in result:
            url = item.get("url_link", "")
            should_exclude, reason = content_filter.should_exclude_from_local_storage(
                url
            )
            if not should_exclude:
                filtered_results.append(item)
            else:
                print(f"🚫 Excluded from local storage: {url} - {reason}")

        return filtered_results
    except Exception as e:
        print(f"⚠️ Content filter not available, using basic filtering: {e}")
        return list(result)


def get_localcopies_by_module(db: Session, module_id: int):
    sql = text(
        """
        SELECT *
        FROM scraped_contents
        WHERE session_id = (SELECT MAX(session_id) FROM scraper_sessions)
          AND localurl IS NOT NULL
          AND module_id = :module_id
    """
    )
    result = db.execute(sql, {"module_id": module_id}).mappings().all()
    return list(result)


def get_scrapedcontent_by_id(db: Session, scraped_id: int):
    sql = text("SELECT * FROM scraped_contents WHERE scraped_id = :scraped_id")
    result = db.execute(sql, {"scraped_id": scraped_id}).mappings().fetchone()
    return dict(result) if result else None
