#!/usr/bin/env python3
"""
Kayak cheap flight scraper

Uses chromedriver to scrape kayak.com for cheap flight data.

Hacked together mostly from:
- <https://github.com/manuelsilverio/scraping_kayak>
- <https://github.com/temannin/ClosestAirportFinder/blob/master/finder.py>
- airport codes: <https://stackoverflow.com/a/62494540> CC-BY-SA 4.0

Copyright 2022 Tyler Cipriani <tyler@tylercipriani.com>
License: GPL-3
"""

import argparse
import requests

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from bs4 import BeautifulSoup
import re
import pandas as pd
import numpy as np
import time

from geopy.geocoders import Nominatim
import airportsdata

from math import sin, cos, sqrt, atan2, radians



def scrape(origin, destination, startdate, enddate, sleep=30):
    # I want cheapest, not best :)
    # url = "https://www.kayak.com/flights/" + origin + "-" + destination + "/" + startdate + "/" + enddate + "?sort=bestflight_a&fs=stops=0"
    url = "https://www.kayak.com/flights/" + origin + "-" + destination + "/" + startdate + "/" + enddate + "?sort=price_a"
    print("\n" + url)

    chrome_options = webdriver.ChromeOptions()
    # agents = ["Firefox/66.0.3", "Chrome/73.0.3683.68", "Edge/16.16299"]
    print("User agent: Chrome/73.0.3683.68")
    chrome_options.add_argument('--user-agent=Chrome/73.0.3683.68')
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(
        options=chrome_options,
        desired_capabilities=chrome_options.to_capabilities()
    )
    #driver.implicitly_wait(sleep)
    driver.get(url)

    # Check if Kayak thinks that we're a bot
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'lxml')

    if soup.find_all('p')[0].getText() == "Please confirm that you are a real KAYAK user.":
        print("Kayak thinks I'm a bot, which I am ... so let's wait a bit and try again")
        driver.close()
        time.sleep(sleep)
        return "failure"

    print(f'Waiting {sleep} seconds for website to load...')
    time.sleep(sleep)

    print('Processing website')

    try:
        soup = BeautifulSoup(driver.page_source, 'lxml')
        price_list = soup.select(
            'div.Common-Booking-MultiBookProvider.Theme-featured-large.multi-row'
        )

        duration_list = soup.select('.duration .top')

        prices = []
        for div in price_list:
            val = div.getText().strip().split('\n')[0].strip().replace(',', '').replace('$', '')
            prices.append(int(val))

        durations = []
        for duration in duration_list:
            durations.append(int(duration.getText().strip().split('h')[0]))
    except:
        import pdb
        pdb.set_trace()

    # close the browser
    driver.close()

    try:
        return sum(prices)/len(prices), sum(durations)/len(durations)
    except:
        return 0, 0


def lat_long(city):
    geolocator = Nominatim(user_agent="MyApp")
    location = geolocator.geocode(city)
    return radians(location.latitude), radians(location.longitude)


def distance_from_airport(lat, lon, lat2, lon2):
    radius_of_earth = 6378.0
    dlon = lon2 - lon
    dlat = lat2 - lat
    a = sin(dlat / 2)**2 + cos(lat) * \
        cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius_of_earth * c * .621371


def filter_major_airports(airports):
    data = requests.get('http://www.airportcodes.org/').content
    cities_and_codes =re.findall(r'([A-Za-z, ]+)\(([A-Z]{3})\)', data.decode('utf8'))
    major_airports = []
    for code in cities_and_codes:
        ap = airports.get(code[-1])
        if ap is not None:
            major_airports.append(ap)
    return major_airports


def find_airport(city):
    lat, lon = lat_long(city)
    airports = airportsdata.load('IATA')
    min_distance = float('inf')
    closeset_airport = None

    # Since this is a list of EVERY. AIRPORT. EVER. I want a smaller list
    major_airports = filter_major_airports(airports)

    for airport in major_airports:
        lat2 = radians(airport['lat'])
        lon2 = radians(airport['lon'])
        distance = distance_from_airport(lat, lon, lat2, lon2)
        if distance < min_distance:
            closest_airport = airport
            min_distance = distance

    return closest_airport['iata']


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--origin', '-o')
    ap.add_argument('--destination', '-d')
    ap.add_argument('--start-date', '-s', help='ISO8601 start date')
    ap.add_argument('--end-date', '-e', help='ISO8601 end date')
    ap.add_argument('--sleep', default=30)
    return ap.parse_args()


if __name__ == '__main__':
    args = parse_args()
    startdate = args.start_date
    enddate = args.end_date

    prices = {}
    travel_times = {}

    with open(args.origin) as f:
        origins = f.readlines()

    with open(args.destination) as f:
        destinations = f.readlines()

    for destination in destinations:
        for origin in origins:
            dest = find_airport(destination)
            orig = find_airport(origin)
            print('Scraping for origin: {} and destination: {}, for date: {}'.format(
                orig,
                dest,
                startdate,
            ))
            avg_price, avg_hour = scrape(
                origin=orig,
                destination=dest,
                startdate=startdate,
                enddate=enddate,
                sleep=int(args.sleep)
            )
            prices.setdefault(f'{orig}', {})
            travel_times.setdefault(f'{orig}', {})
            prices[f'{orig}'][f'{dest}'] = avg_price,
            travel_times[f'{orig}'][f'{dest}'] = avg_hour

        df = pd.DataFrame.from_dict(prices)
        df.to_csv('price.csv')

        df2 = pd.DataFrame.from_dict(travel_times)
        df2.to_csv('travel_time.csv')
        print('DONE!')
