import os
import requests
import datetime
import json

CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["STRAVA_REFRESH_TOKEN"]

def refresh_access_token():
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    return response.json()["access_token"]

def get_year_distance(access_token):
    year_start = datetime.datetime(datetime.datetime.now().year, 1, 1)
    after = int(year_start.timestamp())

    total_meters = 0
    page = 1

    while True:
        r = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "per_page": 200, "page": page},
        )
        activities = r.json()
        if not activities:
            break

        for a in activities:
            total_meters += a["distance"]

        page += 1

    return round(total_meters / 1000, 1)

def main():
    token = refresh_access_token()
    km = get_year_distance(token)

    data = {
        "athlete": "Thibault Schrepel",
        "year": datetime.datetime.now().year,
        "distance_km": km,
        "last_updated": datetime.date.today().isoformat(),
    }

    with open("strava.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
