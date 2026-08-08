<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Metro Weather</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: #edf1f5;
            font-family: Arial, Helvetica, sans-serif;
            color: #20252a;
        }

        .page {
            max-width: 1000px;
            margin: 0 auto;
            padding: 12px;
        }

        .section {
            background: white;
            border: 1px solid #d9dee4;
            border-radius: 8px;
            overflow: hidden;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: #f6f8fa;
            border-bottom: 1px solid #e1e5e9;
        }

        .section-title {
            font-size: 18px;
            font-weight: bold;
        }

        .section-subtitle {
            color: #6e747a;
            font-size: 12px;
            margin-top: 2px;
        }

        .status {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: bold;
        }

        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #1ba64b;
        }

        .history-wrapper {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: #f7f8fa;
            color: #61676d;
            font-size: 11px;
            text-align: left;
            padding: 7px 9px;
            border-bottom: 1px solid #dfe3e7;
        }

        td {
            padding: 8px 9px;
            border-bottom: 1px solid #eceff1;
            font-size: 13px;
        }

        tr:last-child td {
            border-bottom: none;
        }

        .history-time {
            font-weight: bold;
            white-space: nowrap;
        }

        .latest-row {
            background: #f7fbff;
        }

        .small-green-dot,
        .small-red-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }

        .small-green-dot {
            background: #1ba64b;
        }

        .small-red-dot {
            background: #d93025;
        }

        .unavailable {
            color: #b3261e;
        }

        @media (max-width: 600px) {

            .page {
                padding: 6px;
            }

            .section {
                border-radius: 6px;
            }

            .section-header {
                padding: 8px 9px;
            }

            .section-title {
                font-size: 16px;
            }

            .section-subtitle {
                font-size: 10px;
            }

            .status {
                font-size: 10px;
            }

            table {
                min-width: 410px;
            }

            th {
                font-size: 9px;
                padding: 6px 7px;
            }

            td {
                font-size: 11px;
                padding: 7px;
            }
        }

    </style>

</head>


<body>

<div class="page">

    <section class="section">

        <div class="section-header">

            <div>

                <div class="section-title">
                    Last 13 Hours
                </div>

                <div class="section-subtitle">
                    Combined KFCM • KMIC • KMSP
                </div>

            </div>


            <div class="status">

                <span class="status-dot"></span>

                <span id="latestStatus">
                    Loading
                </span>

            </div>

        </div>


        <div class="history-wrapper">

            <table>

                <thead>

                    <tr>
                        <th>Time</th>
                        <th>Temp</th>
                        <th>Dew</th>
                        <th>Wind</th>
                        <th>Status</th>
                    </tr>

                </thead>


                <tbody id="historyBody">
                </tbody>

            </table>

        </div>

    </section>

</div>


<script>

async function loadWeather() {

    try {

        const response = await fetch(
            "data/current.json?t="
            + Date.now()
        );

        if (!response.ok) {

            throw new Error(
                "Unable to load weather data"
            );

        }

        const data =
            await response.json();

        displayHistory(data);

    }

    catch (error) {

        document.getElementById(
            "latestStatus"
        ).textContent =
            "Unavailable";

        console.error(error);

    }

}


function displayHistory(data) {

    const body =
        document.getElementById(
            "historyBody"
        );

    body.innerHTML = "";


    data.history.forEach(
        function(hour, index) {

            const row =
                document.createElement(
                    "tr"
                );


            if (index === 0) {

                row.classList.add(
                    "latest-row"
                );

            }


            if (hour.available) {

                row.innerHTML =

                    "<td class='history-time'>"
                    + hour.display_time
                    + "</td>"

                    + "<td>"
                    + hour.temperature_f
                    + "°"
                    + "</td>"

                    + "<td>"
                    + hour.dewpoint_f
                    + "°"
                    + "</td>"

                    + "<td>"
                    + hour.wind
                    + "</td>"

                    + "<td>"
                    + "<span class='small-green-dot'></span>"
                    + "OK"
                    + "</td>";

            }

            else {

                row.innerHTML =

                    "<td class='history-time'>"
                    + hour.display_time
                    + "</td>"

                    + "<td>—</td>"

                    + "<td>—</td>"

                    + "<td class='unavailable'>"
                    + "Unavailable"
                    + "</td>"

                    + "<td class='unavailable'>"
                    + "<span class='small-red-dot'></span>"
                    + "Unavailable"
                    + "</td>";

            }


            body.appendChild(
                row
            );

        }
    );


    if (
        data.history.length > 0
        && data.history[0].available
    ) {

        document.getElementById(
            "latestStatus"
        ).textContent =
            "Latest: "
            + data.history[0].display_time;

    }

    else {

        document.getElementById(
            "latestStatus"
        ).textContent =
            "Data unavailable";

    }

}


loadWeather();

</script>


</body>

</html>
