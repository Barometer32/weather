import fcntl
import subprocess
import sys
from pathlib import Path


WEATHER_DIR = Path("/weather")

PYTHON = (
    WEATHER_DIR
    / ".venv"
    / "bin"
    / "python"
)

SCRIPTS_DIR = (
    WEATHER_DIR
    / "scripts"
)

LOCK_FILE = Path(
    "/tmp/weather-update.lock"
)


COLLECTORS = [
    SCRIPTS_DIR
    / "update_weather.py",
]


def run_collector(script):
    print()
    print(
        f"Running {script.name}..."
    )

    result = subprocess.run(
        [
            str(PYTHON),
            str(script),
        ],
        cwd=WEATHER_DIR,
    )

    if result.returncode != 0:
        print(
            f"{script.name} failed "
            f"with return code "
            f"{result.returncode}"
        )

        return False

    print(
        f"{script.name} completed."
    )

    return True


def publish_changes():
    print()
    print(
        "Checking published "
        "weather data..."
    )

    subprocess.run(
        [
            "git",
            "add",
            "data/",
        ],
        cwd=WEATHER_DIR,
        check=True,
    )

    diff_result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
        ],
        cwd=WEATHER_DIR,
    )

    if diff_result.returncode == 0:
        print(
            "No published weather "
            "data changed."
        )

        print(
            "Nothing to push."
        )

        return False

    print(
        "Weather data changed."
    )

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "Update weather data",
        ],
        cwd=WEATHER_DIR,
        check=True,
    )

    print(
        "Pushing changes "
        "to GitHub..."
    )

    subprocess.run(
        [
            "git",
            "push",
            "origin",
            "main",
        ],
        cwd=WEATHER_DIR,
        check=True,
    )

    print(
        "GitHub update complete."
    )

    return True


def main():
    lock_handle = open(
        LOCK_FILE,
        "w",
    )

    try:
        fcntl.flock(
            lock_handle,
            fcntl.LOCK_EX
            | fcntl.LOCK_NB,
        )

    except BlockingIOError:
        print(
            "Another weather update "
            "is already running."
        )

        return

    print()
    print(
        "================================"
    )

    print(
        "Starting weather data update"
    )

    print(
        "================================"
    )

    failures = []

    for collector in COLLECTORS:
        if not collector.exists():
            print(
                f"Collector missing: "
                f"{collector}"
            )

            failures.append(
                collector.name
            )

            continue

        success = run_collector(
            collector
        )

        if not success:
            failures.append(
                collector.name
            )

    if failures:
        print()
        print(
            "Collector problems:"
        )

        for failure in failures:
            print(
                f"  {failure}"
            )

    try:
        publish_changes()

    except subprocess.CalledProcessError as error:
        print()
        print(
            "Git publishing failed."
        )

        print(
            f"Return code: "
            f"{error.returncode}"
        )

        sys.exit(
            error.returncode
        )

    print()
    print(
        "Update cycle complete."
    )


if __name__ == "__main__":
    main()
