"""Shared, authenticated and bounded HTTP client for the FACEIT Data API v4."""

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp


logger = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://open.faceit.com/data/v4"


class FaceitAPIError(Exception):
    def __init__(self, message: str, *, status: int | None = None, endpoint: str | None = None):
        super().__init__(message)
        self.status = status
        self.endpoint = endpoint


class FaceitAuthenticationError(FaceitAPIError):
    pass


class FaceitForbiddenError(FaceitAPIError):
    pass


class FaceitNotFoundError(FaceitAPIError):
    pass


class FaceitRateLimitError(FaceitAPIError):
    pass


class FaceitNetworkError(FaceitAPIError):
    pass


class FaceitServerError(FaceitAPIError):
    pass


class FaceitInvalidResponseError(FaceitAPIError):
    pass


class FaceitClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 15,
        max_rate_limit_retries: int = 2,
    ) -> None:
        self.session = session
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_rate_limit_retries = max_rate_limit_retries

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        endpoint = "/" + endpoint.lstrip("/")
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        logger.info("FACEIT request GET %s", endpoint)

        retries = 0
        while True:
            try:
                async with self.session.get(url, headers=headers, params=params, timeout=self.timeout) as response:
                    status = response.status
                    if status == 429:
                        if retries >= self.max_rate_limit_retries:
                            logger.warning("FACEIT rate limit after %d retries: %s", retries, endpoint)
                            raise FaceitRateLimitError("FACEIT rate limit reached", status=status, endpoint=endpoint)
                        delay = self._retry_after(response.headers.get("Retry-After"))
                        retries += 1
                        logger.warning("FACEIT rate limit; retry %d/%d in %.2fs", retries, self.max_rate_limit_retries, delay)
                    elif status == 404 and allow_not_found:
                        return {}
                    elif status >= 400:
                        error_type = {
                            400: FaceitAPIError,
                            401: FaceitAuthenticationError,
                            403: FaceitForbiddenError,
                            404: FaceitNotFoundError,
                        }.get(status, FaceitAPIError)
                        if status >= 500:
                            error_type = FaceitServerError
                        logger.error("FACEIT API error %s for %s", status, endpoint)
                        raise error_type(f"FACEIT returned HTTP {status}", status=status, endpoint=endpoint)
                    else:
                        try:
                            payload = await response.json()
                        except (aiohttp.ContentTypeError, ValueError) as exc:
                            logger.error("Invalid JSON response from FACEIT endpoint %s", endpoint)
                            raise FaceitInvalidResponseError(
                                "FACEIT returned invalid JSON", status=status, endpoint=endpoint
                            ) from exc
                        if not isinstance(payload, dict):
                            raise FaceitInvalidResponseError(
                                "FACEIT returned an unexpected JSON shape", status=status, endpoint=endpoint
                            )
                        return payload
            except (FaceitAPIError, FaceitInvalidResponseError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.error("FACEIT network error for %s (%s)", endpoint, type(exc).__name__)
                raise FaceitNetworkError(
                    f"FACEIT request failed ({type(exc).__name__})", endpoint=endpoint
                ) from exc

            await asyncio.sleep(delay)

    @staticmethod
    def _retry_after(value: str | None) -> float:
        if not value:
            return 1.0
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_time = parsedate_to_datetime(value)
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_time - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 1.0
