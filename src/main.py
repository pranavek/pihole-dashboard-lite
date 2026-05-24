"""One-shot dashboard refresh. Cron drives the cadence (every 15 minutes)."""

import json
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

try:
    from src.pihole_service import PiholeService
    from src.display_service import DisplayService
except ImportError:
    from pihole_service import PiholeService
    from display_service import DisplayService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("pihole-dashboard")


def load_config():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "config.json")) as f:
        return json.load(f)


def main():
    cfg = load_config()
    pihole = PiholeService(cfg["pihole"]["base_url"], cfg["pihole"]["password"])
    display = DisplayService()
    try:
        pihole.login()
        summary = pihole.get_summary()
        logger.info("Summary: %s", summary)
        history = pihole.get_history()
        logger.info("History buckets: %d", len(history[0]))
        display.render(summary, history)
    finally:
        pihole.logout()
        display.sleep()


if __name__ == "__main__":
    main()
