#!/usr/bin/env python3
# thanks to https://beckernick.github.io/faster-web-scraping-python/
# !!: PLEASE RUN on the base path folder, not from the script folder
# !!: python3 script/parser.py

import os
import re
import json
import time
import pytz
import requests
import concurrent.futures
from lxml import html
from datetime import datetime, timedelta

tz = pytz.timezone('Asia/Jakarta')
base_url = 'https://jadwalsholat.org/jadwal-sholat/monthly.php'
OFFSET_MINUTES = 15
RANGE_MONTHS_DEFAULT = 6   # ← jumlah bulan ke depan


def strip_lower(s):
    return re.sub(r'\W+', '', s).lower()


def minus_minutes(time_str, minutes):
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M")
        t = t - timedelta(minutes=minutes)
        return t.strftime("%H:%M")
    except Exception:
        return time_str


def get_cities():
    first_page = requests.get(base_url)
    first_page_doc = html.fromstring(first_page.content)

    city_ids = first_page_doc.xpath('//select[@class="inputcity"]/option/@value')
    city_names = first_page_doc.xpath('//select[@class="inputcity"]/option/text()')
    city_names = [strip_lower(d) for d in city_names]

    return dict(zip(city_ids, city_names))


def get_adzans(city_id, month, year):

    url = f"{base_url}?id={city_id}&m={month}&y={year}"
    page = requests.get(url)
    doc = html.fromstring(page.content)

    rows = doc.xpath(
        '//tr[contains(@class,"table_light") '
        'or contains(@class,"table_dark") '
        'or contains(@class,"table_highlight")]'
    )

    result = []

    for row in rows:
        data = row.xpath('td//text()')

        imsyak = data[1]
        shubuh = data[2]
        terbit = data[3]
        dhuha = data[4]
        dzuhur = data[5]
        ashr = data[6]
        magrib = data[7]
        isya = data[8]

        result.append({
            'tanggal': f"{year}-{month}-{data[0].replace(' ', '')}",

            # DATA ASLI
            'imsyak': imsyak,
            'shubuh': shubuh,
            'terbit': terbit,
            'dhuha': dhuha,
            'dzuhur': dzuhur,
            'ashr': ashr,
            'magrib': magrib,
            'isya': isya,

            # DATA BARU (15 MENIT SEBELUM)
            'sebelum_imsyak': minus_minutes(imsyak, OFFSET_MINUTES),
            'sebelum_shubuh': minus_minutes(shubuh, OFFSET_MINUTES),
            'sebelum_terbit': minus_minutes(terbit, OFFSET_MINUTES),
            'sebelum_dhuha': minus_minutes(dhuha, OFFSET_MINUTES),
            'sebelum_dzuhur': minus_minutes(dzuhur, OFFSET_MINUTES),
            'sebelum_ashr': minus_minutes(ashr, OFFSET_MINUTES),
            'sebelum_magrib': minus_minutes(magrib, OFFSET_MINUTES),
            'sebelum_isya': minus_minutes(isya, OFFSET_MINUTES),
        })

    return result


def write_file(city, adzans):

    flb = './adzan/' + city + '/'
    dt = adzans[0]['tanggal'].replace('-', '/')
    fld = flb + dt[:4]

    if not os.path.exists(fld):
        os.makedirs(fld, mode=0o777)

    with open(fld + '/' + dt[5:7] + '.json', 'w+') as f:
        f.write(json.dumps(adzans))


def process_city(name, id):
    month = os.getenv('JWO_MONTH')
    year = os.getenv('JWO_YEAR')

    write_file(name, get_adzans(id, month, year))
    print(f'✔ {name} {year}-{month} done')


def month_range():
    """Return list of (year, month) to process"""
    env_month = os.getenv('JWO_MONTH')
    env_year = os.getenv('JWO_YEAR')

    now = datetime.now(tz)

    # Manual → 1 bulan saja
    if env_month and env_year:
        return [(env_year, env_month)]

    # Otomatis → 6 bulan ke depan
    months = []
    for i in range(RANGE_MONTHS_DEFAULT):
        d = now + timedelta(days=32 * i)
        months.append((f"{d.year:04d}", f"{d.month:02d}"))

    # unik & berurutan
    return list(dict.fromkeys(months))


def main():

    start = time.time()
    cities = get_cities()
    ranges = month_range()

    for year, month in ranges:
        print(f"\n=== Processing {year}-{month} ===")
        os.environ['JWO_YEAR'] = year
        os.environ['JWO_MONTH'] = month

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for id, name in cities.items():
                futures.append(executor.submit(process_city, name=name, id=id))
            for _ in concurrent.futures.as_completed(futures):
                pass

    print('\nFinished in', round(time.time() - start, 2), 'seconds')


if __name__ == "__main__":
    main()
