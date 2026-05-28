# models/scraped_item.py
# ─────────────────────────────────────────────────────────────
# Pydantic models for scraped data.
#
# WHY MODELS MATTER:
#   Validating data before it reaches the database catches
#   problems early (missing fields, wrong types, encoding issues)
#   rather than letting corrupt data silently slip in.
#
# BEST PRACTICE: define one model per website/scraper. They can
#   all inherit from ScrapedItem for the shared fields.
# ─────────────────────────────────────────────────────────────

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator, model_validator


class ScrapedItem(BaseModel):
    """Base model — fields shared by every scraper."""

    page_url:    str
    domain:      str = ""
    scraped_at:  datetime = None   # type: ignore[assignment]
    scraper_name: str = ""

    @model_validator(mode="after")
    def _set_defaults(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc)
        if not self.domain and self.page_url:
            from urllib.parse import urlparse
            self.domain = urlparse(self.page_url).netloc
        return self

    class Config:
        # Allow extra fields so subclasses don't need to redeclare base fields
        extra = "allow"


class SalonProfile(ScrapedItem):
    """
    Data model for a hair salon staff profile scraped from minimodel.jp.
    Extend this for other profile-style pages.
    """
    scraper_name: str = "minimo"

    salon_name:   Optional[str] = None
    salon_kana:   Optional[str] = None
    staff_name:   Optional[str] = None
    rating:       Optional[str] = None
    location:     Optional[str] = None
    phone_number: Optional[str] = None
    updated_date: Optional[str] = None

    @field_validator("salon_name", "staff_name", "location", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("location", mode="before")
    @classmethod
    def clean_location(cls, v):
        if isinstance(v, str):
            return v.replace("(地図)", "").replace("地図", "").strip() or None
        return v


class FailedURL(BaseModel):
    """Tracks a URL that failed to scrape."""
    url:        str
    error_type: str
    status:     Optional[str] = None
    message:    str
    failed_at:  datetime = None  # type: ignore[assignment]
    scraper_name: str = ""

    @model_validator(mode="after")
    def _set_time(self):
        if not self.failed_at:
            self.failed_at = datetime.now(timezone.utc)
        return self
