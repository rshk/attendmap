#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
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
    print("Unable to find settings. Please copy "
          "attendmap/settings.example.py \n"
          "as attendmap/settings.py, configure it and re-run "
          "setup.py install..")
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
    """Returns a (cached) database connection"""
    global _cached_db_connection
    if _cached_db_connection is not None:
        return _cached_db_connection
    else:
        conn = init_db(DATABASE_NAME)
        _cached_db_connection = conn
        return conn


def var_get(name, default=None):
    """Get a variable from the key/value store"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM variables WHERE name=?", (name,))
    data = c.fetchall()
    assert len(data) < 2
    if len(data) == 0:
        return default
    return data[0]['value']


def var_set(name, value):
    """Set a variable in the key/value store"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO variables (name, value) VALUES (?, ?)",
                  (name, value))
    except sqlite3.IntegrityError:
        c.execute("UPDATE variables SET value=? WHERE name=?", (value, name))
    conn.commit()


def var_del(name):
    """Delete a variable from the key/value store"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM variables WHERE name=?", (name,))
    conn.commit()


def store_tweet(tweet, extra=None):
    """Store a tweet in the database"""

    if extra is None:
        extra = {}
    conn = get_db_connection()
    c = conn.cursor()

    fmt = "%a %b %d %H:%M:%S +0000 %Y"
    tweet_date = datetime.datetime.strptime(tweet['created_at'], fmt)

    c.execute("""
    INSERT INTO tweets
        (id, screen_name, name, date, text, city, lon, lat, orig_tweet)
    VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        tweet['id'],
        tweet['user']['screen_name'],
        tweet['user']['name'],
        tweet_date,
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
    Retrieves the (lon, lat) coordinates of a place, by
    querying the geonames web service.
    """

    params = urllib.urlencode({
        'username': GEONAMES_USER,
        'q': place_text,
        'maxRows': 1,
    })
    response = requests.get(
        "http://api.geonames.org/searchJSON?{}".format(params))
    resp_data = response.json()['geonames'][0]
    loc = float(resp_data['lng']), float(resp_data['lat'])
    return loc


def scan_new_tweets():
    ## Will search for new tweets, where "new" means more recent
    ## than the stored max_tweet_id

    twitter_max_id = var_get('twitter_max_id')
    query_args = {}
    if twitter_max_id is not None:
        query_args['since_id'] = twitter_max_id

    twitter = init_twitter()
    result = twitter.search(
        q=SEARCH_QUERY,
        **query_args)

    for tweet in result['statuses']:
        print("New tweet: {}: {!r}".format(tweet['id'], tweet['text']))
        try:
            store_tweet(tweet)
        except sqlite3.IntegrityError:
            warnings.warn("Duplicate tweet: {}".format(tweet['id']))

    var_set('twitter_max_id', result['search_metadata']['max_id'])


def get_tweet_location(tweet):
    """
    Try to get location from tweet, either extracting from text
    or associated coordinates.
    """

    text_info = match_tweet_text(tweet['text'])

    if text_info and text_info.get('city'):
        try:
            lon, lat = geolocate_place(text_info['city'])
        except:
            pass
        else:
            return {
                'lon': lon,
                'lat': lat,
                'city': text_info['city'],
            }

    try:
        lon, lat = tweet['coordinates']['coordinates']
    except:
        pass
    else:
        return {'lon': lon, 'lat': lat}


def geolocate_tweets(only_new=True):
    """
    Update geolocation information associated with tweets.
    """

    if only_new:
        query = "SELECT * FROM tweets WHERE lon IS NULL OR lat IS NULL"
    else:
        query = "SELECT * FROM tweets"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(query)
    rows = c.fetchall()

    for row in rows:
        ## If we have a city in the tweet text, geolocate that
        ## Else, if the tweet has associated coordinates, use them

        print("Geolocating tweet: {}".format(row['id']))

        tweet = json.loads(row['orig_tweet'])
        tweet_location = get_tweet_location(tweet)

        if tweet_location is not None:
            if 'city' in tweet_location:
                print("    > City found in text")
                c.execute("UPDATE tweets SET city=? WHERE id=?",
                          (tweet_location['city'], row['id']))
                conn.commit()
            else:
                print("    > Location from coordinates")
            c.execute("UPDATE tweets SET lon=?, lat=? WHERE id=?",
                      (tweet_location['lon'],
                       tweet_location['lat'],
                       row['id']))
            conn.commit()


def export_csv():
    import csv
    import io
    b = io.BytesIO()
    w = csv.writer(b)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tweets")
    for row in c.fetchall():
        w.writerow((
            row['id'],
            row['name'].encode('utf-8'),
            row['screen_name'].encode('utf-8'),
            row['text'].encode('utf-8'),
            (row['city'] or '').encode('utf-8'),
            row['lon'],
            row['lat']
        ))
    return b.getvalue()


def export_json():
    obj = []
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tweets")
    for row in c.fetchall():
        obj.append({
            'id': row['id'],
            'name': row['name'],
            'screen_name': row['screen_name'],
            'text': row['text'],
            'city': row['city'],
            'coordinates': {
                'lon': row['lon'],
                'lat': row['lat'],
            }
        })
    return json.dumps(obj)


def export_geojson():
    pass


exporters = {
    'csv': export_csv,
    'json': export_json,
    'geojson': export_geojson,
}
