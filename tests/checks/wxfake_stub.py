"""Подмена сетевого слоя Open-Meteo рядами той же формы."""
from datetime import datetime, timedelta, timezone

from bot.services import weather

START = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
HOURS = 24 * 7
TIMES = [(START + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(HOURS)]


async def fake_get(client, url, params):
    if "marine" in url:
        return {"hourly": {"time": TIMES,
                           "wave_height": [round(1.0 + (h % 24) * 0.1, 1) for h in range(HOURS)],
                           "wave_direction": [210] * HOURS,
                           "wave_period": [7.5] * HOURS,
                           "swell_wave_height": [0.8] * HOURS,
                           "swell_wave_period": [9.0] * HOURS}}
    if "geocoding" in url:
        return {"results": [{"name": "Ushuaia", "country": "Аргентина",
                             "latitude": -54.8, "longitude": -68.3}]}
    return {"hourly": {"time": TIMES,
                       "wind_speed_10m": [10 + (h % 48) for h in range(HOURS)],
                       "wind_gusts_10m": [15 + (h % 48) for h in range(HOURS)],
                       "wind_direction_10m": [270] * HOURS,
                       "pressure_msl": [1013.2] * HOURS,
                       "visibility": [18520] * HOURS,
                       "precipitation": [0.0] * HOURS,
                       "temperature_2m": [21.4] * HOURS}}


weather._get = fake_get
