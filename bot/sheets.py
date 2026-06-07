"""Google Sheets access through a single service account (gspread)."""
from __future__ import annotations

import asyncio
import re

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


class SheetsService:
    def __init__(self, service_account_file: str):
        self._creds = Credentials.from_service_account_file(
            service_account_file, scopes=_SCOPES
        )
        self._client = gspread.authorize(self._creds)

    @property
    def client_email(self) -> str:
        return self._creds.service_account_email

    @staticmethod
    def extract_sheet_id(text: str) -> str | None:
        match = _SHEET_ID_RE.search(text.strip())
        if match:
            return match.group(1)
        # Allow pasting a bare ID too.
        bare = text.strip()
        if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", bare):
            return bare
        return None

    def _open_first_worksheet(self, sheet_id: str):
        return self._client.open_by_key(sheet_id).sheet1

    async def verify_access(self, sheet_id: str) -> bool:
        def _check() -> bool:
            self._open_first_worksheet(sheet_id).row_values(1)
            return True

        try:
            return await asyncio.to_thread(_check)
        except Exception:
            return False

    async def append_expense(self, sheet_id: str, row: list) -> None:
        def _append() -> None:
            ws = self._open_first_worksheet(sheet_id)
            ws.append_row(row, value_input_option="USER_ENTERED")

        await asyncio.to_thread(_append)
