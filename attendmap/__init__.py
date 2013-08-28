#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import sqlite3
import sys
import traceback
import urllib
import warnings

import requests
from twython import Twython


## Read settings

try:
    import attendmap.settings
except ImportError:
    print("Unable to find settings. Please copy attendmap/settings.example.py \n"
          "as attendmap/settings.py, configure it and re-run setup.py install..")
    sys.exit(1)

SEARCH_QUERY = attendmap.settings.SEARCH_QUERY
TWEET_MATCH_REGS = [
    re.compile(regex, flags=re.IGNORECASE)
    for regex in attendmap.settings.TWEET_MATCH_REGS
]

APP_KEY = attendmap.settings.APP_KEY
APP_SECRET = attendmap.settings.APP_SECRET
GEONAMES_USER = attendmap.settings.GEONAMES_USER

DATABASE_NAME = attendmap.settings.DATABASE_NAME
DATABASE_NAME = os.path.join(os.path.dirname(__file__), DATABASE_NAME)


def clean_tweet_text(text):
    """
    Cleanup tweet text before matching. For example, transliterates
    accented letters, replaces multiple spaces, etc.
    Returns the original text converted to lowercase.
    """
    if not isinstance(text, unicode):
        text = unicode(text, encoding='utf-8')
    text = u' '.join(text.lower().split())
    try:
        import unidecode
    except ImportError:
        warnings.warn("The 'unidecode' module was not found. "
                      "Falling back to simple transliteration")
        tt = dict(zip(
            map(ord, u'àáèéìíòóùú'),
            map(ord, u'aaeeiioouu')))
        text = text.translate(tt)
    else:
        text = unidecode.unidecode(text)
    return text


def match_tweet_text(text):
    """Try to extract information from a tweet text"""
    text = clean_tweet_text(text)
    for reg in TWEET_MATCH_REGS:
        data = reg.match(text)
        if data is not None:
            return data.groupdict()


def init_db(db_filename):
    """
    Initializes a database connection.
    If the database didn't exist, this will create all the
    required tables.
    """
    already_exists = os.path.exists(db_filename)
    conn = sqlite3.connect(db_filename)
    conn.row_factory = sqlite3.Row
    if not already_exists:
        ## Create the tables
        c = conn.cursor()
        c.execute("""
        CREATE TABLE tweets (
            id text PRIMARY KEY,
            screen_name TEXT,
            name TEXT,
            date TEXT,
            text TEXT,
            city TEXT,
            lat REAL,
            lon REAL,
            orig_tweet TEXT
        );
        """)
        c.execute("""
        CREATE TABLE variables (
            name TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        conn.commit()
    return conn


_cached_db_connection = None


def get_db_connection():
    global _cached_db_connection
    if _cached_db_connection is not None:
        return _cached_db_connection
    else:
        conn = init_db(DATABASE_NAME)
        _cached_db_connection = conn
        return conn


def var_get(name, default=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM variables WHERE name=?", (name,))
    data = c.fetchall()
    assert len(data) < 2
    if len(data) == 0:
        return default
    return data[0]['value']


def var_set(name, value):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO variables (name, value) VALUES (?, ?)", (name, value))
    except sqlite3.IntegrityError:
        c.execute("UPDATE variables SET value=? WHERE name=?", (value, name))
    conn.commit()


def var_del(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM variables WHERE name=?", (name,))
    conn.commit()


def store_tweet(tweet):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO tweets
        (id, screen_name, name, date, text, city, lon, lat, orig_tweet)
    VALUES
        (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        tweet['id'],
        tweet['screen_name'],
        tweet['name'],
        tweet['created'],
        tweet['text'],
        extra.get('city'),
        extra.get('coordinates', (None, None))[0],
        extra.get('coordinates', (None, None))[1],
        json.dumps(tweet),
    ))


def get_twitter_access_token():
    """Get a Twitter access token"""

    TWITTER_AT_ENV_VAR = 'TWITTER_ACCESS_TOKEN'

    ## Access token via environment variable has the precedence
    if TWITTER_AT_ENV_VAR in os.environ:
        return os.environ[TWITTER_AT_ENV_VAR]

    ## Try in the database
    access_token = var_get('access_token')
    if access_token:
        return access_token

    ## Get a new access token
    twitter = Twython(APP_KEY, APP_SECRET, oauth_version=2)
    access_token = twitter.obtain_access_token()
    var_set('access_token', access_token)

    return access_token


def init_twitter():
    """Initialize Twitter API client"""

    access_token = get_twitter_access_token()
    twitter = Twython(APP_KEY, access_token=access_token)
    return twitter


def geolocate_place(place_text):
    """
    Retrieves the (long, lat) coordinates of a place, by
    querying the geonames web service.
    """

    params = urllib.urlencode({
        'username': GEONAMES_USER,
        'q': place_text,
        'maxRows': 1,
    })
    response = requests.get("http://api.geonames.org/searchJSON?{}".format(params))
    resp_data = response.json()['geonames'][0]
    loc = float(resp_data['lng']), float(resp_data['lat'])
    return loc


def scan_new_tweets():
    ## Will search for new tweets, where "new" means more recent
    ## than the stored max_tweet_id
    pass


command_help = """
Commands:

    update
        Updates tweets in the database by querying the API

    shell
        Used to launch an interactive shell, using ipython.
        Just run: ``ipython -i get_tweets.py shell``

    help
        Show this help message
"""


if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = 'help'

    if command == 'help':
        print command_help
        sys.exit()

    elif command == 'shell':
        pass  # We're done here

    else:
        raise ValueError("Unknown command {}".format(command))


# twitter = init_twitter()

# tweets = twitter.search(q=SEARCH_QUERY)
# for tweet in tweets['statuses']:
#     #print tweet
#     author = tweet['user']['screen_name']
#     author_name = tweet['user']['name']
#     text = tweet['text']
#     #data = TWEET_MATCH_RE.match(text)
#     data = match_tweet_text(text)

#     if data:
#         loc = None

#         if data.get('city'):
#             try:
#                 loc = geolocate_place(data['city'])
#             except:
#                 ## Print the exception but resume..
#                 traceback.print_exc()

#         if (loc is None) and tweet['coordinates']:
#             try:
#                 loc = tuple(tweet['coordinates']['coordinates'])
#             except KeyError:
#                 pass
#             except:
#                 traceback.print_exc()

#         ## todo: extract location, either from the "from" field
#         ## or tweet coordinates
#         print u"{author} ({author_name}): {text}".format(
#             author=author, author_name=author_name, text=text)
#         print u"    >> from {}".format(loc)

#     else:
#         print u"Skipped: {author} ({author_name}): {text}".format(
#             author=author, author_name=author_name, text=text)
