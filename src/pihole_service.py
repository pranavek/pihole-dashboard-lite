"""Pi-hole v6 REST API client.

Session-based auth: POST {base}/api/auth with the app password to obtain a
SID, then pass `sid=...` on subsequent calls. DELETE /api/auth on teardown.
"""

import logging
import requests

logger = logging.getLogger(__name__)


class PiholeError(RuntimeError):
    pass


class PiholeService:
    def __init__(self, base_url, password, timeout=5):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.sid = None
        self.session = requests.Session()

    def login(self):
        url = f"{self.base_url}/api/auth"
        resp = self.session.post(url, json={"password": self.password}, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        session = body.get("session") or {}
        if not session.get("valid"):
            raise PiholeError(f"Auth rejected: {body}")
        self.sid = session["sid"]
        # Newer Pi-hole v6 builds dropped the ?sid= query param; carry the SID
        # via both the cookie jar and the X-FTL-SID header for compatibility.
        self.session.cookies.set("sid", self.sid)
        self.session.headers.update({"X-FTL-SID": self.sid})
        logger.info("Authenticated with Pi-hole")

    def logout(self):
        if not self.sid:
            return
        try:
            self.session.delete(f"{self.base_url}/api/auth", timeout=self.timeout)
        except requests.RequestException as e:
            logger.warning("Logout failed (ignored): %s", e)
        finally:
            self.sid = None

    def _get(self, path):
        if not self.sid:
            self.login()
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_summary(self):
        """Return flat dict with the four display stats."""
        body = self._get("/api/stats/summary")
        queries = body.get("queries", {})
        clients = body.get("clients", {})
        return {
            "ads_blocked": int(queries.get("blocked", 0)),
            "dns_queries": int(queries.get("total", 0)),
            "ads_percentage": float(queries.get("percent_blocked", 0.0)),
            "devices": int(clients.get("active", 0)),
        }

    def get_history(self):
        """Return parallel lists of (total, blocked) 10-minute buckets over 24h."""
        body = self._get("/api/history")
        history = body.get("history", [])
        totals = [int(b.get("total", 0)) for b in history]
        blocked = [int(b.get("blocked", 0)) for b in history]
        return totals, blocked
