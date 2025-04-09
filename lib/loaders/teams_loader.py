import json
from time import sleep
from typing import Dict

import psycopg2
import requests

# requires pandas sqlalchemy psycopg2

def loadCountryLookup():
    # Connect to PostgreSQL
    connection = psycopg2.connect(
        host="localhost",
        database="sports",
        user="sports_reader",
        password="aaa"
    )

    cursor = connection.cursor()

    # Query the country table
    cursor.execute("SELECT country_name, country_code FROM sfn.country")

    # Build the lookup dictionary
    countryLookup = {row[0]: row[1] for row in cursor.fetchall()}

    # Cleanup
    cursor.close()
    connection.close()

    return countryLookup

def loadTeams(leagueId: int, season: int):

    url = "https://v3.football.api-sports.io/teams"

    payload={}
    headers = {
      'x-rapidapi-key': '239914f6f4ac5f34465c14dcdb26437f',
      'x-rapidapi-host': 'v3.football.api-sports.io'
    }

    # Define the query parameters
    params = {
        "season": season,
        "league": leagueId
    }

    response = requests.request("GET", url, headers=headers, data=payload, params=params)
    jsonData = response.json()

    # Load the JSON string into a Python dictionary
    data = jsonData['response']

    if(len(data)==0):
        print('No data found. Skipping.')
        return

    # transform the response data into what we need
    teams = []
    for r in data:
        team = r['team']
        teams.append(team)

    import pandas as pd

    df = pd.DataFrame(teams)

    from sqlalchemy import create_engine, MetaData, Table

    engine = create_engine("postgresql+psycopg2://postgres:aaa@localhost:5432/sports")
    df.rename(columns={"id": "team_id"}, inplace=True)
    df.rename(columns={"name": "team_name"}, inplace=True)

    df.rename(columns={"founded": "year_founded"}, inplace=True)
    df["year_founded"] = df["year_founded"].astype("Int64")  # nullable integer, capital "I". Will be written as db null

    df.rename(columns={"national": "is_national"}, inplace=True)
    df.rename(columns={"logo": "logo_url"}, inplace=True)
    # df.to_sql( schema='sfn', name="country", con=engine, index=False, if_exists="append")

    # Look up country code by country name
    #df['country_code'] = df['country'].apply(getContinentByCountryCode)

    # Map country names to country codes
    countryLookup = loadCountryLookup()
    df["country_code"] = df["country"].map(countryLookup)
    df.drop(columns=["country"], inplace=True)

    conn = engine.connect()
    metadata = MetaData(schema='sfn')
    table = Table("team", metadata, schema="sfn", autoload_with=engine)

    # Step 3: Perform UPSERT for each row
    from sqlalchemy.dialects.postgresql import insert

    for _, row in df.iterrows():
        stmt = insert(table).values(row.to_dict())
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["team_id"],
            set_={
                "team_name": stmt.excluded.team_name,
                "code": stmt.excluded.code,
                "country_code": stmt.excluded.country_code,
                "year_founded": stmt.excluded.year_founded,
                "is_national": stmt.excluded.is_national,
                'logo_url': stmt.excluded.logo_url
            }
        )
        conn.execute(upsert_stmt)
    conn.commit()
    conn.close()
    print("✅ Upsert complete into sfn.team.")

    print('Done.')

def loadLeaguesInCountry(countryCode: str)->Dict:

    # Connect to PostgreSQL
    connection = psycopg2.connect(
        host="localhost",
        database="sports",
        user="sports_reader",
        password="aaa"
    )

    cursor = connection.cursor()

    # Query the country table
    cursor.execute(''' SELECT league_name, league_id
                        FROM sfn.league l, sfn.country c
                        WHERE   l.country_code = c.country_code
                                AND c.country_code = %s ''', (countryCode,))

    # Build the dictionary
    leagues = {row[0]: row[1] for row in cursor.fetchall()}

    # Cleanup
    cursor.close()
    connection.close()

    return leagues


leagues = loadLeaguesInCountry('GB-ENG')

season = 2024
for x in leagues:
    leagueName = x
    leagueId = leagues[leagueName]
    print(f'Loading teams in {leagueName} for season {season}...')
    loadTeams(leagueId, season)
    sleep(10)
