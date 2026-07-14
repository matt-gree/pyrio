import re


class RioAPIError(Exception):
    """Base exception for Project Rio API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


class RioAuthError(RioAPIError):
    """Raised for 401/403 authentication/authorization errors."""
    pass


class RioNotFoundError(RioAPIError):
    """Raised for 404 not found errors."""
    pass


def _extract_error_message(response) -> str:
    """Extract a readable error message from an HTTP error response."""
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            return response.json().get("description", response.text)
        except Exception:
            return response.text
    elif "text/html" in content_type:
        match = re.search(r"<p>(.*?)</p>", response.text)
        return match.group(1) if match else response.text
    return response.text


def raise_for_status(response):
    """Raise an appropriate RioAPIError subclass for HTTP error responses."""
    if response.ok:
        return
    message = _extract_error_message(response)
    status = response.status_code
    if status in (401, 403):
        raise RioAuthError(status, message)
    elif status == 404:
        raise RioNotFoundError(status, message)
    else:
        raise RioAPIError(status, message)
