import json
import requests
import pycountry_convert as pc

# requires pandas sqlalchemy psycopg2 pycountry-convert

def getContinentByCountryCode(country_code: str)->str:
    try:
        # Convert country code to country alpha-2 if it's not already
        country_alpha2 = country_code.upper()

        if(country_alpha2.startswith('GB-')):
            country_alpha2 = 'GB'

        # Convert alpha-2 to continent code
        continent_code = pc.country_alpha2_to_continent_code(country_alpha2)

        # Convert continent code to full continent name
        continent_name = pc.convert_continent_code_to_continent_name(continent_code)

        return continent_name
    except Exception as e:
        return None
        #raise e
        #return f"Error: {str(e)}"

def getContinentByCountryName(countryName: str)->str:
    try:
        # Convert country code to country alpha-2 if it's not already
        country_alpha2 = pc.country_name_to_country_alpha2(countryName)

        if(country_alpha2 is None):
            return None

        return getContinentByCountryCode(country_alpha2)
    except Exception as e:
        return None
        #raise e
        #return f"Error: {str(e)}"


url = "https://v3.football.api-sports.io/countries"

payload={}
headers = {
  'x-rapidapi-key': '239914f6f4ac5f34465c14dcdb26437f',
  'x-rapidapi-host': 'v3.football.api-sports.io'
}

response = requests.request("GET", url, headers=headers, data=payload)
jsonData = response.json()

# Load the JSON string into a Python dictionary
data = jsonData['response']

import pandas as pd

df = pd.DataFrame(data)

from sqlalchemy import create_engine, MetaData, Table

engine = create_engine("postgresql+psycopg2://postgres:aaa@localhost:5432/sports")
df.rename(columns={"code": "country_code"}, inplace=True)
df.rename(columns={"name": "country_name"}, inplace=True)
df.rename(columns={"flag": "flag_url"}, inplace=True)
# some rows will have a Null country code, such as "World"
df.loc[df["country_code"].isna(), "country_code"] = df["country_name"]

# Look up continents by country code
df['continent'] = df['country_code'].apply(getContinentByCountryCode)

# Then fill missing values by trying the country name
df['continent'] = df.apply(
    lambda row: row['continent'] if pd.notnull(row['continent']) else getContinentByCountryName(row['country_name']),
    axis=1
)

# df.to_sql( schema='sfn', name="country", con=engine, index=False, if_exists="append")


conn = engine.connect()
metadata = MetaData(schema='sfn')
table = Table("country", metadata, schema="sfn", autoload_with=engine)

# Step 3: Perform UPSERT for each row
from sqlalchemy.dialects.postgresql import insert

for _, row in df.iterrows():
    stmt = insert(table).values(row.to_dict())
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["country_code"],
        set_={
            "country_name": stmt.excluded.country_name,
            "flag_url": stmt.excluded.flag_url,
            'continent': stmt.excluded.continent
        }
    )
    conn.execute(upsert_stmt)
conn.commit()
conn.close()
print("✅ Upsert complete into sfn.country.")

print('Done.')
