import json
import tempfile
import unittest
from pathlib import Path

from scripts.map_pitchapi import append_csv, read_csv
from scripts.pitch_cache import CachedPitchClient


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Response:
    def __init__(self, status, body='{"data": {}}', headers=None):
        self.status_code = status
        self.text = body
        self.headers = headers or {}


class Session:
    def __init__(self, responses, clock):
        self.headers = {"X-API-KEY": "test-key-not-in-responses"}
        self.responses = iter(responses)
        self.clock = clock
        self.times = []

    def mount(self, *_):
        pass

    def get(self, *_args, **_kwargs):
        self.times.append(self.clock.now)
        return next(self.responses)


class PitchCacheTest(unittest.TestCase):
    def test_cache_survives_a_new_client_and_limits_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(200), Response(200), Response(200)], clock)
            client = CachedPitchClient(session, directory, clock.monotonic, clock.sleep)
            for path in ("/one", "/two", "/three"):
                self.assertEqual(client.get(path), {})
            self.assertGreaterEqual(session.times[1] - session.times[0], 0.2)
            self.assertGreaterEqual(session.times[2] - session.times[1], 0.2)
            replay = Session([], clock)
            self.assertEqual(CachedPitchClient(replay, directory, clock.monotonic, clock.sleep).get("/one"), {})
            self.assertEqual(replay.times, [])

    def test_unavailable_profiles_are_not_retried_and_are_cached(self):
        for status in (403, 404):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                clock = Clock()
                session = Session([Response(status)], clock)
                client = CachedPitchClient(session, directory, clock.monotonic, clock.sleep)
                self.assertIsNone(client.get("/v1/players/p_1", skip_unavailable_profile=True))
                self.assertEqual(len(session.times), 1)
                self.assertEqual(clock.sleeps, [])
                replay = Session([], clock)
                self.assertIsNone(CachedPitchClient(replay, directory, clock.monotonic, clock.sleep).get(
                    "/v1/players/p_1", skip_unavailable_profile=True
                ))
                self.assertEqual(replay.times, [])

    def test_429_honors_retry_after(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(429, headers={"Retry-After": "4"}), Response(200)], clock)
            client = CachedPitchClient(session, directory, clock.monotonic, clock.sleep)
            self.assertEqual(client.get("/test"), {})
            self.assertIn(4.0, clock.sleeps)

    def test_interrupted_retry_resumes_from_cached_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(403)], clock)

            def interrupted_sleep(seconds):
                raise InterruptedError()

            client = CachedPitchClient(session, directory, clock.monotonic, interrupted_sleep, clock.monotonic)
            with self.assertRaises(InterruptedError):
                client.get("/v1/matches/m_1/events")
            resumed_session = Session([Response(200)], clock)
            resumed = CachedPitchClient(resumed_session, directory, clock.monotonic, clock.sleep, clock.monotonic)
            self.assertEqual(resumed.get("/v1/matches/m_1/events"), {})
            self.assertEqual(resumed_session.times, [60.0])

    def test_pending_profile_403_from_previous_run_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(403)], clock)
            def interrupted_sleep(_seconds):
                raise InterruptedError()
            client = CachedPitchClient(session, directory, clock.monotonic, interrupted_sleep, clock.monotonic)
            with self.assertRaises(InterruptedError):
                client.get("/v1/players/p_1")
            replay = Session([], clock)
            resumed = CachedPitchClient(replay, directory, clock.monotonic, clock.sleep, clock.monotonic)
            self.assertIsNone(resumed.get("/v1/players/p_1", skip_unavailable_profile=True))
            self.assertEqual(replay.times, [])
            self.assertEqual(clock.sleeps, [])

    def test_non_profile_forbidden_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(403)] * 6, clock)
            client = CachedPitchClient(session, directory, clock.monotonic, clock.sleep)
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                client.get("/v1/leagues")

    def test_secret_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            session = Session([Response(200, json.dumps({"data": {"key": "test-key-not-in-responses"}}))], clock)
            client = CachedPitchClient(session, directory, clock.monotonic, clock.sleep)
            with self.assertRaisesRegex(RuntimeError, "refusing to cache"):
                client.get("/test")
            self.assertEqual(list(Path(directory).iterdir()), [])


class ResumeOutputTest(unittest.TestCase):
    def test_existing_rows_are_preserved_and_only_new_rows_are_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.csv"
            fields = ["id", "value"]
            append_csv(path, fields, [{"id": "1", "value": "reviewed"}], ["id"])
            append_csv(path, fields, [{"id": "1", "value": "replacement"}, {"id": "2", "value": "new"}], ["id"])
            self.assertEqual(read_csv(path), [{"id": "1", "value": "reviewed"}, {"id": "2", "value": "new"}])


if __name__ == "__main__":
    unittest.main()
