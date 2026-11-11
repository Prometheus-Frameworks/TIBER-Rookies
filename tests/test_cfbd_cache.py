import io
import json
import os
import unittest
from unittest.mock import patch

from scripts import cfbd_cache
from scripts.compute_breakout_age import fetch_roster


def _response(payload):
    resp = io.BytesIO(json.dumps(payload).encode())
    resp.__enter__ = lambda s=resp: s
    resp.__exit__ = lambda *a: False
    return resp


class CacheModuleTests(unittest.TestCase):
    URL = "https://api.collegefootballdata.com/roster?team=Ohio+State&year=2026"

    def test_miss_then_hit(self):
        self.assertIs(cfbd_cache.load(self.URL), cfbd_cache.MISS)
        cfbd_cache.store(self.URL, [{"id": 1}])
        self.assertEqual(cfbd_cache.load(self.URL), [{"id": 1}])

    def test_layout_by_year_and_endpoint_without_key(self):
        path = cfbd_cache.cache_path(self.URL)
        self.assertEqual(path.parent.parent.name, "2026")
        self.assertEqual(path.parent.name, "roster")
        with patch.dict(os.environ, {"CFBD_API_KEY": "secret-key"}):
            cfbd_cache.store(self.URL, [])
        self.assertNotIn("secret-key", path.read_text())

    def test_corrupt_file_is_a_miss(self):
        path = cfbd_cache.cache_path(self.URL)
        path.parent.mkdir(parents=True)
        path.write_text("{not json")
        self.assertIs(cfbd_cache.load(self.URL), cfbd_cache.MISS)


class FetchersUseCacheTests(unittest.TestCase):
    def test_roster_second_call_is_offline(self):
        with patch("urllib.request.urlopen", return_value=_response([{"id": 7}])) as net:
            self.assertEqual(fetch_roster("Ohio State", 2026), [{"id": 7}])
            self.assertEqual(fetch_roster("Ohio State", 2026), [{"id": 7}])
        self.assertEqual(net.call_count, 1)

    def test_failed_roster_is_not_cached(self):
        from urllib.error import URLError
        with patch("urllib.request.urlopen", side_effect=URLError("down")):
            self.assertEqual(fetch_roster("Ohio State", 2026), [])
        self.assertIs(cfbd_cache.load(cfbd_cache_url_roster()), cfbd_cache.MISS)

    def test_stats_category_cached(self):
        rows = [{"player": "A", "team": "B", "statType": "YDS", "stat": "1"}]
        with patch("scripts.compute_production_scores.urlopen", return_value=_response(rows)) as net:
            cfbd_cache.fetch_category(2026, "receiving")
            self.assertEqual(cfbd_cache.fetch_category(2026, "receiving"), rows)
        self.assertEqual(net.call_count, 1)


class PlaysAndTeamsCacheTests(unittest.TestCase):
    def test_plays_weeks_cached(self):
        from scripts import cfbd_plays
        with patch.object(cfbd_plays, "REQUEST_DELAY_S", 0), \
             patch("scripts.cfbd_plays.urlopen", side_effect=lambda *a, **k: _response([{"p": 1}])) as net:
            first = cfbd_plays.fetch_team_plays(2026, "Ohio State", "regular")
            second = cfbd_plays.fetch_team_plays(2026, "Ohio State", "regular")
        self.assertEqual(first, second)
        self.assertEqual(net.call_count, 18)  # weeks 1-18 once, second call fully offline

    def test_fbs_teams_cached(self):
        from scripts.discover_shadow_pool import fetch_fbs_teams
        with patch("scripts.discover_shadow_pool.urlopen",
                   return_value=_response([{"school": "Ohio State"}])) as net:
            fetch_fbs_teams(2026)
            self.assertEqual(fetch_fbs_teams(2026), ["Ohio State"])
        self.assertEqual(net.call_count, 1)


def cfbd_cache_url_roster():
    from scripts.compute_breakout_age import roster_url
    return roster_url("Ohio State", 2026)


if __name__ == "__main__":
    unittest.main()
