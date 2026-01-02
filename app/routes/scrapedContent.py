from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from app.database.database import getDb
from app.schemas import scrapedContent as schemas
from app.crud import scrapedContent as crud

router = APIRouter(prefix="/scrapedcontents", tags=["Scraped Contents"])


@router.get("/", response_model=List[schemas.ScrapedContent])
def get_all_scraped_contents(db: Session = Depends(getDb)):
    return crud.getAll(db)


@router.get("/testroute/", response_model=List[schemas.ScrapedContent])
def get_all_scraped_contents(db: Session = Depends(getDb)):
    return crud.getAll(db)


@router.post("/", response_model=schemas.ScrapedContent)
def create_scraped_content(
    item: schemas.ScrapedContentCreate, db: Session = Depends(getDb)
):
    return crud.create_scraped_content(db, item)


@router.get("/scan", response_model=List[schemas.ScrapedContent])
def get_high_risks(db: Session = Depends(getDb)):
    return crud.getRecentScan(db)


@router.get("/get/{scraped_id}")
def get_scraped_content(scraped_id: int, db: Session = Depends(getDb)):
    result = crud.get_scrapedcontent_by_id(db, scraped_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scraped content not found")
    return result


@router.get("/highrisks", response_model=List[schemas.ScrapedContent])
def get_negative_risks(db: Session = Depends(getDb)):
    return crud.getDangerousLinks(db)


@router.get("/safe", response_model=List[schemas.ScrapedContent])
def get_safe_links(db: Session = Depends(getDb)):
    return crud.get_safe_to_download(db)


@router.get("/localcopyavailable/{module_id}")
def get_local_copies_by_module(module_id: int, db: Session = Depends(getDb)):
    return crud.get_localcopies_by_module(db, module_id)


@router.put("/updaterisk/{link_id}")
def update_risk_info_api(
    link_id: int, score: float, category: str, db: Session = Depends(getDb)
):
    rows_updated = crud.update_risk_info(db, link_id, score, category)
    if rows_updated == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    return {
        "message": "Risk info updated",
        "link_id": link_id,
        "new_score": score,
        "new_category": category,
    }


@router.put("/updatepaywall/{link_id}")
def updatepaywall(link_id: int, ispaywall: bool, db: Session = Depends(getDb)):
    rows_updated = crud.updatePaywallStatus(db, link_id, ispaywall)
    if rows_updated == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"message": "Risk info updated", "link_id": link_id, "is_paywall": ispaywall}


@router.put("/updatecitation/{link_id}")
def updatecitation(link_id: int, citation: str, db: Session = Depends(getDb)):
    rows_updated = crud.updateAPA7citation(db, link_id, citation)
    if rows_updated == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"message": "Citation updated", "link_id": link_id, "apa7": citation}


@router.post("/generatecitation/{link_id}")
def generate_citation_for_link(link_id: int, db: Session = Depends(getDb)):
    """Generate APA 7th edition citation for a specific scraped content item"""
    try:
        # Import APA generator
        import sys
        import os

        sys.path.append(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        from scraper.citation.integrator import APACitationIntegrator

        # Generate citation
        integrator = APACitationIntegrator()
        success = integrator.update_single_citation(link_id, db)

        if success:
            return {
                "message": "APA citation generated successfully",
                "link_id": link_id,
            }
        else:
            raise HTTPException(
                status_code=404, detail="Link not found or citation generation failed"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating citation: {str(e)}"
        )


@router.post("/generatecitations/batch")
def generate_citations_batch(db: Session = Depends(getDb)):
    """Generate APA 7th edition citations for all scraped content without citations"""
    try:
        # Import APA generator
        import sys
        import os

        sys.path.append(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        from scraper.citation.integrator import APACitationIntegrator

        # Generate citations
        integrator = APACitationIntegrator()
        updated_count = integrator.update_citations_for_scraped_content(db)

        return {
            "message": f"Successfully generated {updated_count} APA citations",
            "updated_count": updated_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating citations: {str(e)}"
        )


@router.post("/citation/url")
def generate_citation_for_url(request: dict):
    """Generate APA 7th edition citation for a specific URL"""
    try:
        url = request.get("url")
        title = request.get("title")

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Import APA generator
        import sys
        import os

        sys.path.append(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        from scraper.citation.integrator import APACitationIntegrator

        # Generate citation
        integrator = APACitationIntegrator()
        result = integrator.generate_citation_for_url(url, title)

        return {
            "url": url,
            "citation": result["citation"],
            "type": result["type"],
            "metadata": result.get("metadata", {}),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating citation: {str(e)}"
        )


@router.put("/localurl/{scraped_id}")
def update_localurl_route(scraped_id: int, localurl: str, db: Session = Depends(getDb)):
    updated = crud.update_localurl(db, scraped_id, localurl)
    if updated == 0:
        raise HTTPException(status_code=404, detail="scraped_id not found")

    return {
        "scraped_id": scraped_id,
        "localurl": localurl,
        "message": "localurl updated",
    }
