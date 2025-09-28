from rest_framework.exceptions import APIException


def api_error(status_code: int, message: str) -> APIException:
    """Create DRF APIException with custom status code and message.

    This helper centralizes error creation to keep views thin and consistent.
    """
    exc = APIException(detail=message)
    exc.status_code = status_code
    return exc


