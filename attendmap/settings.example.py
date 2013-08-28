## Example settings file
##----------------------------------------

## Tweet matching
SEARCH_QUERY = "#FakeEventName"
TWEET_MATCH_REGS = [
    r"I will attend #FakeEventName(:?\s+from (?P<city>.*))?",
    r"Partecipero a #FakeEventName(:?\s+da (?P<city>.*))?",
]

## Twitter
APP_KEY = ""
APP_SECRET = ""

## Geonames
GEONAMES_USER = ''

## Sqlite database name
DATABASE_NAME = "../database.sqlite"
