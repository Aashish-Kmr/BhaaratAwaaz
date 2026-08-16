from __future__ import annotations

from fastapi import HTTPException


def api_error(status_code: int, message: str, code: str = "error") -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, "code": code})
