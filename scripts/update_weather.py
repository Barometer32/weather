import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


STATIONS = ["KFCM", "KMIC", "KMSP"]

METAR_URL = "https://aviationweather.gov/api/data/metar"

OUTPUT_FILE = Path("/weather/data/current.json")

KNOTS_TO_MPH = 1.15078

LOCAL_TIMEZONE = ZoneInfo("America/Chicago")

VALID_MINUTE_START = 50
VALID_MINUTE_END = 59

HOURS_TO_DOWNLOAD = 18

HISTORY_HOURS = 13


def fahrenheit(celsius):
    return (celsius * 9 / 5) + 32


def round_half_up(value):
    if value is None:
        return None

    return int(math.floor(value + 0.5))


def wind_direction_name(degrees):
    directions = [
        "N",
        "NE",
        "E",
        "SE",
        "S",
        "SW",
        "W",
        "NW",
    ]

    index = int((degrees + 22.5) // 45) % 8

    return directions[index]


def get_metars():
    params = {
        "ids": ",".join(STATIONS),
        "format": "json",
        "hours": HOURS_TO_DOWNLOAD,
    }

    response = requests.get(
        METAR_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_observation_datetime(report):
    obs_time = report.get("obsTime")

    if obs_time is None:
        return None

    try:
        return datetime.fromtimestamp(
            float(obs_time),
            tz=timezone.utc,
        )

    except (
        TypeError,
        ValueError,
        OSError,
    ):
        return None


def is_valid_hourly_report(report):
    obs_datetime = get_observation_datetime(
        report
    )

    if obs_datetime is None:
        return False

    return (
        VALID_MINUTE_START
        <= obs_datetime.minute
        <= VALID_MINUTE_END
    )


def group_valid_reports_by_hour(data):
    hours = defaultdict(dict)

    for report in data:
        station = report.get("icaoId")

        if station not in STATIONS:
            continue

        if not is_valid_hourly_report(
            report
        ):
            continue

        obs_datetime = (
            get_observation_datetime(
                report
            )
        )

        hour_key = obs_datetime.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        existing = hours[hour_key].get(
            station
        )

        if existing is None:
            hours[hour_key][station] = (
                report
            )
            continue

        existing_time = (
            get_observation_datetime(
                existing
            )
        )

        if obs_datetime > existing_time:
            hours[hour_key][station] = (
                report
            )

    return hours


def calculate_temperature(reports):
    values = []

    for station in STATIONS:
        value = reports[station].get(
            "temp"
        )

        if value is None:
            return None

        values.append(
            fahrenheit(float(value))
        )

    return sum(values) / len(values)


def calculate_dewpoint(reports):
    values = []

    for station in STATIONS:
        value = reports[station].get(
            "dewp"
        )

        if value is None:
            return None

        values.append(
            fahrenheit(float(value))
        )

    return sum(values) / len(values)


def calculate_wind(reports):
    u_components = []
    v_components = []

    for station in STATIONS:
        report = reports[station]

        speed_knots = report.get(
            "wspd"
        )

        direction = report.get(
            "wdir"
        )

        if speed_knots is None:
            return None, None

        try:
            speed_knots = float(
                speed_knots
            )

        except (
            TypeError,
            ValueError,
        ):
            return None, None

        if speed_knots == 0:
            u_components.append(0.0)
            v_components.append(0.0)
            continue

        if direction is None:
            return None, None

        try:
            direction = float(
                direction
            )

        except (
            TypeError,
            ValueError,
        ):
            return None, None

        radians = math.radians(
            direction
        )

        u = (
            -speed_knots
            * math.sin(radians)
        )

        v = (
            -speed_knots
            * math.cos(radians)
        )

        u_components.append(u)
        v_components.append(v)

    average_u = (
        sum(u_components)
        / len(u_components)
    )

    average_v = (
        sum(v_components)
        / len(v_components)
    )

    speed_knots = math.sqrt(
        average_u ** 2
        + average_v ** 2
    )

    speed_mph = (
        speed_knots
        * KNOTS_TO_MPH
    )

    if speed_mph <= 3:
        return speed_mph, None

    direction = (
        math.degrees(
            math.atan2(
                -average_u,
                -average_v,
            )
        )
        + 360
    ) % 360

    return speed_mph, direction


def build_hour_record(
    display_hour_utc,
    reports,
):
    stations_present = sorted(
        reports.keys()
    )

    missing_stations = [
        station
        for station in STATIONS
        if station not in reports
    ]

    local_time = (
        display_hour_utc.astimezone(
            LOCAL_TIMEZONE
        )
    )

    record = {
        "hour_utc":
            display_hour_utc.isoformat(),

        "hour_local":
            local_time.isoformat(),

        "display_time":
            local_time.strftime(
                "%-I %p"
            ),

        "stations_present":
            stations_present,

        "missing_stations":
            missing_stations,
    }

    if missing_stations:
        record.update({
            "available": False,
            "status": "Unavailable",
            "temperature_f": None,
            "dewpoint_f": None,
            "wind": "Unavailable",
            "wind_speed_mph": None,
            "wind_direction": None,
        })

        return record

    temperature = (
        calculate_temperature(
            reports
        )
    )

    dewpoint = (
        calculate_dewpoint(
            reports
        )
    )

    wind_speed, wind_direction = (
        calculate_wind(
            reports
        )
    )

    if (
        temperature is None
        or dewpoint is None
        or wind_speed is None
    ):
        record.update({
            "available": False,
            "status": "Unavailable",
            "temperature_f": None,
            "dewpoint_f": None,
            "wind": "Unavailable",
            "wind_speed_mph": None,
            "wind_direction": None,
        })

        return record

    temperature_display = (
        round_half_up(
            temperature
        )
    )

    dewpoint_display = (
        round_half_up(
            dewpoint
        )
    )

    wind_speed_display = (
        round_half_up(
            wind_speed
        )
    )

    if wind_speed <= 3:
        wind_display = "Calm"
        wind_direction_display = None

    else:
        wind_direction_display = (
            wind_direction_name(
                wind_direction
            )
        )

        wind_display = (
            f"{wind_direction_display} "
            f"at {wind_speed_display} mph"
        )

    record.update({
        "available": True,
        "status": "Complete",

        "temperature_f":
            temperature_display,

        "dewpoint_f":
            dewpoint_display,

        "wind":
            wind_display,

        "wind_speed_mph":
            wind_speed_display,

        "wind_direction":
            wind_direction_display,
    })

    return record


def get_reports_for_display_hour(
    grouped_hours,
    display_hour,
):
    source_hour = (
        display_hour
        - timedelta(hours=1)
    )

    return grouped_hours.get(
        source_hour,
        {},
    )


def load_existing_output():
    if not OUTPUT_FILE.exists():
        return None

    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


def parse_hour_utc(hour_text):
    if not hour_text:
        return None

    try:
        value = datetime.fromisoformat(
            hour_text
        )

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def main():
    print(
        "Downloading METAR observations..."
    )

    raw_data = get_metars()

    grouped_hours = (
        group_valid_reports_by_hour(
            raw_data
        )
    )

    now_utc = datetime.now(
        timezone.utc
    )

    current_hour = now_utc.replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    current_reports = (
        get_reports_for_display_hour(
            grouped_hours,
            current_hour,
        )
    )

    candidate_current = (
        build_hour_record(
            current_hour,
            current_reports,
        )
    )

    existing_output = (
        load_existing_output()
    )

    if candidate_current["available"]:
        latest_verified = (
            candidate_current
        )

    else:
        latest_verified = None

        if existing_output:
            previous = (
                existing_output.get(
                    "current_conditions"
                )
            )

            if (
                previous
                and previous.get(
                    "available"
                )
            ):
                latest_verified = previous

        if latest_verified is None:
            latest_verified = (
                candidate_current
            )

    history_anchor = parse_hour_utc(
        latest_verified.get(
            "hour_utc"
        )
    )

    if history_anchor is None:
        history_anchor = current_hour

    history = []

    for hours_back in range(
        HISTORY_HOURS
    ):
        display_hour = (
            history_anchor
            - timedelta(
                hours=hours_back
            )
        )

        reports = (
            get_reports_for_display_hour(
                grouped_hours,
                display_hour,
            )
        )

        record = build_hour_record(
            display_hour,
            reports,
        )

        history.append(record)

    output = {
        "current_conditions":
            latest_verified,

        "history":
            history,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=4,
        )

    print()
    print(
        "Latest Verified Hour"
    )

    print(
        "--------------------"
    )

    if latest_verified.get(
        "available"
    ):
        print(
            f"Time: "
            f"{latest_verified['display_time']}"
        )

        print(
            f"Temperature: "
            f"{latest_verified['temperature_f']}°F"
        )

        print(
            f"Dew Point: "
            f"{latest_verified['dewpoint_f']}°F"
        )

        print(
            f"Wind: "
            f"{latest_verified['wind']}"
        )

    else:
        print(
            "No verified hour available."
        )

    print()
    print(
        f"History rows: "
        f"{len(history)}"
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
