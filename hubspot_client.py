"""
Thin HubSpot CRM v3 client.

Only two things are needed by this dashboard:

  1. list_properties(object_type)  -> every property with its internal name
                                      and its human label.
  2. count(object_type, groups)    -> the number of records matching a set of
                                      filters, read off the "total" field of a
                                      search response.

count() is the whole trick behind this dashboard. A search with limit=1 still
returns an accurate "total" for the full matching set, so a blank count for a
field costs exactly one API call no matter how many records are in the portal.
Nothing is ever paginated and no record data is downloaded.
"""

from __future__ import annotations

import threading
import time

import requests

BASE_URL = "https://api.hubapi.com"


class HubSpotError(RuntimeError):
    """Raised for any HubSpot response the app cannot recover from."""


class RateLimiter:
    """
    Minimum interval throttle, shared by every call made through one client.

    HubSpot's CRM Search API is capped at 5 requests per second at the account
    level, and that pool is shared across all search endpoints. Contacts and
    companies searches drain the same bucket, so the limiter sits on the
    client, not on the endpoint.
    """

    def __init__(self, rate_per_sec: float):
        self._min_interval = 1.0 / max(rate_per_sec, 0.1)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            gap = self._min_interval - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()


class HubSpotClient:
    def __init__(
        self,
        token: str,
        rate_per_sec: float = 3.0,
        timeout: int = 30,
        max_retries: int = 5,
    ):
        if not token or not token.strip():
            raise HubSpotError("No HubSpot token was supplied.")
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = RateLimiter(rate_per_sec)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # -- internals ---------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{BASE_URL}{path}"
        last_error = ""

        for attempt in range(self.max_retries):
            self.limiter.wait()
            try:
                resp = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
            except requests.RequestException as exc:
                last_error = f"network error: {exc}"
                if attempt == self.max_retries - 1:
                    break
                time.sleep(2**attempt)
                continue

            if resp.status_code == 429:
                # Honour Retry-After when HubSpot sends it, back off otherwise.
                try:
                    pause = float(resp.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    pause = 2**attempt
                time.sleep(min(max(pause, 1.0), 30.0))
                last_error = "rate limited (429)"
                continue

            if resp.status_code in (500, 502, 503, 504):
                last_error = f"HubSpot {resp.status_code}"
                time.sleep(2**attempt)
                continue

            if resp.status_code == 401:
                raise HubSpotError(
                    "HubSpot rejected the token (401). Check that the private "
                    "app access token is correct and has not been rotated."
                )

            if resp.status_code == 403:
                raise HubSpotError(
                    "HubSpot returned 403. The private app is missing a scope. "
                    "It needs crm.objects.contacts.read and crm.schemas.contacts.read "
                    "(plus the matching companies scopes if you re-enable companies "
                    "in config.OBJECTS)."
                )

            if not resp.ok:
                raise HubSpotError(
                    f"HubSpot {resp.status_code} on {path}: {resp.text[:400]}"
                )

            return resp.json()

        raise HubSpotError(
            f"Gave up on {path} after {self.max_retries} attempts. Last error: {last_error}"
        )

    # -- public ------------------------------------------------------------

    def list_properties(self, object_type: str) -> list[dict]:
        """
        Every property defined on the object, standard and custom.

        Returns the raw HubSpot payload trimmed to what the app uses:
        name, label, type, fieldType and (for dropdowns) the option values.
        """
        data = self._request("GET", f"/crm/v3/properties/{object_type}")
        out = []
        for prop in data.get("results", []):
            out.append(
                {
                    "name": prop.get("name", ""),
                    "label": prop.get("label", "") or prop.get("name", ""),
                    "type": prop.get("type", ""),
                    "fieldType": prop.get("fieldType", ""),
                    "group": prop.get("groupName", ""),
                    "options": [
                        o.get("value")
                        for o in (prop.get("options") or [])
                        if o.get("value") is not None
                    ][:200],
                }
            )
        return out

    def count(self, object_type: str, filter_groups: list | None = None) -> int:
        """
        Number of records matching filter_groups.

        filter_groups is HubSpot's OR-of-ANDs structure: groups are OR'd
        together, filters inside a group are AND'd. Pass None or [] to count
        every (non-archived) record on the object.
        """
        body = {
            "limit": 1,
            "properties": ["hs_object_id"],
            "filterGroups": filter_groups or [],
        }
        data = self._request(
            "POST", f"/crm/v3/objects/{object_type}/search", json=body
        )
        return int(data.get("total", 0))

    def ping(self) -> bool:
        """Cheap auth check used on startup."""
        self._request("GET", "/crm/v3/objects/contacts?limit=1")
        return True
