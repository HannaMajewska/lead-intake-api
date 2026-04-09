import logging
from dataclasses import dataclass

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings
from app.exceptions import AppError


logger = logging.getLogger(__name__)


@dataclass
class SheetsAppendResult:
    saved: bool
    row_ref: str


class GoogleSheetsAdapter:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    HEADER = [
        "lead_id",
        "created_at",
        "name",
        "email",
        "phone",
        "message",
        "source",
        "campaign",
        "city",
        "crm_status",
        "crm_record_id",
    ]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _build_service(self):
        credentials = Credentials.from_service_account_file(
            self.settings.google_credentials_path,
            scopes=self.SCOPES,
        )
        return build("sheets", "v4", credentials=credentials)

    def _map_http_error(self, exc: HttpError, *, action: str) -> AppError:
        status = getattr(exc.resp, "status", 500)

        logger.exception(
            f"sheets_{action}_failed",
            extra={
                "status_code": status,
                "sheet_id": self.settings.google_sheet_id,
                "sheet_name": self.settings.google_sheet_name,
            },
        )

        if status == 400:
            return AppError(
                status_code=502,
                error_code="GOOGLE_SHEETS_RANGE_ERROR",
                message="Google Sheets rejected the request range or payload.",
            )

        if status == 403:
            return AppError(
                status_code=502,
                error_code="GOOGLE_SHEETS_PERMISSION_DENIED",
                message="Google Sheets access denied. Check sharing permissions for the service account.",
            )

        if status == 404:
            return AppError(
                status_code=502,
                error_code="GOOGLE_SHEETS_NOT_FOUND",
                message="Google Sheet or sheet tab was not found.",
            )

        return AppError(
            status_code=502,
            error_code="GOOGLE_SHEETS_API_ERROR",
            message="Google Sheets API error.",
        )

    def ensure_header(self) -> None:
        try:
            service = self._build_service()
            header_range = f"{self.settings.google_sheet_name}!A1:K1"

            response = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.settings.google_sheet_id,
                    range=header_range,
                )
                .execute()
            )

            values = response.get("values", [])
            current_header = values[0] if values else []

            if current_header == self.HEADER:
                return

            body = {"values": [self.HEADER]}

            (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.settings.google_sheet_id,
                    range=header_range,
                    valueInputOption="RAW",
                    body=body,
                )
                .execute()
            )

            logger.info(
                "sheets_header_initialized",
                extra={"sheet_name": self.settings.google_sheet_name},
            )

        except HttpError as exc:
            raise self._map_http_error(exc, action="header_init") from exc
        except FileNotFoundError as exc:
            logger.exception(
                "google_credentials_file_not_found",
                extra={"credentials_path": self.settings.google_credentials_path},
            )
            raise AppError(
                status_code=500,
                error_code="GOOGLE_CREDENTIALS_FILE_NOT_FOUND",
                message="Google credentials file was not found.",
            ) from exc

    def get_all_rows(self) -> list[list[str]]:
        try:
            self.ensure_header()

            service = self._build_service()
            target_range = f"{self.settings.google_sheet_name}!A:K"

            response = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.settings.google_sheet_id,
                    range=target_range,
                )
                .execute()
            )

            return response.get("values", [])

        except HttpError as exc:
            raise self._map_http_error(exc, action="read") from exc
        except FileNotFoundError as exc:
            logger.exception(
                "google_credentials_file_not_found",
                extra={"credentials_path": self.settings.google_credentials_path},
            )
            raise AppError(
                status_code=500,
                error_code="GOOGLE_CREDENTIALS_FILE_NOT_FOUND",
                message="Google credentials file was not found.",
            ) from exc

    def append_lead_row(self, row: list[str]) -> SheetsAppendResult:
        try:
            self.ensure_header()

            service = self._build_service()
            target_range = f"{self.settings.google_sheet_name}!A:K"
            body = {"values": [row]}

            response = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.settings.google_sheet_id,
                    range=target_range,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )

            updated_range = response.get("updates", {}).get("updatedRange", "")

            logger.info(
                "sheets_append_success",
                extra={"updated_range": updated_range},
            )

            return SheetsAppendResult(saved=True, row_ref=updated_range)

        except HttpError as exc:
            raise self._map_http_error(exc, action="append") from exc
        except FileNotFoundError as exc:
            logger.exception(
                "google_credentials_file_not_found",
                extra={"credentials_path": self.settings.google_credentials_path},
            )
            raise AppError(
                status_code=500,
                error_code="GOOGLE_CREDENTIALS_FILE_NOT_FOUND",
                message="Google credentials file was not found.",
            ) from exc