from types import SimpleNamespace

from googleapiclient.errors import HttpError

from app.adapters.sheets import GoogleSheetsAdapter
from app.config import Settings


def build_http_error(status_code: int, message: str = "error") -> HttpError:
    resp = SimpleNamespace(status=status_code, reason=message)
    content = f'{{"error": {{"message": "{message}"}}}}'.encode()
    return HttpError(resp=resp, content=content)


def build_settings() -> Settings:
    return Settings(
        google_sheet_id="test-sheet-id",
        google_sheet_name="Sheet1",
        google_credentials_path="credentials/service_account.json",
    )


def test_map_http_error_400():
    adapter = GoogleSheetsAdapter(settings=build_settings())

    app_error = adapter._map_http_error(
        build_http_error(400, "Unable to parse range"),
        action="append",
    )

    assert app_error.status_code == 502
    assert app_error.error_code == "GOOGLE_SHEETS_RANGE_ERROR"
    assert app_error.message == "Google Sheets rejected the request range or payload."


def test_map_http_error_403():
    adapter = GoogleSheetsAdapter(settings=build_settings())

    app_error = adapter._map_http_error(
        build_http_error(403, "Forbidden"),
        action="append",
    )

    assert app_error.status_code == 502
    assert app_error.error_code == "GOOGLE_SHEETS_PERMISSION_DENIED"
    assert "access denied" in app_error.message.lower()


def test_map_http_error_404():
    adapter = GoogleSheetsAdapter(settings=build_settings())

    app_error = adapter._map_http_error(
        build_http_error(404, "Not Found"),
        action="append",
    )

    assert app_error.status_code == 502
    assert app_error.error_code == "GOOGLE_SHEETS_NOT_FOUND"
    assert app_error.message == "Google Sheet or sheet tab was not found."


def test_map_http_error_fallback():
    adapter = GoogleSheetsAdapter(settings=build_settings())

    app_error = adapter._map_http_error(
        build_http_error(500, "Internal error"),
        action="append",
    )

    assert app_error.status_code == 502
    assert app_error.error_code == "GOOGLE_SHEETS_API_ERROR"
    assert app_error.message == "Google Sheets API error."