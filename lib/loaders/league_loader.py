import json
import requests

# requires pandas sqlalchemy psycopg2

url = "https://v3.football.api-sports.io/leagues"

payload={}
headers = {
  'x-rapidapi-key': '239914f6f4ac5f34465c14dcdb26437f',
  'x-rapidapi-host': 'v3.football.api-sports.io'
}

response = requests.request("GET", url, headers=headers, data=payload)
jsonData = response.json()

# Load the JSON string into a Python dictionary
data = jsonData['response']

# transform the response data into what we need
leagues = []
for r in data:
    league = r['league']
    countryCode = r['country']['code']
    if(countryCode==None):
        countryCode = r['country']['name']
    league['country_code'] = countryCode
    leagues.append(league)

import pandas as pd

df = pd.DataFrame(leagues)

from sqlalchemy import create_engine, MetaData, Table

engine = create_engine("postgresql+psycopg2://postgres:aaa@localhost:5432/sports")
df.rename(columns={"id": "league_id"}, inplace=True)
df.rename(columns={"name": "league_name"}, inplace=True)
df.rename(columns={"type": "league_type"}, inplace=True)
df.rename(columns={"logo": "logo_url"}, inplace=True)
# df.to_sql( schema='sfn', name="country", con=engine, index=False, if_exists="append")


conn = engine.connect()
metadata = MetaData(schema='sfn')
table = Table("league", metadata, schema="sfn", autoload_with=engine)

# Step 3: Perform UPSERT for each row
from sqlalchemy.dialects.postgresql import insert

for _, row in df.iterrows():
    stmt = insert(table).values(row.to_dict())
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["league_id"],
        set_={
            "league_name": stmt.excluded.league_name,
            "league_type": stmt.excluded.league_type,
            'logo_url': stmt.excluded.logo_url
        }
    )
    conn.execute(upsert_stmt)
conn.commit()
conn.close()
print("✅ Upsert complete into sfn.league.")

print('Done.')
