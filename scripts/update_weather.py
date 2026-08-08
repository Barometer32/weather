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

HOURS_TO_DOWNLOAD = 15
HISTORY_HOURS = 12


def fahrenheit(celsius):
    return (celsius * 9 / 5) + 32


def round_half_up(value):
    if value is None:
        return None

    return int(math.floor(value + 0.5))


def wind_direction_name(degrees):
    directions = [
        "North",
        "Northeast",
        "East",
        "Southeast",
        "South",
        "Southwest",
        "West",
        "Northwest",
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

    except (TypeError, ValueError, OSError):
        return None


def is_valid_hourly_report(report):
    obs_datetime = get_observation_datetime(report)

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

        if not is_valid_hourly_report(report):
            continue

        obs_datetime = get_observation_datetime(report)

        hour_key = obs_datetime.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        existing = hours[hour_key].get(station)

        if existing is None:
            hours[hour_key][station] = report
            continue

        existing_time = get_observation_datetime(existing)

        if obs_datetime > existing_time:
            hours[hour_key][station] = report

    return hours


def calculate_temperature(reports):
    temperatures = []

    for station in STATIONS:
        temp_c = reports[station].get("temp")

        if temp_c is None:
            return None

        temperatures.append(
            fahrenheit(float(temp_c))
        )

    return sum(temperatures) / len(temperatures)


def calculate_dewpoint(reports):
    dewpoints = []

    for station in STATIONS:
        dew_c = reports[station].get("dewp")

        if dew_c is None:
            return None

        dewpoints.append(
            fahrenheit(float(dew_c))
        )

    return sum(dewpoints) / len(dewpoints)


def calculate_wind(reports):
    u_components = []
    v_components = []

    for station in STATIONS:
        report = reports[station]

        speed_knots = report.get("wspd")
        direction = report.get("wdir")

        if speed_knots is None:
            return None, None

        try:
            speed_knots = float(speed_knots)

        except (TypeError, ValueError):
            return None, None

        if speed_knots == 0:
            u_components.append(0.0)
            v_components.append(0.0)
            continue

        if direction is None:
            return None, None

        try:
            direction = float(direction)

        except (TypeError, ValueError):
            return None, None

        radians = math.radians(direction)

        u = -speed_knots * math.sin(radians)
        v = -speed_knots * math.cos(radians)

        u_components.append(u)
        v_components.append(v)

    average_u = sum(u_components) / len(u_components)
    average_v = sum(v_components) / len(v_components)

    speed_knots = math.sqrt(
        average_u ** 2
        + average_v ** 2
    )

    speed_mph = speed_knots * KNOTS_TO_MPH

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


def build_hour_record(display_hour_utc, reports):
    stations_present = sorted(reports.keys())

    missing_stations = [
        station
        for station in STATIONS
        if station not in reports
    ]

    display_hour_local = display_hour_utc.astimezone(
        LOCAL_TIMEZONE
    )

    base_record = {
        "hour_utc": display_hour_utc.isoformat(),
        "hour_local": display_hour_local.isoformat(),
        "display_time": display_hour_local.strftime("%-I %p"),
        "stations_present": stations_present,
        "missing_stations": missing_stations,
    }

    if missing_stations:
        base_record.update({
            "available": False,
            "status": "Unavailable",
            "temperature_f": None,
            "dewpoint_f": None,
            "wind": "Unavailable",
            "wind_speed_mph": None,
            "wind_direction": None,
        })

        return base_record

    temperature = calculate_temperature(reports)
    dewpoint = calculate_dewpoint(reports)
    wind_speed, wind_direction = calculate_wind(reports)

    if (
        temperature is None
        or dewpoint is None
        or wind_speed is None
    ):
        base_record.update({
            "available": False,
            "status": "Unavailable",
            "temperature_f": None,
            "dewpoint_f": None,
            "wind": "Unavailable",
            "wind_speed_mph": None,
            "wind_direction": None,
        })

        return base_record

    temperature_display = round_half_up(
        temperature
    )

    dewpoint_display = round_half_up(
        dewpoint
    )

    wind_speed_display = round_half_up(
        wind_speed
    )

    if wind_speed <= 3:
        wind_display = "Calm"
        wind_direction_display = None

    else:
        wind_direction_display = wind_direction_name(
            wind_direction
        )

        wind_display = (
            f"{wind_direction_display} "
            f"at {wind_speed_display} mph"
        )

    base_record.update({
        "available": True,
        "status": "Complete",
        "temperature_f": temperature_display,
        "dewpoint_f": dewpoint_display,
        "wind": wind_display,
        "wind_speed_mph": wind_speed_display,
        "wind_direction": wind_direction_display,
    })

    return base_record


def build_station_details(reports):
    station_output = {}

    for station in STATIONS:
        report = reports.get(station)

        if report is None:
            station_output[station] = {
                "available": False
            }
            continue

        obs_datetime = get_observation_datetime(
            report
        )

        station_output[station] = {
            "available": True,

            "observation_time_utc":
                obs_datetime.isoformat()
                if obs_datetime
                else None,

            "observation_time_local":
                obs_datetime.astimezone(
                    LOCAL_TIMEZONE
                ).isoformat()
                if obs_datetime
                else None,

            "temperature_c":
                report.get("temp"),

            "dewpoint_c":
                report.get("dewp"),

            "wind_direction_degrees":
                report.get("wdir"),

            "wind_speed_knots":
                report.get("wspd"),

            "raw_metar":
                report.get("rawOb"),
        }

    return station_output


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


def main():
    print(
        "Downloading METAR observations..."
    )

    raw_data = get_metars()

    grouped_hours = group_valid_reports_by_hour(
        raw_data
    )

    now_utc = datetime.now(
        timezone.utc
    )

    current_top_hour = now_utc.replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    history = []

    for hours_back in range(
        HISTORY_HOURS
    ):
        display_hour = (
            current_top_hour
            - timedelta(
                hours=hours_back
            )
        )

        source_hour = (
            display_hour
            - timedelta(hours=1)
        )

        reports = grouped_hours.get(
            source_hour,
            {},
        )

        record = build_hour_record(
            display_hour,
            reports,
        )

        history.append(record)

    candidate_current = history[0]

    current_source_hour = (
        current_top_hour
        - timedelta(hours=1)
    )

    current_reports = grouped_hours.get(
        current_source_hour,
        {},
    )

    missing_stations = [
        station
        for station in STATIONS
        if station not in current_reports
    ]

    existing_output = load_existing_output()

    if candidate_current["available"]:
        current_to_publish = (
            candidate_current
        )

        stations_to_publish = (
            build_station_details(
                current_reports
            )
        )

        quality = {
            "ok": True,

            "all_stations_present": True,

            "valid_minute_window":
                f"{VALID_MINUTE_START:02d}-"
                f"{VALID_MINUTE_END:02d}",

            "stations_required":
                STATIONS,

            "stations_present":
                sorted(
                    current_reports.keys()
                ),

            "missing_stations":
                [],

            "message":
                "All 3 stations verified",

            "new_hour_ready": True,
        }

    else:
        if (
            existing_output
            and existing_output.get(
                "current_conditions"
            )
            and existing_output[
                "current_conditions"
            ].get(
                "available"
            )
        ):
            current_to_publish = (
                existing_output[
                    "current_conditions"
                ]
            )

            stations_to_publish = (
                existing_output.get(
                    "stations",
                    {},
                )
            )

        else:
            current_to_publish = (
                candidate_current
            )

            stations_to_publish = (
                build_station_details(
                    current_reports
                )
            )

        quality = {
            "ok":
                current_to_publish.get(
                    "available",
                    False,
                ),

            "all_stations_present":
                False,

            "valid_minute_window":
                f"{VALID_MINUTE_START:02d}-"
                f"{VALID_MINUTE_END:02d}",

            "stations_required":
                STATIONS,

            "stations_present":
                sorted(
                    current_reports.keys()
                ),

            "missing_stations":
                missing_stations,

            "message":
                "Waiting for new hourly "
                "METAR set",

            "new_hour_ready":
                False,
        }

    output = {
        "current_conditions":
            current_to_publish,

        "quality":
            quality,

        "stations":
            stations_to_publish,

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
        "Metro Current Conditions"
    )

    print(
        "------------------------"
    )

    print(
        f"Showing: "
        f"{current_to_publish['display_time']}"
    )

    if current_to_publish.get(
        "available"
    ):
        print(
            f"Temperature: "
            f"{current_to_publish['temperature_f']}°F"
        )

        print(
            f"Dew Point: "
            f"{current_to_publish['dewpoint_f']}°F"
        )

        print(
            f"Wind: "
            f"{current_to_publish['wind']}"
        )

    else:
        print(
            "Conditions: Unavailable"
        )

    if candidate_current["available"]:
        print(
            "New hourly observation: READY"
        )

    else:
        print(
            "New hourly observation: WAITING"
        )

        print(
            "Missing:",
            ", ".join(
                missing_stations
            )
            or "none",
        )

    print()
    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
