"""
Announcement endpoints for the High School Management System API
"""

from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)

logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"


class AnnouncementPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=1, max_length=280)
    start_date: Optional[str] = Field(default=None)
    end_date: str = Field(...)


def parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    if value in (None, ""):
        return None

    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        logger.exception("Invalid %s value", field_name)
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be in YYYY-MM-DD format"
        ) from exc


def validate_date_range(start_date: Optional[date], end_date: date) -> None:
    if start_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be on or before end_date"
        )


def require_teacher(teacher_username: Optional[str]) -> Dict[str, Any]:
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def serialize_announcement(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(document.get("_id")),
        "title": document.get("title"),
        "message": document.get("message"),
        "start_date": document.get("start_date"),
        "end_date": document.get("end_date"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at")
    }


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get active announcements for the banner."""
    today = date.today().isoformat()
    query = {
        "end_date": {"$gte": today},
        "$or": [
            {"start_date": {"$exists": False}},
            {"start_date": None},
            {"start_date": ""},
            {"start_date": {"$lte": today}}
        ]
    }

    try:
        announcements = announcements_collection.find(query).sort(
            [("start_date", 1), ("created_at", -1)]
        )
        return [serialize_announcement(doc) for doc in announcements]
    except Exception:
        logger.exception("Failed to fetch active announcements")
        raise HTTPException(
            status_code=500,
            detail="Failed to load announcements"
        )


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_announcements(
    teacher_username: Optional[str] = Query(None)
) -> List[Dict[str, Any]]:
    """List all announcements for management."""
    require_teacher(teacher_username)

    try:
        announcements = announcements_collection.find().sort(
            [("end_date", -1), ("start_date", -1)]
        )
        return [serialize_announcement(doc) for doc in announcements]
    except Exception:
        logger.exception("Failed to list announcements")
        raise HTTPException(
            status_code=500,
            detail="Failed to load announcements"
        )


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement."""
    require_teacher(teacher_username)

    start_date = parse_date(payload.start_date, "start_date")
    end_date = parse_date(payload.end_date, "end_date")
    if end_date is None:
        raise HTTPException(status_code=400, detail="end_date is required")

    validate_date_range(start_date, end_date)

    document = {
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    try:
        result = announcements_collection.insert_one(document)
        document["_id"] = result.inserted_id
        return serialize_announcement(document)
    except Exception:
        logger.exception("Failed to create announcement")
        raise HTTPException(
            status_code=500,
            detail="Failed to create announcement"
        )


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement."""
    require_teacher(teacher_username)

    start_date = parse_date(payload.start_date, "start_date")
    end_date = parse_date(payload.end_date, "end_date")
    if end_date is None:
        raise HTTPException(status_code=400, detail="end_date is required")

    validate_date_range(start_date, end_date)

    try:
        announcement_object_id = ObjectId(announcement_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid announcement id") from exc

    updates = {
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat(),
        "updated_at": datetime.utcnow()
    }

    try:
        result = announcements_collection.update_one(
            {"_id": announcement_object_id},
            {"$set": updates}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Announcement not found")

        updated = announcements_collection.find_one({"_id": announcement_object_id})
        if not updated:
            raise HTTPException(status_code=404, detail="Announcement not found")

        return serialize_announcement(updated)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update announcement")
        raise HTTPException(
            status_code=500,
            detail="Failed to update announcement"
        )


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Delete an announcement."""
    require_teacher(teacher_username)

    try:
        announcement_object_id = ObjectId(announcement_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid announcement id") from exc

    try:
        announcement = announcements_collection.find_one({"_id": announcement_object_id})
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")

        announcements_collection.delete_one({"_id": announcement_object_id})
        return {"message": "Announcement deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete announcement")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete announcement"
        )
