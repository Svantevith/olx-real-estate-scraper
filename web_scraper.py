import requests
import bs4
import pandas as pd
import re
import os
from datetime import datetime
from typing import NoReturn
import numpy as np
import argparse

TRANSACTIONS = {
    'buy',
    'rent',
    'exchange'
}

PROVINCES = {
    'dolnoslaskie',
    'kujawsko-pomorskie',
    'lubelskie',
    'lubuskie',
    'lodzkie',
    'malopolskie',
    'mazowieckie',
    'opolskie',
    'podkarpackie',
    'podlaskie',
    'pomorskie',
    'slaskie',
    'swietokrzyskie',
    'warminsko-mazurskie',
    'wielkopolskie',
    'zachodnio-pomorskie'
}


def parser_function():
    description = 'Scrape the OLX website for your dream apartment!'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'transaction',
        type=str,
        help='Choose whether to [buy], [rent] or [exchange] a real estate.',
        default='buy',
        nargs='?'
    )
    parser.add_argument(
        'province',
        type=str,
        help=f"Name of province in Poland, where to search for real estate. Available options: {', '.join(PROVINCES)}",
        default='',
        nargs='?'
    )
    parser.add_argument(
        'start_page',
        type=int,
        help='First page queried.',
        default=1,
        nargs='?'
    )
    parser.add_argument(
        'end_page',
        type=int,
        help='Last page queried.',
        default=1,
        nargs='?'
    )
    return parser.parse_args()


def unique_path(path: str) -> str:
    filename, extension = os.path.splitext(path)
    counter = 2
    while os.path.exists(path):
        path = f'{filename[:-1]}{counter}{extension}'
        counter += 1
    return path


def get_title(_offer: bs4.Tag) -> str:
    return _offer.find('strong').text.strip('\n')


def get_price(_offer: bs4.Tag) -> int:
    return parse_numeric(_offer.find('p', 'price').text)


def get_localisation(_offer: bs4.Tag) -> str:
    bottom_cell = _offer.find('td', 'bottom-cell')
    return bottom_cell.find('small', 'breadcrumb x-normal').text.strip('\n')


def get_link(_offer) -> str:
    return _offer.find('a')['href']


def get_last_page(_bs: bs4.BeautifulSoup) -> int:
    return int(_bs.find_all('span', 'item fleft')[-1].text.strip('\n'))


def parse_numeric(x: str) -> float:
    numeric = ''.join(map(lambda s: s[0], re.findall('(\d+(,\d+)?)', x)))
    try:
        return int(numeric)
    except ValueError:
        return float(numeric.replace(',', '.'))


def save_to_excel(df: pd.DataFrame) -> NoReturn:
    file_name = f"{datetime.strftime(datetime.now(), 'Apartments_OLX_%Y%m%d_%H%M_v1')}.xlsx"
    excel_path = unique_path(os.path.join(os.getcwd(), 'Export', file_name))
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    df.to_excel(excel_path, index=False)
    print(f'\n[!] Excel spreadsheet has been successfully exported as {excel_path}')


def get_transaction(transaction: str) -> str:
    return transaction if transaction in TRANSACTIONS else 'buy'


def get_province(province: str) -> str:
    return province if province.lower() in PROVINCES else ''


def describe_apartments(df: pd.DataFrame, transaction, province) -> NoReturn:
    if transaction == 'buy':
        transaction = 'sale'
    price_lower, price_upper = map(int, np.quantile(df['Price'], [0.45, 0.55]))
    area_range = df.loc[(df['Price'] >= price_lower) & (df['Price'] <= price_upper), 'Area']
    print(
        f'\nAverage price of apartments for {transaction} in {province.title()} province, Poland is '
        f'ranging from {price_lower} to {price_upper} PLN, '
        f'corresponding to the area ranging from '
        f'{area_range.min()} to {area_range.max()} m²'
    )
    price_min = df['Price'].min()
    area_min = df.loc[df['Price'].values.argmin(), 'Area']
    city_min = df.loc[df['Price'].values.argmin(), 'City']
    print(
        f"If you are looking for a cheap accommodation, "
        f"a {area_min} m² apartment for {price_min} PLN is available in {city_min}"
    )


def get_url(transaction: str, province: str) -> str:
    transaction = {
        'buy': 'sprzedaz',
        'rent': 'wynajem',
        'exchange': 'zamiana'
    }[transaction]
    return f'https://www.olx.pl/nieruchomosci/mieszkania/{transaction}/{province.lower()}'


def get_info_from_offer(_offer) -> list:
    link = get_link(_offer)
    offer_page = requests.get(link)
    sub_bs = bs4.BeautifulSoup(offer_page.content, 'html.parser')
    labels = ['Powierzchnia', 'Liczba pokoi']
    data = []
    if 'olx.pl' in link:
        values = sub_bs.find_all('strong', 'offer-details__value')
        names = sub_bs.find_all('span', 'offer-details__name')
        found = -1
        for label in labels:
            j = found + 1
            for name in names[j:]:
                if label == name.text:
                    val = values[j].text
                    if val == '4 i więcej':
                        val = '>4'
                    else:
                        val = parse_numeric(val)
                    data.append(val)
                    found = j
                    break
                else:
                    j += 1
    else:
        for label in labels:
            val = sub_bs.find('div', {'role': 'region', 'aria-label': label}).text
            if val.endswith('więcej niż 10'):
                val = '>10'
            else:
                val = parse_numeric(val)
            data.append(val)

    return data


def get_pages(start_page: str, end_page: str) -> tuple:
    start_page = 1 if int(start_page) <= 0 else int(start_page)
    end_page = start_page if int(end_page) < start_page else int(end_page)
    return start_page, end_page


def get_params():
    args = vars(parser_function())
    transaction = get_transaction(args['transaction'])
    province = get_province(args['province'])
    start_page, end_page = get_pages(args['start_page'], args['end_page'])
    return transaction, province, start_page, end_page


def web_scraper(df: pd.DataFrame, transaction: str, province: str, start_page: int, end_page) -> NoReturn:
    URL = get_url(transaction, province)
    message = f'Searching through {URL}'
    if start_page == end_page:
        print(f'\n{message}, page {end_page}:\n')
    else:
        print(f'\n{message}, from {start_page} to {end_page} page:\n')
    for i in range(start_page, end_page + 1):
        url = f'{URL}?page={i}'
        page = requests.get(url)
        bs = bs4.BeautifulSoup(page.content, 'html.parser')
        if i > get_last_page(bs):
            break
        for j, offer in enumerate(bs.find_all('div', 'offer-wrapper'), start=1):
            title = get_title(offer)
            price = get_price(offer)
            localisation = get_localisation(offer)
            try:
                city, district = localisation.split(', ')
            except ValueError:
                city, district = (localisation, '')
            area, rooms = get_info_from_offer(offer)
            print(f'\t[Page {i}, Ad {j}] [{title.title()}] {localisation}: {area} m², {price} PLN')
            df.at[offers.shape[0]] = [city, district, area, rooms, price]


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    transaction_type, province_name, entry_page, last_page = get_params()
    print(f"Parameters: '{transaction_type}', '{province_name}', '{entry_page}', '{last_page}'")
    offers = pd.DataFrame(columns=['City', 'District', 'Area', 'Rooms', 'Price'])
    try:
        web_scraper(offers, transaction_type, province_name, entry_page, last_page)
    except KeyboardInterrupt:
        print('\n[!] Web scraping interrupted by the user', end='')
    finally:
        offers = offers.convert_dtypes()
        describe_apartments(offers, transaction_type, province_name)
        save_to_excel(offers)
