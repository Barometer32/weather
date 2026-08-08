import json
import math
from datetime import datetime, timezone

import requests


STATIONS = ["KFCM", "KMIC", "KMSP"]

METAR_URL = "https://aviationweather.gov/api/data/metar"

OUTPUT_FILE = "/weather/data/current.json"

KNOTS_TO_MPH = 1.15078


def fahrenheit(celsius):
    return (celsius * 9 / 5) + 32


def wind_direction_name(degrees):
    directions = [
        "North",
        "Northeast",
        "East",
        "Southeast",
        "South",
        "Southwest",
        "West",
        "Northwest"
    ]

    index = round(degrees / 45) % 8
    return directions[index]


def get_metars():
    params = {
        "ids": ",".join(STATIONS),
        "format": "json",
        "hours": 2
    }

    response = requests.get(
        METAR_URL,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


def select_latest_station_reports(data):
    selected = {}

    for report in data:
        station = report.get("icaoId")

        if station not in STATIONS:
            continue

        observation_time = report.get("obsTime", 0)

        if (
            station not in selected
            or observation_time > selected[station].get("obsTime", 0)
        ):
            selected[station] = report

    return selected


def calculate_temperature(stations):
    temperatures = []

    for station in stations.values():
        temp_c = station.get("temp")

        if temp_c is not None:
            temperatures.append(
                fahrenheit(float(temp_c))
            )

    if not temperatures:
        return None

    return sum(temperatures) / len(temperatures)


def calculate_dewpoint(stations):
    dewpoints = []

    for station in stations.values():
        dew_c = station.get("dewp")

        if dew_c is not None:
            dewpoints.append(
                fahrenheit(float(dew_c))
            )

    if not dewpoints:
        return None

    return sum(dewpoints) / len(dewpoints)


def calculate_wind(stations):
    u_components = []
    v_components = []

    for station in stations.values():

        speed_knots = station.get("wspd")
        direction = station.get("wdir")

        if speed_knots is None:
            continue

        speed_knots = float(speed_knots)

        if speed_knots == 0:
            u_components.append(0)
            v_components.append(0)
            continue

        if direction is None:
            continue

        try:
            direction = float(direction)
        except (TypeError, ValueError):
            continue

        radians = math.radians(direction)

        u = -speed_knots * math.sin(radians)
        v = -speed_knots * math.cos(radians)

        u_components.append(u)
        v_components.append(v)

    if not u_components:
        return None, None

    average_u = sum(u_components) / len(u_components)
    average_v = sum(v_components) / len(v_components)

    speed_knots = math.sqrt(
        average_u ** 2 +
        average_v ** 2
    )

    speed_mph = speed_knots * KNOTS_TO_MPH

    direction = (
        math.degrees(
            math.atan2(
                -average_u,
                -average_v
            )
        )
        + 360
    ) % 360

    return speed_mph, direction


def main():

    print("Downloading METAR observations...")

    raw_data = get_metars()

    stations = select_latest_station_reports(raw_data)

    print(
        "Stations found:",
        ", ".join(sorted(stations.keys()))
    )

    temperature = calculate_temperature(stations)
    dewpoint = calculate_dewpoint(stations)
    wind_speed, wind_direction = calculate_wind(stations)

    if temperature is not None:
        temperature_display = round(temperature)
    else:
        temperature_display = None

    if dewpoint is not None:
        dewpoint_display = round(dewpoint)
    else:
        dewpoint_display = None

    if wind_speed is None:

        wind_display = "Unavailable"
        wind_speed_display = None
        wind_direction_display = None

    elif wind_speed <= 3:

        wind_display = "Calm"
        wind_speed_display = round(wind_speed)
        wind_direction_display = None

    else:

        wind_speed_display = round(wind_speed)

        wind_direction_display = wind_direction_name(
            wind_direction
        )

        wind_display = (
            f"{wind_direction_display} "
            f"at {wind_speed_display} mph"
        )

    station_output = {}

    for station_id, report in stations.items():

        station_output[station_id] = {

            "observation_time":
                report.get("reportTime")
                or report.get("obsTime"),

            "temperature_c":
                report.get("temp"),

            "dewpoint_c":
                report.get("dewp"),

            "wind_direction_degrees":
                report.get("wdir"),

            "wind_speed_knots":
                report.get("wspd"),

            "raw_metar":
                report.get("rawOb")
        }

    output = {

        "updated_utc":
            datetime.now(timezone.utc).isoformat(),

        "stations_used":
            sorted(stations.keys()),

        "current_conditions": {

            "temperature_f":
                temperature_display,

            "dewpoint_f":
                dewpoint_display,

            "wind":
                wind_display,

            "wind_speed_mph":
                wind_speed_display,

            "wind_direction":
                wind_direction_display
        },

        "stations":
            station_output
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4
        )

    print()
    print("Combined Current Conditions")
    print("---------------------------")
    print(f"Temperature: {temperature_display}°F")
    print(f"Dew Point: {dewpoint_display}°F")
    print(f"Wind: {wind_display}")

    print()
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
