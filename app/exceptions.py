class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class DuplicateLeadError(AppError):
    def __init__(self, message: str = "Duplicate lead detected.") -> None:
        super().__init__(
            status_code=409,
            error_code="DUPLICATE_LEAD",
            message=message,
        )