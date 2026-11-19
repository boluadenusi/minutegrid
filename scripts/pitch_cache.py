"""Rate-limited, persistent PitchAPI responses for the mapping script."""

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

if __package__:
    from .probe_pitchapi import BASE_URL
else:
    from probe_pitchapi import BASE_URL


class PitchRequestError(RuntimeError):
    """A single API resource could not be retrieved."""


class PitchFatalError(RuntimeError):
    """An authentication or persistent server failure stops the run."""


class CachedPitchClient:
    def __init__(self, session, cache_dir, clock=time.monotonic, sleep=time.sleep, wall_clock=time.time):
        self.session = session
        self.session.mount("https://", HTTPAdapter(max_retries=0))
        self.cache_dir = Path(cache_dir)
        self.clock = clock
        self.sleep = sleep
        self.wall_clock = wall_clock
        self.next_request = 0.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, path):
        return self.cache_dir / (hashlib.sha256(path.encode("utf-8")).hexdigest() + ".json")

    def cached_at(self, path):
        """Wall-clock time the cached response was written, or None."""
        cache_path = self.cache_path(path)
        return cache_path.stat().st_mtime if cache_path.exists() else None

    def get(self, path, *, skip_unavailable_profile=False, refresh=False):
        """refresh=True ignores a cached response and requests (and re-caches) it."""
        key = self.session.headers.get("X-API-KEY")
        if key and key in path:
            raise RuntimeError("Request path contains the API key")
        cache_path = self.cache_path(path)
        attempt = 0
        if cache_path.exists() and not refresh:
            with cache_path.open(encoding="utf-8") as file:
                cached = json.load(file)
            if cached["path"] != path:
                raise RuntimeError(f"Cache path mismatch: {cache_path}")
            attempt = cached.get("attempts", 0)
            if skip_unavailable_profile and cached["status"] in (403, 404):
                if cached.get("retry_at") is not None:
                    cached.pop("retry_at")
                    self._save(cache_path, cached)
                return self._result(path, cached["status"], cached["body"], True)
            if cached.get("retry_at") is None:
                return self._result(path, cached["status"], cached["body"], skip_unavailable_profile)
            delay = cached["retry_at"] - self.wall_clock()
            if delay > 0:
                self.sleep(delay)

        while attempt < 6:
            delay = self.next_request - self.clock()
            if delay > 0:
                self.sleep(delay)
            self.next_request = self.clock() + 0.2
            try:
                response = self.session.get(BASE_URL + path, timeout=30, allow_redirects=False)
            except requests.RequestException as error:
                raise PitchRequestError(f"PitchAPI request failed for {path}: {type(error).__name__}") from None
            status = response.status_code
            body = response.text
            if key and key in body:
                raise RuntimeError(f"PitchAPI response for {path} contains the API key; refusing to cache it")
            attempt += 1
            if skip_unavailable_profile and status in (403, 404):
                self._save(cache_path, {"path": path, "status": status, "body": body, "attempts": attempt})
                return self._result(path, status, body, True)
            if (status in (403, 429) or 500 <= status <= 599) and attempt <= 5:
                if status == 403:
                    wait = 60.0
                else:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is None:
                        wait = 60.0 if status == 429 else float(2 ** (attempt - 1))
                    else:
                        try:
                            wait = max(0.0, float(retry_after))
                        except ValueError:
                            retry_date = parsedate_to_datetime(retry_after)
                            if retry_date.tzinfo is None:
                                retry_date = retry_date.replace(tzinfo=timezone.utc)
                            wait = max(0.0, (retry_date - datetime.now(timezone.utc)).total_seconds())
                self._save(cache_path, {
                    "path": path, "status": status, "body": body,
                    "attempts": attempt, "retry_at": self.wall_clock() + wait,
                })
                print(f"PitchAPI HTTP {status} for {path}; retry {attempt}/5 after {wait:g}s", flush=True)
                self.sleep(wait)
                continue
            self._save(cache_path, {"path": path, "status": status, "body": body, "attempts": attempt})
            return self._result(path, status, body, skip_unavailable_profile)
        raise RuntimeError(f"PitchAPI retry loop failed for {path}")

    def _save(self, cache_path, value):
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache_dir, delete=False) as file:
                temp_name = file.name
                json.dump(value, file, ensure_ascii=False)
            os.replace(temp_name, cache_path)
            temp_name = None
        finally:
            if temp_name is not None:
                Path(temp_name).unlink(missing_ok=True)

    @staticmethod
    def _result(path, status, body, skip_unavailable_profile):
        if status in (403, 404) and skip_unavailable_profile:
            print(f"Player profile unavailable {path}: HTTP {status}; no nationality", flush=True)
            return None
        if status == 401 or 500 <= status <= 599:
            raise PitchFatalError(f"PitchAPI returned HTTP {status} for {path}")
        if status != 200:
            raise PitchRequestError(f"PitchAPI returned HTTP {status} for {path}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise PitchRequestError(f"PitchAPI returned invalid JSON for {path}") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise PitchRequestError(f"PitchAPI returned an unexpected response for {path}")
        return payload["data"]
