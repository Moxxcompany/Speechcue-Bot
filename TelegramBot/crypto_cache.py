import os

import requests
import time
from django.core.cache import cache

def fetch_with_retry(url, headers, retry_count=3):
    for attempt in range(retry_count):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            retry_delay = 2 ** attempt
            print(f"Rate limit hit, retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            response.raise_for_status()
    raise ValueError(f"Failed to fetch data from {url} after {retry_count} attempts.")



def fetch_crypto_price_with_retry(crypto_symbol, retry_count=3):
    x_api_key = os.getenv('x-api-key')
    cache_key = f"{crypto_symbol}_price"

    cached_price = cache.get(cache_key)

    if cached_price:
        print(f"Using cached price for {crypto_symbol}: {cached_price}")
        return cached_price

    symbol = crypto_symbol.upper()

    url = f"https://api.tatum.io/v3/tatum/rate/{symbol}?basePair=USD"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    for attempt in range(retry_count):
        try:
            response = requests.get(url, headers = headers)
            print(f"fetch response {response}")
            if response.status_code == 200:
                price = response.json()["value"]

                cache.set(cache_key, price, timeout=300)
                print(f"Fetched and cached price for {crypto_symbol}: {price}")

                return price
            elif response.status_code == 429:
                retry_delay = 2 ** attempt
                print(f"Rate limit hit, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching price for {crypto_symbol}: {e}")

    cached_price = cache.get(cache_key)
    if cached_price:
        print(f"Using stale cached price for {crypto_symbol} after API failure: {cached_price}")
        return cached_price

    raise ValueError(f"Failed to fetch price for {crypto_symbol} and no cached value available.")


def get_cached_crypto_price(crypto_symbol, fetch_func):
    cache_key = f"{crypto_symbol}_price"

    price = cache.get(cache_key)
    print(f"cache key : {cache_key}")
    print(f"price : {price}")
    if not price:
        try:
            price = fetch_func()
            cache.set(cache_key, price, timeout=300)
            print(f"Fetched and cached price for {crypto_symbol}: {price}")
        except ValueError as e:
            print(f"Error: {e}")
            return None
    else:
        print(f"Using cached price for {crypto_symbol}: {price}")

    return price
