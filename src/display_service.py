"""Render Pi-hole stats + 24h history to a Waveshare 2.13" V4 e-paper.

Layout (250x122, landscape, B/W):
  - 2x2 segregated stat grid in y=0..76
  - 24h chart strip in y=78..122
  - No header / branding (full real estate goes to numbers + chart)
"""

import datetime
import os
import sys
import logging
from PIL import Image, ImageDraw, ImageFont

if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

try:
    from waveshare_epd import epd2in13_V4
except (ImportError, RuntimeError, Exception) as e:  # noqa: BLE001
    print(f"Warning: waveshare_epd driver unavailable ({e}); using mock.")

    class _MockEPD:
        width = 122
        height = 250

        def init(self): pass
        def Clear(self, color): pass
        def display(self, image): pass
        def getbuffer(self, image): return []
        def sleep(self): pass

    class _MockModule:
        EPD = _MockEPD

    epd2in13_V4 = _MockModule()


logger = logging.getLogger(__name__)

ROW_H = 38           # half of 76 (grid region)
GRID_BOTTOM = 76
COL_X = 125          # vertical divider
CHART_TOP = 80

AXIS_LABELS = 6                       # HH markers along the x-axis
HOURS_PER_LABEL = 24 // AXIS_LABELS   # interval between labels
AXIS_HEIGHT = 10                      # px reserved for HH labels under the chart
AXIS_GAP = 2                          # px between chart bottom and label row

# Pi-hole returns 144 ten-minute buckets per 24h. We collapse three at a time
# into 48 thirty-minute buckets so each bar is wide enough (~5 px on a 250 px
# panel) for the hollow-outline-plus-filled-block overlay to actually read on
# a 1-bit display.
SRC_BUCKETS = 144
CHART_BUCKETS = 48
GROUP_SIZE = SRC_BUCKETS // CHART_BUCKETS


def _downsample(values, group_size):
    return [sum(values[i:i + group_size]) for i in range(0, len(values), group_size)]


class DisplayService:
    def __init__(self):
        self.epd = epd2in13_V4.EPD()
        self.epd.init()
        self.epd.Clear(0xFF)

        font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
        try:
            self.font_value = ImageFont.truetype(os.path.join(font_dir, "DejaVuSans-Bold.ttf"), 24)
            self.font_label = ImageFont.truetype(os.path.join(font_dir, "DejaVuSans.ttf"), 11)
            self.font_axis = ImageFont.truetype(os.path.join(font_dir, "DejaVuSans.ttf"), 9)
        except IOError:
            logger.warning("Fonts not found; using default bitmap font")
            self.font_value = ImageFont.load_default()
            self.font_label = ImageFont.load_default()
            self.font_axis = ImageFont.load_default()

    def render(self, summary, history):
        # Landscape: width = panel's long side, height = short side.
        width = self.epd.height
        height = self.epd.width

        image = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(image)

        self._draw_grid(draw, summary, width, height)
        self._draw_chart(draw, history, datetime.datetime.now(), width, height)

        # Match eink_weather: rotate 180 before pushing to the panel.
        image = image.rotate(180)
        self.epd.display(self.epd.getbuffer(image))
        image.save("last_display.png")
        return image

    def _draw_grid(self, draw, summary, width, height):
        # Horizontal divider between rows; vertical divider between columns.
        draw.line((0, ROW_H, width, ROW_H), fill=0)
        draw.line((COL_X, 4, COL_X, GRID_BOTTOM - 4), fill=0)

        cells = [
            (8,        2, f"{summary['ads_blocked']:,}",         "Ads blocked today"),
            (COL_X + 8, 2, f"{summary['dns_queries']:,}",         "DNS queries today"),
            (8,        ROW_H + 2, f"{summary['ads_percentage']:.2f}%", "Ad percentage"),
            (COL_X + 8, ROW_H + 2, f"{summary['devices']:,}",         "Devices protected"),
        ]
        for x, y, value, label in cells:
            draw.text((x, y), value, font=self.font_value, fill=0)
            # Label sits just below the value; pin it near the bottom of the cell.
            draw.text((x, y + ROW_H - 16), label, font=self.font_label, fill=0)

    def _draw_chart(self, draw, history, now, width, height):
        totals, blocked = history
        if not totals:
            return

        chart_bottom = height - 1 - AXIS_HEIGHT - AXIS_GAP
        chart_height = chart_bottom - CHART_TOP
        chart_width = width - 2

        totals = _downsample(totals[-SRC_BUCKETS:], GROUP_SIZE)
        blocked = _downsample(blocked[-SRC_BUCKETS:], GROUP_SIZE)
        n = len(totals)

        peak = max(totals) or 1
        scale = (chart_height - 1) / peak

        draw.line((0, CHART_TOP - 2, width, CHART_TOP - 2), fill=0)

        for i, (t, b) in enumerate(zip(totals, blocked)):
            x0 = 1 + (i * chart_width) // n
            x1 = 1 + ((i + 1) * chart_width) // n - 1
            if x1 < x0:
                x1 = x0
            t_h = int(round(t * scale))
            b_h = int(round(b * scale))
            if t_h <= 0 and b_h <= 0:
                continue
            t_top = chart_bottom - t_h
            b_top = chart_bottom - b_h
            if t_h > 0:
                draw.line((x0, t_top, x1, t_top), fill=0)
                draw.line((x0, t_top, x0, chart_bottom), fill=0)
                draw.line((x1, t_top, x1, chart_bottom), fill=0)
            if b_h > 0:
                draw.rectangle((x0, b_top, x1, chart_bottom), outline=0, fill=0)

        # HH labels along x-axis, rounded to nearest hour, evenly spaced.
        label_y = chart_bottom + AXIS_GAP
        for k in range(AXIS_LABELS):
            x_pos = 1 + (k * chart_width) // AXIS_LABELS
            hours_back = 24 - HOURS_PER_LABEL * k
            seg_time = (now
                        - datetime.timedelta(hours=hours_back)
                        + datetime.timedelta(minutes=30))
            draw.text((x_pos, label_y), f"{seg_time.hour:02d}",
                      font=self.font_axis, fill=0, anchor="lt")

    def sleep(self):
        try:
            self.epd.sleep()
        except Exception as e:  # noqa: BLE001
            logger.warning("EPD sleep failed: %s", e)

    def clear(self):
        self.epd.Clear(0xFF)
        self.epd.sleep()


if __name__ == "__main__":
    import random
    random.seed(7)

    stub_summary = {
        "ads_blocked": 20385,
        "dns_queries": 104730,
        "ads_percentage": 19.46,
        "devices": 34,
    }
    stub_totals = [random.randint(40, 800) for _ in range(144)]
    stub_blocked = [int(t * random.uniform(0.05, 0.45)) for t in stub_totals]

    ds = DisplayService()
    ds.render(stub_summary, (stub_totals, stub_blocked))
    ds.sleep()
    print("Saved last_display.png")
