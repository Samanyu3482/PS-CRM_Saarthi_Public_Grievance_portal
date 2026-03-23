import os
from fastapi import APIRouter, File, UploadFile, HTTPException
from pathlib import Path

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    try:
        filename = file.filename
        dest = UPLOAD_DIR / filename
        # prevent overwriting by adding suffix if exists
        counter = 1
        stem = dest.stem
        suffix = dest.suffix
        while dest.exists():
            dest = UPLOAD_DIR / f"{stem}-{counter}{suffix}"
            counter += 1

        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)

        # Return a URL path relative to the app mount
        return {"url": f"/uploads/{dest.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
