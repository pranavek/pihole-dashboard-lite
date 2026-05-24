# Pi-hole Dashboard Lite

Pi-hole stats on a Waveshare 2.13" V4 e-paper display, refreshed by cron every
15 minutes.

## What it shows

- Ads blocked today
- DNS queries today
- Ad percentage
- Devices protected (clients active in the last 24h)
- 24h queries-vs-blocked bar chart

Layout: a 2×2 segregated stat grid on top, full-width 24h chart at the bottom.

## Hardware

- Raspberry Pi with SPI enabled (any model with GPIO).
- Waveshare 2.13" e-Paper Display **V4** (B/W). Driver: `epd2in13_V4` (bundled).

## Software

- Python 3.9+
- Pi-hole v6+ (REST API at `/api/`). Generate an *app password* in the Pi-hole
  web UI: `Settings → API → Configure app password`.

## Install

```bash
git clone https://github.com/pranavek/pihole-dashboard-lite
cd pihole-dashboard-lite
pip3 install -r requirements.txt
```

Edit `config.json`:

```json
{
  "pihole": {
    "base_url": "http://pi.hole",
    "password": "YOUR_APP_PASSWORD"
  }
}
```

## Run

One-shot (cron does the looping):

```bash
python3 src/main.py
```

Install the cron entry:

```bash
crontab pihole-stats.cron
```

This adds:

```cron
*/15 * * * * /usr/bin/python3 /home/pi/pihole-dashboard-lite/src/main.py >> /var/log/pihole-dashboard.log 2>&1
```

Adjust the path if you cloned elsewhere.

## Offline preview

`src/display_service.py` runs standalone with stub data and writes
`last_display.png` — useful for laying out without a Pi attached. The mock EPD
kicks in automatically when the `waveshare_epd` driver can't load.

```bash
python3 src/display_service.py
```

## Project layout

```
pihole-dashboard-lite/
├── src/
│   ├── main.py              # cron entry point
│   ├── pihole_service.py    # v6 REST client (auth → summary + history)
│   └── display_service.py   # 250×122 B/W renderer
├── lib/waveshare_epd/       # bundled hardware driver
├── fonts/                   # Montserrat
├── config.json              # base_url + app password
├── requirements.txt
├── pihole-stats.cron
└── README.md
```
