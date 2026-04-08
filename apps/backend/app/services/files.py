"""
File and image handling helpers shared across routers.
"""
import hashlib
import os
from pathlib import Path

import requests as http
from sqlalchemy.orm import Session

from .helpers import STATIC_DIR, ext_from_content_type


def save_plant_image(
    db: Session,
    entry,                  # PlantLibrary ORM object
    img_bytes: bytes,
    source: str,
    ext: str = '.jpg',
    source_url: str | None = None,
    attribution: str | None = None,
    make_primary: bool = False,
):
    """
    Hash-check img_bytes, save to static/plant_images/, insert PlantLibraryImage row.
    Returns (PlantLibraryImage row, was_duplicate). Caller must commit.
    """
    from ..db.models import PlantLibraryImage

    fhash = hashlib.sha256(img_bytes).hexdigest()
    existing = db.query(PlantLibraryImage).filter_by(file_hash=fhash).first()
    if existing:
        return existing, True

    count = db.query(PlantLibraryImage).filter_by(
        plant_library_id=entry.id, source=source
    ).count()
    filename = f'{entry.id}_{source}_{count + 1}{ext}'
    dest = STATIC_DIR / 'plant_images' / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(img_bytes)

    has_primary = db.query(PlantLibraryImage).filter_by(
        plant_library_id=entry.id, is_primary=True
    ).first() is not None
    is_primary = make_primary or not has_primary

    img_row = PlantLibraryImage(
        plant_library_id=entry.id,
        filename=filename,
        source=source,
        source_url=source_url,
        attribution=attribution,
        file_hash=fhash,
        is_primary=is_primary,
    )
    db.add(img_row)
    if is_primary:
        entry.image_filename = filename
    return img_row, False


def download_and_save_plant_image(
    db: Session,
    entry,
    url: str,
    source: str,
    attribution: str | None = None,
    make_primary: bool = False,
):
    """Download image from URL and call save_plant_image. Returns (img_row, was_dup) or raises."""
    r = http.get(url, timeout=15)
    r.raise_for_status()
    ext = ext_from_content_type(r.headers.get('content-type', ''))
    return save_plant_image(db, entry, r.content, source, ext=ext,
                            source_url=url, attribution=attribution,
                            make_primary=make_primary)
