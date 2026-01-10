# Standard library imports (in order of appearance then import/from)
import time
import json
import re # from collections import Counter
import math
import os # os.getcwd() # os.chdir()
from collections import Counter

# Third Party imports (in order of appearance then import/from)
import requests
import numpy as np
import bs4 as bs
import pandas as pd
from binance.exceptions import BinanceAPIException, BinanceRequestException #, BinanceWithdrawException, maybe refactor and add for executing binance_trade_coin_btc exceptions (also need logic for these) for BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
from kucoin.exceptions import KucoinAPIException, KucoinRequestException
from pycoingecko import CoinGeckoAPI
from datetime import datetime, timedelta
from pytrends.request import TrendReq

# Local Imports

__all__ = [
    "_fetch_data",
    "trendline",
    "get_coin_data_coinmarketcap",
    # "get_coin_data_coingecko",
    "get_coin_data",
    # "get_coin_data_granular_cg",
    # "get_coins_markets_cg",
    "get_coins_markets_coinmarketcap",
    # "get_coins_markets_coingecko",
    "save_coins_data",
    "get_saved_coins_data",
    "get_google_trends_pt",
    "get_kucoin_pairs",
    "get_binance_pairs",
    "kucoin_trade_coin_usdt",
    "binance_trade_coin_btc", # still being used in #retry_exchange_open_orders_in_portfolio and #retry_exchange_trade_error_or_paper_orders_in_portfolio for precautionary
    "kucoin_check_24h_vol_and_price_in_usdt",
    # "binance_check_24h_vol_and_price_in_btc",
    "exchange_check_arbitrage",
    # "kucoin_usdt_check_arbitrages",
    # "binance_btc_check_arbitrages",
    "update_portfolio_postions_back_testing",
    "update_portfolio_buy_and_sell_coins",
    "run_portfolio_rr",
    "get_kucoin_assets",
    # "get_binance_assets",
    "portfolio_align_balance_with_exchange",
    "portfolio_calculate_roi",
    "portfolio_panic_sell",
    "retry_exchange_open_orders_in_portfolio",
    "retry_exchange_trade_error_or_paper_orders_in_portfolio",
    "portfolio_trading",
    "save_portfolio_backup",
    "get_saved_portfolio_backup",
]
cg = CoinGeckoAPI()

# same as in eventregistry/quant-trading/crypto.py
# need to have ndg-httpsclient, pyopenssl, and pyasn1 (latter 2 are normally already installed) installed to deal with Caused by SSLError(SSLError("bad handshake: SysCallError(60, 'ETIMEDOUT')",),) according to https://stackoverflow.com/questions/33410577 (should also check tls_version and maybe unset https_proxy from commandline), but doesn't seem to work
def _fetch_data(func, params, error_str, empty_data, retry=True):
    try:
        data = func(**params)
    except (ValueError, TypeError) as e:
        print(str(e) + error_str)
        data = empty_data
    except Exception as e:
        print(str(e) + error_str)
        data = empty_data
        if retry and ((type(e) in [UnboundLocalError, TimeoutError, RuntimeError, requests.exceptions.ConnectionError, requests.exceptions.TooManyRedirects, BinanceAPIException, BinanceRequestException, KucoinAPIException, KucoinRequestException]) or (type(e) is requests.exceptions.HTTPError and e.response.status_code == 429)): # UnboundLocalError because of response error (local variable 'response' referenced before assignment), if use urllib for request TimeoutError is urllib.error.URLError: <urlopen error [Errno 60] Operation timed out>, requests.exceptions.ConnectionError is for (even when not using urllib): NewConnectionError('<urllib3.connection.VerifiedHTTPSConnection object at 0x119429240>: Failed to establish a new connection: [Errno 60] Operation timed out and: requests.exceptions.ConnectionError: ('Connection aborted.', OSError("(54, 'ECONNRESET')",)), currently unresolved - (even when not using urllib): Max retries exceeded with url: /?t=PD (Caused by SSLError(SSLError("bad handshake: SysCallError(50/54/60, 'ENETDOWN'/'ETIMEDOUT'/'ECONNRESET')",)
            time.sleep(60) # CoinGecko has limit of 100 requests/minute therefore sleep for a minute, unsure of request limit for Google Trends
            data = _fetch_data(func, params, error_str, empty_data, retry=False)
    return data

# data is dataframe column series
def trendline(data, order=1, reverse_to_ascending=False):
    data_index_values = data.index.values[::-1] if reverse_to_ascending else data.index.values
    coeffs = np.polyfit(data_index_values, list(data), order)
    slope = coeffs[-2]
    return float(slope)

# coinmarktcap detected automation 403 forbidden after 1 day
def get_coin_data_coinmarketcap(coin):
    market_data = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}
    site_url = 'https://www.coinmarketcap.com/currencies/' + coin
    resp = requests.get(site_url, headers=headers)
    soup = bs.BeautifulSoup(resp.text, 'html.parser')
    # divs = soup.find_all("div", {"class": "sc-8755d3ba-0 sc-d6430309-0 boyZcw"}) #
    # divs = soup.find_all("div", {"class": "sc-8755d3ba-0 iausdo"})
    span_price = soup.find("span", {"class": "sc-65e7f566-0 WXGwg base-text"}) if soup.find("span", {"class": "sc-65e7f566-0 WXGwg base-text"}) else soup.find("span", {"class": "abbreviation-price"}) # 2025-07-01 some reason bitcoin has "sc-65e7f566-0 esyGGG base-text" # changed 2024-11-29 "sc-d1ede7e3-0 fsQm base-text" changed 2024-05-24 "sc-f70bb44c-0 jxpCgO base-text" "sc-16891c57-0 dxubiK base-text" # "sc-16891c57-0 imoWES coin-stats-header"
    price = span_price.text.strip().replace('$',"").replace(',',"") if span_price and span_price.text else float("NaN")
    market_data['price'] = float(price)
    dl_statistics = soup.find("dl", {"class": "sc-65e7f566-0 cqLPHw CoinMetrics_xflex-container__O27KR"}) # changed 2024-11-29 "sc-65e7f566-0 eQBACe coin-metrics-table" changed 2024-07-19 "sc-d1ede7e3-0 bwRagp coin-metrics-table"# changed 2024-05-24 "sc-f70bb44c-0 iQEJet coin-metrics-table" "sc-16891c57-0 gPFIPZ coin-metrics-table" # "sc-8755d3ba-0 ddgngg" # "sc-8755d3ba-0 iausdo" # dl_statistics =  "sc-16891c57-0 hpRXnp"
    if not dl_statistics:
        print("Error scraping coinmarketcap data for coin: " + coin)
        return market_data
    divs = dl_statistics.find_all('div') # convert_value True
    times_table = {'P': 1e15, 'T': 1e12, 'B': 1e9, 'M': 1e6, 'K': 1e3}
    divs_major = dl_statistics.find_all('div', class_ = "sc-65e7f566-0 eQBACe")
    max_supply_id = "_".join(divs_major[-1].find("div", class_="LongTextDisplay_content-wrapper__2ho_9").text.strip().replace('.', "").split()).lower()
    max_supply_value = (divs_major[-1].find("div", class_="BasePopover_base__T5yOf popover-base") if divs_major[-1].find("div", class_="BasePopover_base__T5yOf popover-base") else divs_major[-1].find("div", class_="CoinMetrics_overflow-content__tlFu7")).text.strip().replace('$',"").replace(',',"").replace('%',"").replace('#',"").replace('(',"").replace(')',"").split(" ")[0]
    try:
        max_supply_value = float("NaN") if max_supply_value in ["∞", "-", "--", "No Data", "No"] else float(max_supply_value[:-1]) * times_table[max_supply_value[-1]] if re.findall(r"["+"".join(times_table.keys())+"]", max_supply_value) else float(max_supply_value)
    except Exception as e:
        print(str(e) + " - Value issue for id: " + max_supply_id + " for coin: " + coin + " retrying") # if id not in market_data:
        max_supply_value = (divs_major[-1].find("div", class_="BasePopover_base__T5yOf popover-base") if divs_major[-1].find("div", class_="BasePopover_base__T5yOf popover-base") else divs_major[-1].find("div", class_="CoinMetrics_overflow-content__tlFu7")).text.strip().replace('$',"").replace(',',"").replace('%',"").replace('#',"").replace('(',"").replace(')',"").replace('\xa0'," ").split(" ")[-1] # assuming it's this error: {symbol} {quantity} MNT 1B instead of {quantity} {symbol} 1B MNT # '\xa0' is a non-break space
        max_supply_value = float("NaN") if max_supply_value in ["∞", "-", "--", "No Data", "No"] else float(max_supply_value[:-1]) * times_table[max_supply_value[-1]] if re.findall(r"["+"".join(times_table.keys())+"]", max_supply_value) else float(max_supply_value) # value = float("NaN")
    market_data[max_supply_id] = max_supply_value
    # divs = soup.find_all("div", {"class": "sc-aef7b723-0 RdAHw"})
    for div in divs:
        # count = 0 # print(count) # count += 1
        # if convert_value:
        if div.find("dt"):
            # print(div.text.strip()) # break
            id = "_".join(div.find("dt").text.strip().replace('.', "").split()).lower() # fdv = fully_diluted_valuation (price x max supply)
            value = (div.find("dd").find("span") if id != "vol/mkt_cap_(24h)" else div.find("dd")).text.strip().replace('$',"").replace(',',"").replace('%',"").replace('#',"").replace('(',"").replace(')',"").split(" ")[0] # .split("$")[-1] # re.split('; |, |\*|\n',a) re.split('$|%|[a-zA-Z]+', div.find("dd").text.strip()) .split("%").split(" ")
            # print(id + ": " + str(value))
        if id in market_data:
            continue
        try:
            value = float("NaN") if value in ["∞", "-", "--", "No Data", "No"] else float(value)/100.0 if id == "vol/mkt_cap_(24h)" else float(value[:-1]) * times_table[value[-1]] if re.findall(r"["+"".join(times_table.keys())+"]", value) else float(value) # changed 2024-11-29 "volume/market_cap_(24h)" # re.search("".join(times_table.keys()), text_value): # text_values = re.split('[a-zA-Z]+', text_value) # " + "".join(times_table.keys()) + "
        except Exception as e:
            print(str(e) + " - Value issue for id: " + id + " for coin: " + coin + " retrying") # if id not in market_data:
            value = div.find("dd").find("span").text.strip().replace('$',"").replace(',',"").replace('%',"").replace('#',"").replace('(',"").replace(')',"").replace('\xa0'," ").split(" ")[-1] # assuming vol/mkt_cap_(24h) passes fine and it's this error: {symbol} {quantity} MNT 1B instead of {quantity} {symbol} 1B MNT
            value = float("NaN") if value in ["∞", "-", "--", "No Data", "No"] else float(value[:-1]) * times_table[value[-1]] if re.findall(r"["+"".join(times_table.keys())+"]", value) else float(value) # not accounting for other potential errors # value = float("NaN")
        market_data[id] = value
    return market_data

# coingecko detected automation 403 forbidden on 2023-05-02 04:27:25.340357 ~several days after implementation, also on 2025-12-08
def get_coin_data_coingecko(coin):
    data = {}
    site_url = 'https://www.coingecko.com/en/coins/' + coin
    resp = requests.get(site_url) # 403 error persists even with: , headers=headers # headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10 7 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}
    soup = bs.BeautifulSoup(resp.text, 'html.parser')
    # table = soup.find("table", {"class": "tw-w-full"})
    divs = soup.find_all("div", {"class": "tw-flex tw-justify-between tw-w-full tw-h-10 tw-py-2.5 tw-border-b tw-border-gray-200 dark:tw-border-opacity-10 tw-pl-0"})
    market_data = {}
    for div in divs:
        id = "_".join(div.text.strip().split()[0].split()).lower()
        value = float("NaN") if div.text.strip().split()[-1].strip() in ["∞", "-"] else float(div.text.strip().split()[-1].replace('$',"").replace(',',""))
        market_data[id] = value
    current_price_in_btc = float(soup.find("div", {"class": "tw-text-gray-500 text-normal dark:tw-text-white dark:tw-text-opacity-60 tw-mb-3"}).text.strip().split()[0].replace(',',"")) if soup.find("div", {"class": "tw-text-gray-500 text-normal dark:tw-text-white dark:tw-text-opacity-60 tw-mb-3"}) else float("NaN")
    current_price = float(soup.find("span", {"class": "tw-text-gray-900 dark:tw-text-white tw-text-3xl"}).text.strip().replace('$',"").replace(',',""))
    current_market_cap = float(soup.find("div", {"class": "tw-flex tw-justify-between tw-w-full tw-h-10 tw-py-2.5 lg:tw-border-t-0 tw-border-b tw-border-gray-200 dark:tw-border-opacity-10 tw-pl-0"}).text.strip().split()[-1].replace('$',"").replace(',',""))
    data["symbol"] = soup.find("span", {"class": "tw-font-normal tw-text-gray-500 dark:tw-text-white dark:tw-text-opacity-60 tw-text-base tw-mt-0.5"}).text.strip().lower()
    data['market_data'] = {**{"current_price": {"usd": current_price, "btc": current_price_in_btc}, "market_cap": {"usd": current_market_cap}}, **market_data}
    return data

# date is a string in format '%d-%m-%Y', make sure historical time is on utc time, CoinGecko historical saves in UTC time and uses opening price for that day, refactor - can return [market_data_in_coin_data, data] to simplify logic issues later, can also move logic of retry_current_if_no_historical_market_data inside function so all of the logic is inside function
def get_coin_data(coin, date=None, historical=False, retry_current_if_no_historical_market_data=False):
    # probably refactor, if run on current day and utc time is before midnight / want most recent price
    if not historical: # or date == datetime.now().strftime('%d-%m-%Y')
        # data = cg.get_coin_by_id(id=coin)
        data = get_coin_data_coinmarketcap(coin)
    else:
        data = cg.get_coin_history_by_id(coin, date=date)
        if ('market_data' not in data or not data['market_data']['market_cap']['usd']) and retry_current_if_no_historical_market_data and (date == datetime.utcnow().strftime('%d-%m-%Y')):
            print("Retrying current since no historical market data and day is current day for coin: " + coin + " on (utc time): " + str(datetime.utcnow()))
            data = get_coin_data(coin) # no need for retries / recursive break out loop since historical passed as False
    # maybe refactor and add if 'market_data' not in data or not data['market_data']['market_cap']['usd']: print('Error') and make data['market_data']['current_price']['usd'] = None
    return data

# Minutely data will be used for duration within 1 day, Hourly data will be used for duration between 1 day and 90 days, Daily data will be used for duration above 90 days
def get_coin_data_granular_cg(coin, from_timestamp, to_timestamp, currency='btc'): # time is in local time (PST)
    data = cg.get_coin_market_chart_range_by_id(coin, vs_currency=currency, from_timestamp=from_timestamp, to_timestamp=to_timestamp)
    # maybe refactor and add if 'prices' not in data: print('Error') and make data['prices'] = None
    return data

def get_coins_markets_cg(currency='btc', per_page=250, pages=1): # if decide to use less than max 250 entries per_page need to change error_str of _fetch_data executions
    same_symbol_coins = {'ftt': 'farmatrust', 'hot': 'hydro-protocol', 'stx': 'stox', 'btt': 'blocktrade', 'edg': 'edgeless', 'ghost': 'ghostprism', 'ult': 'shardus', 'box': 'box-token', 'mtc': 'mtc-mesh-network', 'spc': 'spacechain', 'ong': 'ong-social', 'comp': 'compound-coin'} # 'tac': 'traceability-chain' # same_symbol is just covering the top 1000 by market cap from coingecko on
    data = []
    for page in range(pages):
        data.extend(cg.get_coins_markets(vs_currency=currency, per_page=per_page, page=page + 1)) # no fetch_data on this call since get_coins_markets always called with _fetch_data
    for coin in data:
        if (coin['symbol'] in same_symbol_coins) and (same_symbol_coins[coin['symbol']] == coin['id']): # (list(same_symbol_coins.keys()) + list(binance_btc_api_error_coins.keys())) and coin['id'] in (list(same_symbol_coins.values()) + list(binance_btc_api_error_coins.values())): # refactor, some coins have the same symbol, find a way to select first occurence of symbol, issues with FTT and HOT
            data.remove(coin)
    return data

def get_coins_markets_coinmarketcap(pages=10): # refactor add market cap
    data = {}
    market_cap_rank = 0
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10 7 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'} #
    for page in range(1, pages+1):
        site_url = 'https://www.coinmarketcap.com/?page=' + str(page)
        resp = requests.get(site_url, headers=headers)
        # resp = requests.get(site_url)
        soup = bs.BeautifulSoup(resp.text, 'html.parser')
        table = soup.find("table", class_=lambda x: x and "cmc-table" in x) # chatgpt recommendation 2025-07-08 since changed again 2025-07-03 # changed ~2025-06-23 "sc-db1da501-3 ccGPRR cmc-table" # changed ~2025-04-15 "sc-db1da501-3 kTEDDd cmc-table" # changed 2025-03-01 (noticed on 2025-03-24) "sc-e66afe2c-3 gDwpBm cmc-table" # changed 2025-02-28 "sc-936354b2-3 tLXcG cmc-table" changed 2024-11-29 "sc-7b3ac367-3 etbcea cmc-table" changed 2024-07-30 "sc-963bde9f-3 fGUAUU cmc-table"# changed 2024-07-19 "sc-963bde9f-3 dzympI cmc-table"# changed 2024-05-24 "sc-ae0cff98-3 ipWPGi cmc-table" "sc-14cb040a-3 dsflYb cmc-table" "sc-feda9013-3 ePzlNg cmc-table" # "class": "sc-66133f36-3 etbEmy cmc-table" "sc-b6abf4b4-3 gTnkjE cmc-table"}) # idx,  0, # "sc-996d6db8-3 cOXNvh cmc-table" # "sc-beb003d5-3 ieTeVa cmc-table" # need to change this up every once in a while
        for row in table.find_all('tr')[1:]: # page 'coinmarketcap-20-index-dtf' is populating 1st position
            # print(row)
            tds = row.find_all("td")
            a_link = row.find("a", {"class": "cmc-link"})
            if a_link.find_all("p"):
                links = a_link.find_all("p") # links = a_link.find_all("p") if a_link.find_all("p") else a_link.find_all("span")
                coin_id = "-".join(links[0].text.strip().split()).lower() # mayve refactor error for coins like tether (combines tether-usdt instead of actual name tether) # coin_id = links[0].text.strip().lower() if links[0].text.strip() else links[0].text.strip()
                coin_symbol = links[1].text.strip().lower() # coin_symbol = links[1].text.strip().lower()
            else:
                links = a_link.find_all("span")
                coin_id = "-".join(links[1].text.strip().split()).lower()
                coin_symbol = links[2].text.strip().lower()
                # price =
            # print(coin_id + ": " + coin_symbol + ", " + str(tds[3].text.strip()))
            market_cap_rank = (market_cap_rank + 1) if coin_id != 'coinmarketcap-20-index-dtf' else market_cap_rank # market_cap_rank = float(tds[1].text.strip()) if tds[1].text.strip() else float("NaN") #
            try:
                price = float(tds[3].text.strip().replace('$',"").replace(',',"")) # if tds[3].text.strip() else float("NaN")
            except Exception as e:
                price = float("NaN")
                print(str(e) + " - Price issue(s) for coin: " + coin_id + " with market cap rank: " + str(market_cap_rank))
            try:
                market_cap = float(tds[7].text.split('$')[-1].replace('$',"").replace(',',"")) if tds[7].text.split('$')[-1] else float("NaN")
                volume_24h = float(tds[8].find("a").text.strip().replace('$',"").replace(',',"")) if tds[8].find("a").text.strip() else float("NaN") # find("a") since there is also volume listed in coin
                circulating_supply = float(tds[9].text.split(" ")[0].strip().replace(',',"")) if tds[9].text.split(" ")[0].strip() else float("NaN")
            except Exception as e:
                print(str(e) + " - Market Cap / Volume (24h) / Circulating Supply issue(s) for coin: " + coin_id + " with market cap rank: " + str(market_cap_rank))
                market_cap, volume_24h, circulating_supply = [float("NaN")]*3
            data[coin_id] = {"symbol": coin_symbol, "market_cap_rank": market_cap_rank, "price": price, "market_cap": market_cap, "volume_24h": volume_24h, "circulating_supply": circulating_supply}
            # if market_cap_rank == 11:
            #     print("Market cap rank: " + str(market_cap_rank)) # + ", Sleeping 10s")
            #     break
                # time.sleep(10)
    return data

# coingecko detected automation 403 forbidden on 2023-05-05 ~several days after implementation, works on 2025-12-08
def get_coins_markets_coingecko(pages=10):
    data = {}
    for page in range(1, pages+1):
        site_url = 'https://www.coingecko.com/?page=' + str(page)
        resp = requests.get(site_url)
        soup = bs.BeautifulSoup(resp.text, 'html.parser')
        table = soup.find("table", {"class": "gecko-homepage-coin-table gecko-sticky-table sortable"}) # "sort table mb-0 text-sm text-lg-normal table-scrollable"
        for row in table.find_all('tr')[1:]:
            market_cap_rank = float(row.find("td", {"class": "tw-sticky tw-left-[34px] gecko-sticky"}).text.strip()) # "table-number tw-text-left text-xs cg-sticky-col cg-sticky-second-col tw-max-w-14 lg:tw-w-14"
            coin_id_and_symbol_a = row.find("a", {"class": "tw-flex tw-items-center tw-w-full"})
            coin_id = coin_id_and_symbol_a['href'].split('/')[-1] # {"class": "tw-flex tw-flex-auto tw-items-start md:tw-flex-row tw-flex-col"}
            coin_symbol = coin_id_and_symbol_a.find("div", {"class": "tw-block 2lg:tw-inline tw-text-xs tw-leading-4 tw-text-gray-500 dark:tw-text-moon-200 tw-font-medium"}).text.strip().lower() # row.find("span", {"class": "d-lg-inline font-normal text-3xs tw-ml-0 md:tw-ml-2 md:tw-self-center tw-text-gray-500 dark:tw-text-white dark:tw-text-opacity-60"}).text.strip().lower()
            current_data_tds = row.find_all("td", {"class": "tw-text-end"})
            current_price = float(current_data_tds[0]['data-sort']) # float(row.find("td", {"class": "tw-text-end"})['data-sort']) # float(row.find("div", {"class": "tw-flex-1"}).text.strip().replace('$',"").replace(',',""))
            # print(str(market_cap_rank) + ": " + coin_id + "; " + coin_symbol + "; " + str(current_price))
            current_24h_volume = float(current_data_tds[5]['data-sort']) # float(row.find("td", {"class": "tw-text-end"})['data-sort']) # float(row.find("td", {"class": "td-liquidity_score lit text-right col-market"}).text.strip().replace('$',"").replace(',',"")) if row.find("td", {"class": "td-liquidity_score lit text-right col-market"}).text.strip() != '-' else 0
            current_market_cap = float(current_data_tds[6]['data-sort']) # float(row.find("td", {"class": "td-market_cap cap col-market cap-price text-right"}).text.strip().replace('$',"").replace(',',""))
            data[coin_id] = {"symbol": coin_symbol, "market_cap_rank": market_cap_rank, "price": current_price, "24h_volume": current_24h_volume, "market_cap": current_market_cap}
    return data

def save_coins_data(date, pages=10): # date is in format '%Y-%m-%d' # maybe refactor and add date if code block runs at a datetime.now() which is close to the next day, if runs longer no need to add date since market runs 24/7 # number of pages should be constant
    coins = _fetch_data(get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={}) # refactor all - ensure error_str have date: # 'currency': 'btc',
    df_coins = pd.DataFrame(columns = ["Market Cap Rank", "Facebook Likes", "Twitter Followers", "Reddit Subscribers", "Reddit Posts & Comments 48h", "Developer Stars", "Developer Issues", "Alexa Rank", "Price", "Price (BTC)", "Market Cap", "24h Volume", "24h Volume / Market Cap", "Fully Diluted Valuation", "Supply: Circulating", "Supply: Max", "Supply: Total"]) # maybe refactor and add columns which measure other KPIs (look to stocks.py for motivation)
    count = 0
    for coin_id, symbol_and_market_data in coins.items(): # here and throughout where iterating over get_coins_markets_cg assuming that all necessary keys are there (not checking for example if 'market_cap_rank', 'current_price', 'symbol' in coin) (has been the case in all cases observed)
        count += 1
        if count % 134 == 0:
            print("Sleeping 1min every 134 requests on: " + str(datetime.now()))
            time.sleep(1*60)
        coin_data = _fetch_data(get_coin_data, params={'coin': coin_id}, error_str=" - No " + "" + " coin data for: " + coin_id + " on: " + str(datetime.now()), empty_data={})
        if not coin_data:
            print("Error retrieving initial coin data for: " + coin_id)
            df_coins.loc[coin_id, ["Market Cap Rank", "Price", "Market Cap", "24h Volume", "Supply: Circulating"]] = [symbol_and_market_data['market_cap_rank'], symbol_and_market_data['price'], symbol_and_market_data['market_cap'], symbol_and_market_data['volume_24h'], symbol_and_market_data['circulating_supply']]
        else:
            # generally incomplete historical community data: facebook likes, twitter followers; developer data
            df_coins.loc[coin_id] = [
                symbol_and_market_data['market_cap_rank'],
                float("NaN"), # coin_data['community_data']['facebook_likes'] if coin_data['community_data']['facebook_likes'] else float("NaN"),
                float("NaN"), # coin_data['community_data']['twitter_followers'] if coin_data['community_data']['twitter_followers'] else float("NaN"),
                float("NaN"), # coin_data['community_data']['reddit_subscribers'] if coin_data['community_data']['reddit_subscribers'] else float("NaN"),
                float("NaN"), # coin_data['community_data']['reddit_average_posts_48h'] + coin_data['community_data']['reddit_average_comments_48h'] if (coin_data['community_data']['reddit_average_posts_48h'] and coin_data['community_data']['reddit_average_comments_48h']) else float("NaN"),
                float("NaN"), # coin_data['developer_data']['stars'] if coin_data['developer_data']['stars'] else float("NaN"),
                float("NaN"), # coin_data['developer_data']['total_issues'] if coin_data['developer_data']['total_issues'] else float("NaN"),
                float("NaN"), # coin_data['public_interest_stats']['alexa_rank'] if coin_data['public_interest_stats']['alexa_rank'] else float("NaN"),
                coin_data["price"] if "market_cap" in coin_data else symbol_and_market_data['price'], # float("NaN")
                float("NaN"), # coin_data['market_data']['current_price']['btc'] if coin_data['market_data']['current_price']['btc'] else float("NaN"),
                coin_data["market_cap"] if "market_cap" in coin_data else symbol_and_market_data['market_cap'], # coin_data['market_data']['market_cap']['usd'] if coin_data['market_data']['market_cap']['usd'] else float("NaN"),
                coin_data["volume_(24h)"] if "volume_(24h)" in coin_data else symbol_and_market_data['volume_24h'], # coin_data['market_data']['24_hour_trading_vol'] if coin_data['market_data']['24_hour_trading_vol'] else float("NaN"),
                coin_data["vol/mkt_cap_(24h)"] if "vol/mkt_cap_(24h)" in coin_data else float("NaN"),
                coin_data["fdv"] if "fdv" in coin_data else float("NaN"), # coin_data['market_data']['fully_diluted_valuation'] if ('fully_diluted_valuation' in coin_data['market_data'] and coin_data['market_data']['fully_diluted_valuation']) else float("NaN"),
                coin_data["circulating_supply"] if "circulating_supply" in coin_data else symbol_and_market_data['circulating_supply'],
                coin_data["max_supply"] if "max_supply" in coin_data else float("NaN"),
                coin_data["total_supply"] if "total_supply" in coin_data else float("NaN")
            ]
    f = open('data/crypto/saved_coins_data/' + 'coins_' + date + '.pckl', 'wb') # 2020_06_02, format is '%Y-%m-%d' # datetime.now().strftime('%Y-%m-%d')
    pd.to_pickle(df_coins, f)
    f.close()
    return df_coins

# 02/24/2020 is first day with 100 coins, 02/27/2020 is first day with 200 coins, 03/09/2020 is first day with 250 coins, 07/04/2020 is first day with 1000 coins, 2022-04-25->26 frozen, 2024-07-28->29 frozen, 2025-02-02->11 Jackson Hole some error, 2025-02-20->24 KCS retrieval error
def get_saved_coins_data(date): # date is a string in format '%Y-%m-%d'
    try:
        f = open('data/crypto/saved_coins_data/' + 'coins_' + date + '.pckl', 'rb')
        df_coins_historical = pd.read_pickle(f)
        f.close()
    except Exception as e:
        print(str(e) + " - No coins historical saved data for date: " + date)
        df_coins_historical = pd.DataFrame()
    return df_coins_historical

def get_google_trends_pt(kw_list, from_date, to_date, trend_days=270, cat=0, geo='', tz=480, gprop='', hl='en-US', isPartial_col=False): # trend_days max is around 270 # category to narrow results # geo e.g 'US', 'UK' # tz = timezone offset default is 360 which is US CST (UTC-6), PST is 480 (assuming UTC-8*60) # hl language default is en-US # gprop : filter results to specific google property like 'images', 'news', 'youtube' or 'froogle' # overlap=100, sleeptime=1, not doing multiple searches # other variables: timeout=(10,25), proxies=['https://34.203.233.13:80',], retries=2, backoff_factor=0.1, requests_args={'verify':False}, from_start=False, scale_cols=True
    data = pd.DataFrame()
    if len(kw_list) != 1: # not doing multirange_interest_over_time: len(kw_list)==0 or len(kw_list)>5
        print("Error: The keyword list must be 1, not doing multirange_interest_over_time") # be > 0 and can contain at most 5 words
        return data
    # not verifying from_date, to_date types, _fetch_data should handle error
    n_days = (to_date - from_date).days
    if n_days>270 or trend_days>270:
        print("Error: To - From Dates or Trend days must not exceed 270")
        return data
    _pytrends = TrendReq(hl=hl, tz=tz)
    # pytrends.build_payload(kw_list, cat=0, timeframe=, geo='', gprop='')
    try:
        _pytrends.build_payload(kw_list, cat=cat, timeframe=[from_date.strftime('%Y-%m-%d') + ' ' + to_date.strftime('%Y-%m-%d')], geo=geo, gprop=gprop) # trend_dates[0]
    except Exception as e:
        print(str(e) + " - No (or issue with) Pytrends for kw_list: " + str(kw_list) + " with from_date: " + str(from_date) + " and to_date: " + str(to_date))
    data = _pytrends.interest_over_time().reset_index()
    if not isPartial_col:
        data.drop('isPartial', axis=1, inplace=True)
    return data

# Currently, the KuCoin operations are not licensed in the USA; hence, it doesn’t have to report to IRS. However, the company states that it may disclose personal data at the request of government authorities. Therefore, you should report any income you generate from KuCoin to tax authorities.
# Kucoin API is restricted for each account, the request rate limit is 45 times/3s
def get_kucoin_pairs(): # pair="USDT"
    base_url = "https://api.kucoin.com"
    resp = requests.get(base_url + '/api/v1/market/allTickers')
    data = json.loads(resp.text)
    kucoin_pairs_with_price_and_vol_current = {}
    for pair_price in data['data']['ticker']:
        if ('last' in pair_price) and pair_price['last']: # (pair_price['symbol'].split("-")[1] == pair) and
            kucoin_pairs_with_price_and_vol_current[pair_price['symbol']] = {'price': float(pair_price['last']), '24h_volume': float(pair_price['volValue']) if ('volValue' in pair_price) and pair_price['volValue'] else float("NaN")}
    return kucoin_pairs_with_price_and_vol_current

def get_binance_pairs():
    binance_pairs_with_price_current = {}
    for pair_price in _fetch_data(binance_client.get_all_tickers, params={}, error_str=" - Binance get all tickers error on: " + str(datetime.now()), empty_data=[]):
        if ('price' in pair_price) and pair_price['price']:
            binance_pairs_with_price_current[pair_price['symbol']] = {'price': float(pair_price['price'])}
    return binance_pairs_with_price_current

def kucoin_trade_coin_usdt(symbol_pair, coin, trade=None, side=None, usdt_invest=None, quantity=None, price_in_btc=None, paper_trading=True, open_time=5, other_notes=None):
    if not (trade or side):
        raise ValueError('trade or side value is required')
    if not (usdt_invest or quantity): # or (quantity and not (quantity % int(quantity) == 0) # (quantity and not isinstance(quantity, int)) # allow selling of non-integer quantities if quantity specified since retry open orders can be non-integer since executed quantity can be a float, i.e. WNXMBTC retry open order buy on 09/04/2020: quantity (18.394) = original_quantity(24) - executed_quantity(5.606)
        raise ValueError("usdt_invest or quantity required") # and if quantity specified must be an integer
    # symbol = symbol_pair.split("-")[0].lower() # symbol_pair = coin.upper() + '-USDT'
    side = side if side else kucoin_client.SIDE_SELL if trade == "sell" else kucoin_client.SIDE_BUY if trade == "buy" else None # precautionary, case sensitive and string has to be either 'buy' or 'sell' otherwise error in order # binance_client.SIDE_SELL is "SELL" and binance_client.SIDE_BUY is "BUY" but precautionary in case python-binance api changes # side is terminology used by python-binance api
    kucoin_pairs_with_price_and_vol_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={})
    price, btc_price = kucoin_pairs_with_price_and_vol_current[symbol_pair]['price'] if symbol_pair in kucoin_pairs_with_price_and_vol_current else float("NaN"), kucoin_pairs_with_price_and_vol_current['BTC-USDT']['price'] # maybe refactor add fail safes
    price_in_btc = price_in_btc if price_in_btc else price / btc_price
    quantity = quantity if quantity else float("NaN") if np.isnan(price) else math.floor(usdt_invest / price) if usdt_invest > 10 else math.ceil(usdt_invest / price) # not checking if price_in_btc > btc_invest (resulting in fractions of a coin for example 'yearn-finance' on 08/10/2020) since would have to return "BTrade Error" which would lead to more logic downstream, easier to check before calling this function, also if it happens quantity = 0 and "BTrade Error" would occur # for now taken care of in update_portfolio_buy_and_sell_coins() - see comments near non-back_testing buying logic # have to worry about insufficient BTC available if round up and minimum order amounts (usually around $10 or 0.001 BTC as of June 12 2020) if round down - error if less than minimum: about APIError(code=-1013): Filter failure: MIN_NOTIONAL # sammchardy/python-binance/issues/219, got (rounding - I think) error for FETBTC: APIError(code=-1013): Filter failure: LOT_SIZE
    if paper_trading:
        message_body = "Q Trading @crypto (Paper Trading): " + symbol_pair + " " + (trade if trade else side) + " at price_in_btc " + str(price_in_btc) + " and price $" + str(price) + " and quantity " + str(quantity) + ", " + str(other_notes) + ", :)" # None if 'BTCUSDT' not in binance_pairs_with_price_current because want message to reflect logic of function
        print("executed kucoin_trade_coin_usdt()\n" + "\033[94m" + message_body +  "\033[0m") # blue # maybe refactor and add other color to function calls
        return [quantity, price, price_in_btc, {}, [], None] # here and below not returning position ('long' or 'long-p' based on value of paper_trading) as well, only helps in a one situation (complicates logic a bit in another situation) and can also be derived from value of trade_notes
    # maybe refactor and add precautionary alert to ensure ok with real trading - as parameter in function (to turn alert on or off, default on when not portfolio_trading, off when portfolio_trading)
    order = _fetch_data(kucoin_client.create_limit_order, params={
        'symbol': symbol_pair, #'LINK-USDT',
        'side': side, # kucoin_client.SIDE_BUY,
        'price': price, # 7.29,
        'size': round(quantity, 8)
        # 'timeInForce': 'GTC' # default
    }, error_str=" - Kucoin trade execution error for symbol pair " + str(symbol_pair) + ", " + str(trade if trade else side) + ", price " + str(price) + ", quantity " + str(quantity) + ", " + " on: " + str(datetime.now()), empty_data={})
    if not order: # maybe refactor and raise error, possibly a precautionary alert like above which is default on when not portfolio_trading, off when portfolio_trading
        return [quantity, price, price_in_btc, {}, [], "KTrade Error"]
    # check open_orders immediately and use open_time if no order['fills'] and no open_orders to avoid ~Filled situation and to prevent assigning '~Filled' to a position which should have 'Not filled' (happened with STORJBTC buy on 2020-08-27 17:20:45)
    open_orders = _fetch_data(kucoin_client.get_orders, params={'symbol': symbol_pair, 'status': 'active'}, error_str=" - Kucoin open orders error for symbol pair: " + symbol_pair + " on: " + str(datetime.now()), empty_data={'items':[]})['items'] # probably need to refactor since this doesn't always work, orders['items'][0]['cancelExist'] is more reliable however the orders['items'][0]['id'] doesn't always work (when cancelling etc) # also need to refactor since might need information besides ['items']
    if not order['orderId'] and not open_orders: # if not open_orders['items'][0]['cancelExist']: # maybe refactor 'cancelExist' main way of telling if order is open or closed atm # if both of these conditions fail after order went through most likely means that more processing time (on Binance servers) is needed to process open_order (unlikely but possible that open_order was created and executed in the span of ~4 lines of code) # maybe refactor might be able to use 'executedQty'
        time.sleep(open_time)
        open_orders = _fetch_data(kucoin_client.get_orders, params={'symbol': symbol_pair, 'status': 'active'}, error_str=" - Kucoin open orders error for symbol pair: " + symbol_pair + " on: " + str(datetime.now()), empty_data={'items':[]})['items'] # ,
    trade_notes = "Filled" if not open_orders else "Not filled" if (open_orders and float(open_orders[0]['size']) == quantity) else "Partially filled" if (open_orders and float(open_orders[0]['size']) != quantity) else "~Filled" # if have open_time > 0 can most likely (high probability) assume that if no order['fills'] and no open_orders that order has been Filled, but keep as precautionary (might be a failure on Binance servers in creating open_order or an API documentation change), should always check balances / assets
    message_body = "Q Trading @crypto: " + symbol_pair + " " + (trade if trade else side) + " at price_in_btc " + str(price_in_btc) + " and price $" + str(price) + " and quantity " + str(quantity) + ", " + str(other_notes) + ", " + trade_notes + (" :)" if trade_notes == "Filled" else " :/" if trade_notes == "Partially filled" else " :(")
    color_start, color_end = ["\033[92m", "\033[0m"] if trade_notes in ["Filled", "~Filled"] else ["\033[33m", "\033[0m"] if trade_notes == "Partially filled" else ["\033[91m", "\033[0m"] # green yellow red # last condition is if "Not filled" or "BTrade Error"
    print("executed kucoin_trade_coin_usdt()\n" + color_start + message_body + color_end + "\n\033[1mOrder:\033[0m " + str(order) + "\n\033[1mOpen orders:\033[0m" + str(open_orders))
    twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': message_body}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None) # No need to add message_body here and other cases to error_str since already printed in line before # maybe add logic here and other locations to deal with error - possibly e-mailing through another client
    return [quantity, price, price_in_btc, order, open_orders, trade_notes] #

# can add option for market or limit, but for now only limit orders, can also add options for different kind of timeInForce options, also add option to trade on another exchange if necessary or another base currency, maybe add option for checking 24h_vol, price, pump and dump so can have logic here and return value block_trade for logic at location of trade, returning price_in_btc since a bit more accurate than coingecko price
def binance_trade_coin_btc(symbol_pair, trade=None, side=None, btc_invest=None, quantity=None, paper_trading=True, open_time=1, other_notes=None): # don't like non-boolean value for trade value but having two bool values would complicate matters (i.e if both set True etc.) # assuming binance processes open_order (if order not immediately filled) almost immediately (1s) (and that this open_order sometimes filled immediately since often getting ~Filled) # can use recvWindow with api
    if not (trade or side):
        raise ValueError('trade or side value is required')
    if not (btc_invest or quantity): # or (quantity and not (quantity % int(quantity) == 0) # (quantity and not isinstance(quantity, int)) # allow selling of non-integer quantities if quantity specified since retry open orders can be non-integer since executed quantity can be a float, i.e. WNXMBTC retry open order buy on 09/04/2020: quantity (18.394) = original_quantity(24) - executed_quantity(5.606)
        raise ValueError("btc_invest or quantity required") # and if quantity specified must be an integer
    side = side if side else binance_client.SIDE_SELL if trade == "sell" else binance_client.SIDE_BUY if trade == "buy" else None # precautionary, case sensitive and string has to be either 'buy' or 'sell' otherwise error in order # binance_client.SIDE_SELL is "SELL" and binance_client.SIDE_BUY is "BUY" but precautionary in case python-binance api changes # side is terminology used by python-binance api
    binance_pairs_with_price_current = get_binance_pairs() # precautionay checking for ('price' in pair_price) and pair_price['price'] # faster than splitting into binance_btc_pairs_with_price_in_btc and binance_usdt_pairs_with_price
    price_in_btc = binance_pairs_with_price_current[symbol_pair] if symbol_pair in binance_pairs_with_price_current else float("NaN") # float("NaN") so will throw error in binance_client.create_order
    price = price_in_btc*binance_pairs_with_price_current['BTCUSDT'] if 'BTCUSDT' in binance_pairs_with_price_current else float("NaN") # if Binance offers more USDT trading pairs can refactor to binance_pairs_with_price_current['<SYMBOL>USDT']
    quantity = quantity if quantity else float("NaN") if np.isnan(price_in_btc) else math.floor(btc_invest / price_in_btc) if btc_invest > 0.001 else math.ceil(btc_invest / price_in_btc) # not checking if price_in_btc > btc_invest (resulting in fractions of a coin for example 'yearn-finance' on 08/10/2020) since would have to return "BTrade Error" which would lead to more logic downstream, easier to check before calling this function, also if it happens quantity = 0 and "BTrade Error" would occur # for now taken care of in update_portfolio_buy_and_sell_coins() - see comments near non-back_testing buying logic # have to worry about insufficient BTC available if round up and minimum order amounts (usually around $10 or 0.001 BTC as of June 12 2020) if round down - error if less than minimum: about APIError(code=-1013): Filter failure: MIN_NOTIONAL # sammchardy/python-binance/issues/219, got (rounding - I think) error for FETBTC: APIError(code=-1013): Filter failure: LOT_SIZE
    if paper_trading:
        message_body = "Q Trading @crypto (Paper Trading): " + symbol_pair + " " + (trade if trade else side) + " at price_in_btc " + str(price_in_btc) + " and price $" + str(price) + " and quantity " + str(quantity) + ", " + str(other_notes) + ", :)" # None if 'BTCUSDT' not in binance_pairs_with_price_current because want message to reflect logic of function
        print("executed binance_trade_coin_btc()\n" + "\033[94m" + message_body +  "\033[0m") # blue # maybe refactor and add other color to function calls
        return [quantity, price, price_in_btc, {}, [], None] # here and below not returning position ('long' or 'long-p' based on value of paper_trading) as well, only helps in a one situation (complicates logic a bit in another situation) and can also be derived from value of trade_notes
    # maybe refactor and add precautionary alert to ensure ok with real trading - as parameter in function (to turn alert on or off, default on when not portfolio_trading, off when portfolio_trading)
    order = _fetch_data(binance_client.create_order, params={
        'symbol': symbol_pair,
        'side': side,
        'type': binance_client.ORDER_TYPE_LIMIT,
        'timeInForce': 'GTC', # 'day' would be ideal
        'price': '{:.8f}'.format(price_in_btc), # 1e-08 is maximum precision allowed by Binance, HOTBTC has lowest price on Binance right now (2020-05-25): $0.000617 (0.00000007BTC), should only worry about precision if a coin worth this much stays the same price and BTC price >= $60,000 (a factor of 1e8 difference)
        'quantity': round(quantity, 8) # round(quantity,8) since if quantity specified might come in with more than 8 decimals, especially when partial open orders like this error for INJBTC on 2020-12-19 04:30:41.68:  APIError(code=-1111): Precision is over the maximum defined for this asset. - Binance trade execution error for symbol pair INJBTC, BUY, price_in_btc 0.0001373, quantity 125.20000000000005,  on: 2020-12-19 04:30:47.834535
    }, error_str=" - Binance trade execution error for symbol pair " + str(symbol_pair) + ", " + str(trade if trade else side) + ", price_in_btc " + str(price_in_btc) + ", quantity " + str(quantity) + ", " + " on: " + str(datetime.now()), empty_data={})
    if not order: # maybe refactor and raise error, possibly a precautionary alert like above which is default on when not portfolio_trading, off when portfolio_trading
        return [quantity, price_in_btc, {}, [], "BTrade Error"]
    # check open_orders immediately and use open_time if no order['fills'] and no open_orders to avoid ~Filled situation and to prevent assigning '~Filled' to a position which should have 'Not filled' (happened with STORJBTC buy on 2020-08-27 17:20:45)
    open_orders = _fetch_data(binance_client.get_open_orders, params={'symbol': symbol_pair}, error_str=" - Binance open orders error for symbol pair: " + symbol_pair + " on: " + str(datetime.now()), empty_data=[])
    if not order['fills'] and not open_orders: # if both of these conditions fail after order went through most likely means that more processing time (on Binance servers) is needed to process open_order (unlikely but possible that open_order was created and executed in the span of ~4 lines of code) # maybe refactor might be able to use 'executedQty'
        time.sleep(open_time)
        open_orders = _fetch_data(binance_client.get_open_orders, params={'symbol': symbol_pair}, error_str=" - Binance open orders error for symbol pair: " + symbol_pair + " on: " + str(datetime.now()), empty_data=[])
    trade_notes = "Filled" if (order['fills'] and not open_orders) else "Not filled" if (not order['fills'] and open_orders) else "Partially filled" if (order['fills'] and open_orders) else "~Filled" # if have open_time > 0 can most likely (high probability) assume that if no order['fills'] and no open_orders that order has been Filled, but keep as precautionary (might be a failure on Binance servers in creating open_order or an API documentation change), should always check balances / assets
    message_body = "Q Trading @crypto: " + symbol_pair + " " + (trade if trade else side) + " at price_in_btc " + str(price_in_btc) + " and price $" + str(price) + " and quantity " + str(quantity) + ", " + str(other_notes) + ", " + trade_notes + (" :)" if trade_notes == "Filled" else " :/" if trade_notes == "Partially filled" else " :(")
    color_start, color_end = ["\033[92m", "\033[0m"] if trade_notes in ["Filled", "~Filled"] else ["\033[33m", "\033[0m"] if trade_notes == "Partially filled" else ["\033[91m", "\033[0m"] # green yellow red # last condition is if "Not filled" or "BTrade Error"
    print("executed binance_trade_coin_btc()\n" + color_start + message_body + color_end + "\n\033[1mOrder:\033[0m " + str(order) + "\n\033[1mOpen orders:\033[0m" + str(open_orders))
    twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': message_body}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None) # No need to add message_body here and other cases to error_str since already printed in line before # maybe add logic here and other locations to deal with error - possibly e-mailing through another client
    return [quantity, price, price_in_btc, order, open_orders, trade_notes] # can add check if order['fills'] 'qty'(s) equal quantity

def kucoin_check_24h_vol_and_price_in_usdt(symbol_pair, kucoin_usdt_24h_vol, price, kucoin_price, kucoin_usdt_24h_vol_min=50000, kucoin_price_mismatch_limit=0.05):
    kucoin_usdt_24h_vol_too_low, kucoin_price_mismatch = kucoin_usdt_24h_vol <= kucoin_usdt_24h_vol_min, abs((kucoin_price - price) / price) >= kucoin_price_mismatch_limit
    if kucoin_usdt_24h_vol_too_low or kucoin_price_mismatch:
        message_body = "Q Trading @crypto: " + symbol_pair + (" Kucoin 24h vol is less than " + str(kucoin_usdt_24h_vol_min) + "," if kucoin_usdt_24h_vol_too_low else "") + (" Kucoin price is more than " + str(kucoin_price_mismatch_limit*100) + "% different than CoinGecko price" if kucoin_price_mismatch else "") + " on: " + str(datetime.now()) + ", not buying :(" + (", but maybe arbitrage :/" if kucoin_price_mismatch else "") # :/ at end for logic
        print("\033[95m" + message_body + "\033[0m")
        twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': message_body}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None)
    return [kucoin_usdt_24h_vol_too_low, kucoin_price_mismatch]

# if add other exchanges can change name to exchange_check_btc_24h_vol_and_price, maybe add pump and dump check
def binance_check_24h_vol_and_price_in_btc(symbol_pair, binance_btc_24h_vol_in_btc, price_in_btc, binance_price_in_btc, binance_btc_24h_vol_in_btc_min=5, binance_price_in_btc_mismatch_limit=0.05):
    binance_btc_24h_vol_in_btc_too_low, binance_price_in_btc_mismatch = binance_btc_24h_vol_in_btc <= binance_btc_24h_vol_in_btc_min, abs((binance_price_in_btc - price_in_btc) / price_in_btc) >= binance_price_in_btc_mismatch_limit # binance_price_in_btc_mismatch could be sign of less demand for coin or different coin type listed on Binance (both compared to other exchanges), ... , don't want to buy coin if mispriced, wait for price to normalize # maybe add logic for arbitrage opportunities
    if binance_btc_24h_vol_in_btc_too_low or binance_price_in_btc_mismatch:
        message_body = "Q Trading @crypto: " + symbol_pair + (" Binance 24h vol is less than " + str(binance_btc_24h_vol_in_btc_min) + "," if binance_btc_24h_vol_in_btc_too_low else "") + (" Binance price is more than " + str(binance_price_in_btc_mismatch_limit*100) + "% different than CoinGecko price" if binance_price_in_btc_mismatch else "") + " on: " + str(datetime.now()) + ", not buying :(" + (", but maybe arbitrage :/" if binance_price_in_btc_mismatch else "") # :/ at end for logic
        print("\033[95m" + message_body + "\033[0m")
        twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': message_body}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None)
    return [binance_btc_24h_vol_in_btc_too_low, binance_price_in_btc_mismatch]

# if only for exchange arbitrage, no shorting and assuming can buy and sell at either exchange/market
def exchange_check_arbitrage(price, other_price, arbitrage_roi_min=0.05):
    buy_price, sell_price = price if price <= other_price else other_price, other_price if other_price > price else price # long logic, no shorting
    arbitrage_opportunity = (sell_price - buy_price) / buy_price
    if abs(arbitrage_opportunity) >= arbitrage_roi_min:
        return [True, arbitrage_opportunity]
    return [False, arbitrage_opportunity]

def kucoin_usdt_check_arbitrages(pages=10):
    # coins_symbol_to_id, binance_btc_pairs_api_less_same_symbol_and_api_errors = {}, []
    arbitrage_pairs = Counter()
    kucoin_pairs_with_price_and_vol_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={})
    coins = _fetch_data(get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={}) # faster than iterating through binance pairs and retrieving price for each coin, allows for more flexibility with exchanges etc.
    for coin_id, symbol_and_market_data in coins.items(): # refactor, some coins have the same symbol, find a way to select first occurence of symbol, issues with FTT and HOT
        # coin_data = _fetch_data(get_coin_data, params={'coin': coin['id']}, error_str=" - No " + "" + " coin data for: " + coin['id'], empty_data={})
        # if not coin_data or not ('market_data' in coin_data and 'btc' in coin_data['market_data']['current_price']):
        #     print("Error retreiving market data for coin: " + coin + " on: " + str(datetime.now()))
        #     continue
        price, symbol_pair = symbol_and_market_data['price'], symbol_and_market_data['symbol'].upper() + '-USDT' #  if 'Price' in coin else float("NaN")
        # coins_symbol_to_id[coin['symbol']] = coin['id']
        if (symbol_pair in kucoin_pairs_with_price_and_vol_current):
            # binance_btc_pairs_api_less_same_symbol_and_api_errors.append(symbol_pair)
            kucoin_price = kucoin_pairs_with_price_and_vol_current[symbol_pair]['price'] if symbol_pair in kucoin_pairs_with_price_and_vol_current else float("NaN") # *(binance_pairs_with_price_current['BTCUSDT'] if 'BTCUSDT' in binance_pairs_with_price_current else float("NaN")) # price, = coin_data['market_data']['current_price']['btc'],
            arbitrage, arbitrage_opportunity = exchange_check_arbitrage(price=price, other_price=kucoin_price)
            if arbitrage:
                arbitrage_pairs[symbol_pair] = arbitrage_opportunity
    return arbitrage_pairs

def binance_btc_check_arbitrages(pages=1):
    # coins_symbol_to_id, binance_btc_pairs_api_less_same_symbol_and_api_errors = {}, []
    arbitrage_pairs = Counter()
    binance_btc_api_error_coins = {'chat': 'chatcoin', 'btt': 'bittorrent-2', 'sub': 'substratum', 'salt': 'salt', 'phx': 'red-pulse-phoenix', 'tusd': 'true-usd', 'pax': 'paxos-standard', 'npxs': 'pundi-x', 'dent': 'dent', 'wings': 'wings', 'cloak': 'cloakcoin', 'bcn': 'bytecoin', 'cocos': 'cocos-bcx', 'mft': 'mainframe', 'dgd': 'digixdao', 'key': 'selfkey', 'win': 'wink', 'ncash': 'nucleus-vision', 'rpx': 'red-pulse', 'ven': 'vechain-old-erc20', 'hsr': 'hshare', 'storm': 'storm', 'mod': 'modum', 'bchsv': 'bitcoin-cash-sv', 'icn': 'ic-node', 'trig': 'triggers', 'btcb': 'bitcoinbrand', 'bcc': 'bitcoincash-classic', 'bchabc': 'bitcoin-cash', 'edo': 'eidoo'} # rpx&hsr&storm&bchsv&icn&trig&btcb&bcc unsure of coin id (usually using coingecko.com/en/coins/coin_id) but has to do with red-pulse(-phoenix)&hshare&storm(x)&bitcoin(-cash)-sv&ic-node&triggers&bitcoinbrand/bitcoin-bep2&bitcoincash-classic, 'pnt': 'penta'/'penta-network-token', 'yoyo'(binance)/'yoyow'(coingecko), # api_error or coin is delisted/new name or type of token or not shown on Binance website as of 07/01/2020 # maybe refactor and add binance_btc_api_error_coins to other functions so these coins are updated and avoided - for now assuming that if coin is in top 250 (with rr algorithm) shouldn't have these problems
    binance_pairs_with_price_current = get_binance_pairs()
    coins = _fetch_data(get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={}) # faster than iterating through binance pairs and retrieving price for each coin, allows for more flexibility with exchanges etc.
    for coin_id, symbol_and_market_data in coins.items(): # refactor, some coins have the same symbol, find a way to select first occurence of symbol, issues with FTT and HOT
        # coin_data = _fetch_data(get_coin_data, params={'coin': coin['id']}, error_str=" - No " + "" + " coin data for: " + coin['id'], empty_data={})
        # if not coin_data or not ('market_data' in coin_data and 'btc' in coin_data['market_data']['current_price']):
        #     print("Error retreiving market data for coin: " + coin + " on: " + str(datetime.now()))
        #     continue
        price, symbol_pair = symbol_and_market_data['price'], symbol_and_market_data['symbol'].upper() + 'BTC'
        # coins_symbol_to_id[coin['symbol']] = coin['id']
        if (symbol_pair in binance_pairs_with_price_current) and (symbol_and_market_data['symbol'] not in binance_btc_api_error_coins.keys()):
            # binance_btc_pairs_api_less_same_symbol_and_api_errors.append(symbol_pair)
            binance_price = binance_pairs_with_price_current[symbol_pair] # *(binance_pairs_with_price_current['BTCUSDT'] if 'BTCUSDT' in binance_pairs_with_price_current else float("NaN")) # price, = coin_data['market_data']['current_price']['btc'],
            arbitrage, arbitrage_opportunity = exchange_check_arbitrage(price=price, other_price=binance_price)
            if arbitrage:
                arbitrage_pairs[symbol_pair] = arbitrage_opportunity
    return arbitrage_pairs

def update_portfolio_postions_back_testing(portfolio, stop_day, end_day, **params):
    STOP_LOSS = portfolio['constants']['sl']
    BASE_PAIR = portfolio['constants']['base_pair'] # 'btc' # portfolio['constants']['base_pair'] # maybe refactor and add to other functions so that can avoid +'BTC' or +'-USDT' and coin_data['market_data']['current_price']['btc'/'usdt']
    TRAILING_STOP_LOSS_ARM, TRAILING_STOP_LOSS_PERCENTAGE = portfolio['constants']['tsl_a'], portfolio['constants']['tsl_p'] # TAKE_PROFIT_PERCENTAGE = 1.0
    # PRICE_UNCERTAINTY_PERCENTAGE = 0.05 # to reflect that can't always buy/sell at CoinGecko price and that stop loss and trailing stop loss orders can't always be fulfilled at the exact percentage and that real trading prices are updated every 4 minutes vs. back_testing is every hour
    END_DAY_OPEN_POSITIONS_GTRENDS_15D, END_DAY_OPEN_POSITIONS_KUCOIN_USDT_24H_VOL = portfolio['constants']['end_day_open_positions_gtrends_15d'], portfolio['constants']['end_day_open_positions_kucoin_usdt_24h_vol']
    # binance_pairs_with_price_current = params['binance_pairs_with_price_current'] # maybe refactor here and other params[] and add logic for dealing with error ('binance_pairs_with_price_current' not in params)
    kucoin_pairs_with_price_and_vol_current = params['kucoin_pairs_with_price_and_vol_current']
    # sell if TSL or SL, update current positions (assume symbol doesn't change), update current google trends and/or binance btc 24h vol if conditions met, update current positions
    # print("Sleeping 2min every time we update portfolio positions back testing on: " + str(stop_day))
    # time.sleep(2*60)
    for coin in portfolio['open'].index: # print(str(stop_day) + "\n" + str(portfolio['open'].drop(['binance_btc_24h_vol(btc)', 'rank_rise_d', 'gtrends_15d'], axis=1))) # print("updating: " + coin, end=", ") # print("buying: " + coin, end=", ") # print(str(stop_day) + "\n" + str(portfolio['open'].drop(['position', 'buy_date', 'buy_price(btc)', 'balance'], axis=1)))
        # time is local time (PST) not utc time, price and time are in hourly intervals even within 24 hours
        # coin_data_granular = _fetch_data(get_coin_data_granular_cg, params={'coin': coin, 'currency': 'usd', 'from_timestamp': datetime.timestamp(stop_day - timedelta(days=1)), 'to_timestamp': datetime.timestamp(stop_day)}, error_str=" - No granular coin data for: " + coin + " from: " + str(stop_day - timedelta(days=1)) + " to: " + str(stop_day), empty_data={}) # if think in terms of ultimately accumulating btc can make currency 'btc' and have tsl/sl be in relation to btc rather than usd
        coin_data_granular_in_btc = _fetch_data(get_coin_data_granular, params={'coin': coin, 'currency': 'btc', 'from_timestamp': datetime.timestamp(stop_day - timedelta(days=1)), 'to_timestamp': datetime.timestamp(stop_day)}, error_str=" - No granular coin data for: " + coin + " from: " + str(stop_day - timedelta(days=1)) + " to: " + str(stop_day), empty_data={})
        if not ('prices' in coin_data_granular_in_btc and coin_data_granular_in_btc['prices']): # 'market_data' not in coin_data or not coin_data['market_data']['market_cap']['usd']: # remove granular from error_str
            print("Error retreiving granular market data for coin: " + coin + " on date: " + stop_day.strftime('%Y-%m-%d')) # error message should be covered in method
            portfolio['open'].loc[coin, 'other_notes'] = "MDI " +  stop_day.strftime('%Y-%m-%d') # MDI stands for Market Data Issue
        else:
            buy_price_in_btc, tsl_armed, tsl_max_price_in_btc, quantity = portfolio['open'].loc[coin, ['buy_price(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'balance']]
            symbol_pair = portfolio['open'].loc[coin, 'symbol'].upper() + '-USDT' # 'BTC'
            # can add price_trend or google_trend analysis
            for idx,timestamp_price_in_btc in enumerate(coin_data_granular_in_btc['prices']):
                price_in_btc, interval_time = timestamp_price_in_btc[1], datetime.fromtimestamp(timestamp_price_in_btc[0]/1000) # CoinGecko timestamp is off by factor of 1000
                price_in_btc_change = (price_in_btc - buy_price_in_btc) / buy_price_in_btc
                # if price_in_btc_change >= TAKE_PROFIT_PERCENTAGE:
                if not tsl_armed and price_in_btc_change >= TRAILING_STOP_LOSS_ARM:
                    tsl_armed, tsl_max_price_in_btc = True, price_in_btc
                if tsl_armed:
                    if price_in_btc > tsl_max_price_in_btc:
                        tsl_max_price_in_btc = price_in_btc
                    tsl_price_in_btc_change = (price_in_btc - tsl_max_price_in_btc) / tsl_max_price_in_btc
                    if tsl_price_in_btc_change <= TRAILING_STOP_LOSS_PERCENTAGE:
                        # coin_data_granular_in_btc = _fetch_data(get_coin_data_granular, params={'coin': coin, 'currency': 'btc', 'from_timestamp': datetime.timestamp(stop_day - timedelta(days=1)), 'to_timestamp': datetime.timestamp(stop_day)}, error_str=" - No granular coin data for: " + coin + " from: " + str(stop_day - timedelta(days=1)) + " to: " + str(stop_day), empty_data={}) # more time consuming (0.03 vs. 0.003) but more accurate than doing btc_data on stop_day and obtaining btc_price - would be the price for that stop_day (i.e. if sold 2020-06-01 20:00:00 PST btc_price will be (stop_day) btc_price: 2020-06-02 17:00:00 PST) # maybe refactor and check if 'prices' not in coin_data_granular for now let it fail during back_testing don't want to add logic for adding/replacing more important other_notes
                        sell_price_in_btc = price_in_btc # tsl_max_price * (1 + TRAILING_STOP_LOSS_PERCENTAGE) # use price even though Minutely data will be used for duration within 1 day, Hourly data will be used for duration between 1 day and 90 days, Daily data will be used for duration above 90 days, since tsl_max_price might also be a bit inaccurate # * (1 - PRICE_UNCERTAINTY_PERCENTAGE) # maybe refactor here and other change sell_price_in_btc to price_in_btc
                        coin_data = _fetch_data(get_coin_data, params={'coin': coin, 'date': (interval_time + timedelta(hours=7)).strftime('%d-%m-%Y'), 'historical': True, 'retry_current_if_no_historical_market_data': False}, error_str=" - No " + "historical" + " coin data for: " + coin + " on date: " + str(interval_time + timedelta(hours=7)), empty_data={}) # assuming here and other references that CoinGecko price not too much different from Kucoin
                        sell_price = coin_data['market_data']['current_price']['usd'] if ('market_data' in coin_data) and ('current_price' in coin_data['market_data']) and ('usd' in coin_data['market_data']['current_price']) else float("NaN")
                        monetary_return = sell_price*quantity if BASE_PAIR == 'usdt' else sell_price_in_btc*quantity
                        other_notes, trade_notes = 'Sell by TSL', None # maybe refactor not likely that market_data wont be in btc_data - other_notes[:2] + other_notes[7:9] gives you sUBP allows to see both notes # precautionary trade_notes while back_testing should always be None
                        portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + monetary_return # maybe refactor and add here and in all calls to adjusting portfolio['balance']['btc'] throughout a precautionary check for price_in_btc (since it's possible but rare that price_in_btc might be float("NaN")) and don't want one bad order to affect other orders
                        symbol, position, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d = portfolio['open'].loc[coin, ['symbol', 'position', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d']]
                        portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, interval_time, sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).append(pd.Series([coin, interval_time, sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, tsl_max_price_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin) # 'binance_btc_24h_vol(btc)', portfolio['open'].loc[coin, 'binance_btc_24h_vol(btc)'], 'binance_btc_24h_vol(btc)',
                        break # continue not break since want to check last conditional - (idx == len(coin_data_granular_in_btc['prices']) - 1)
                elif price_in_btc_change <= STOP_LOSS:
                    # coin_data_granular_in_btc = _fetch_data(get_coin_data_granular, params={'coin': coin, 'currency': 'btc', 'from_timestamp': datetime.timestamp(stop_day - timedelta(days=1)), 'to_timestamp': datetime.timestamp(stop_day)}, error_str=" - No granular coin data for: " + coin + " from: " + str(stop_day - timedelta(days=1)) + " to: " + str(stop_day), empty_data={})
                    sell_price_in_btc = price_in_btc # sell_price, sell_price_in_btc = price, coin_data_granular_in_btc['prices'][idx][1] # buy_price * (1 + STOP_LOSS) # use price even though Minutely data will be used for duration within 1 day, Hourly data will be used for duration between 1 day and 90 days, Daily data will be used for duration above 90 days, since buy_price might also be a bit inaccurate and unrealistic to sell at exact STOP_LOSS loss # * (1 - PRICE_UNCERTAINTY_PERCENTAGE)
                    coin_data = _fetch_data(get_coin_data, params={'coin': coin, 'date': (interval_time + timedelta(hours=7)).strftime('%d-%m-%Y'), 'historical': True, 'retry_current_if_no_historical_market_data': False}, error_str=" - No " + "historical" + " coin data for: " + coin + " on date: " + str(interval_time + timedelta(hours=7)), empty_data={}) # assuming here and other references that CoinGecko price not too much different from Kucoin
                    sell_price = coin_data['market_data']['current_price']['usd'] if ('market_data' in coin_data) and ('current_price' in coin_data['market_data']) and ('usd' in coin_data['market_data']['current_price']) else float("NaN")
                    monetary_return = sell_price*quantity if BASE_PAIR == 'usdt' else sell_price_in_btc*quantity
                    other_notes, trade_notes = 'Sell by SL', None # maybe refactor not likely that market_data wont be in btc_data - other_notes[:2] + other_notes[7:9] gives you sUBP allows to see both notes # precautionary trade_notes while back_testing should always be None
                    portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + monetary_return
                    symbol, position, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d = portfolio['open'].loc[coin, ['symbol', 'position', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d']]
                    portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, interval_time, sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).append(pd.Series([coin, interval_time, sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, tsl_max_price_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin) # 'binance_btc_24h_vol(btc)', portfolio['open'].loc[coin, 'binance_btc_24h_vol(btc)'], 'binance_btc_24h_vol(btc)',
                    break
                if (idx == len(coin_data_granular_in_btc['prices']) - 1): # some days ends earlier than 16:59 like 2020-06-08 ends 15:59 (fet), 16:12 (edo), 16:29 (stmx, bnt) issue with coingecko data (but also when when run on different occasions returns different results for same day i.e. with end_day 6/14/2020 and different start days (6/17/2020 and same start days) return different end times)
                    if stop_day == end_day:
                        # if END_DAY_OPEN_POSITIONS_KUCOIN_USDT_24H_VOL and (symbol_pair in kucoin_pairs_with_price_and_vol_current) and (stop_day.date() == datetime.now().date()): # maybe refactor - stop_day.date() == datetime.now().date() is a bit inaccurate (can make accurate to the hour or minute) # uses old/incomplete information - not np.isnan(portfolio['open'].loc[coin, 'binance_btc_24h_vol(btc)'])
                            # portfolio['open'].loc[coin, 'binance_btc_24h_vol(btc)'] = float(_fetch_data(binance_client.get_ticker, params={'symbol': symbol_pair}, error_str=" - Binance get ticker error for symbol pair: " + symbol_pair + " on: " + str(datetime.now().date()), empty_data={'quoteVolume': "NaN"})['quoteVolume']) # *binance_pairs_with_price_current['BTCUSDT'] # here, buying have to account for error if coin is no longer listed on binance # binance_client.get_ticker other useful keys 'bidPrice', 'bidQty', 'askPrice', 'askQty' OHLV
                        if END_DAY_OPEN_POSITIONS_GTRENDS_15D:
                            coin_search_term = coin if not re.search('-', coin) else coin.split("-")[0]  # precautionary returns coin or coin symbol, assuming coins are unique to tickers / other similar search terms
                            # using Pytrends (Cryptory is deprecated doesn't work after Python 3.6-3.8) since good data and can retrieve other metrics like reddit subscribers, exchange rates, metal prices
                            google_trends = _fetch_data(get_google_trends_pt, params={'kw_list': [coin_search_term], 'from_date': stop_day - timedelta(days=15), 'to_date': stop_day}, error_str=" - No " + "google trends" + " data for coin search term: " + coin_search_term + " from: " + str(stop_day - timedelta(days=15)) + " to: " + str(stop_day), empty_data=pd.DataFrame())
                            google_trends_slope = trendline(google_trends.sort_values('date', inplace=False, ascending=True)[coin_search_term]) if not google_trends.empty else float("NaN") # sort_values is precautionary, should already be ascending:  # , reverse_to_ascending=True
                            portfolio['open'].loc[coin, 'gtrends_15d'] = google_trends_slope
                    portfolio['open'].loc[coin, ['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)']] = [interval_time, price_in_btc, price_in_btc_change, tsl_armed, tsl_max_price_in_btc]
    # print("Sleeping 1min every time after updating portfolio positions back testing on: " + str(stop_day))
    # time.sleep(1*60)
    return portfolio

def update_portfolio_buy_and_sell_coins(portfolio, coins_to_buy, coins_to_sell, stop_day, end_day, paper_trading, back_testing, **params): # refactor and add back_testing
    BASE_PAIR = portfolio['constants']['base_pair'] # if not back_testing else 'btc'
    INVEST, INVEST_MIN = portfolio['constants'][BASE_PAIR.lower() + '_invest'], portfolio['constants'][BASE_PAIR.lower() + '_invest_min']
    BUY_DATE_GTRENDS_15D = portfolio['constants']['buy_date_gtrends_15d']
    coins_to_avoid = {'jupiter': 'CoinGecko issues ie price is $0.001469126328981041 on 2024-03-21 17:00:00 when it should be $1.24 (confuses with Jupiter Dex token jupiter-ag / jupiter-project)', 'flux': 'CoinGecko issues ie price is $0.08684909049706278 on 2024-03-21 17:00:00 when it should be $1.38 (correct id is flux-zelcash, flux is incorrect id)'}
    # binance_pairs_with_price_current = params['binance_pairs_with_price_current']
    if not back_testing:
        coins_data = _fetch_data(get_coins_markets_coinmarketcap, params={'pages': 10}, error_str=" - No " + "" + " coins markets data with pages: " + str(10) + " on: " + str(datetime.now()), empty_data={})
        coins_symbol_to_id = {**{'btc': 'bitcoin', 'bnb': 'binancecoin', 'fet': 'fetch-ai', 'kmd': 'komodo', 'cnd': 'cindicator', 'coti': 'coti', 'tfuel': 'theta-fuel', 'tomo': 'tomochain', 'gto': 'gifto', 'btg': 'bitcoin-gold'}, **{symbol_and_market_data['symbol']: coin_id for coin_id, symbol_and_market_data in coins_data.items()}}
        coins_id_to_symbol = {value: key for key,value in coins_symbol_to_id.items()}
    kucoin_pairs_with_price_and_vol_current = params['kucoin_pairs_with_price_and_vol_current']
    retry_end_day_if_no_historical_market_data = True if datetime.utcnow() >= (end_day + timedelta(hours=7)) and datetime.utcnow() <= (end_day + timedelta(hours=7+1)) else False # if run between closing and 1 hour after closing time and historical market_data for stop day (next day in utc time) day not available allow retry on current day, useful if want to make trades within that hour
    for coin, market_cap_rank_change in coins_to_sell:
        symbol_pair = portfolio['open'].loc[coin, 'symbol'].upper() + '-USDT' # maybe refactor, -USDT here and below to make kucoin_trade_coin_usdt() logic easier # maybe refactor all and change balance variable name to order_quantity
        position, buy_price_in_btc, quantity = portfolio['open'].loc[coin, ['position', 'buy_price(btc)', 'balance']] # maybe refactor, buy_price_in_btc here so only one call for both 'buy_price(btc)', 'balance' to portfolio.loc[]
        if back_testing:
            sell_date, sell_price_in_btc, roi_in_btc, other_notes = portfolio['open'].loc[coin, ['current_date', 'current_price(btc)', 'current_roi(btc)', 'other_notes']] # binance_btc_24h_vol_in_btc, 'binance_btc_24h_vol(btc)', # not using slightly more accurate price with coin_data['market_data']['current_price']['usd'] and date using stop_day (16:.. vs. 17 PST) since then have to retrieve coin_data and recalculate roi
            # coin_data = _fetch_data(get_coin_data, params={'coin': coin, 'date': (stop_day + timedelta(hours=7)).strftime('%d-%m-%Y'), 'historical': True, 'retry_current_if_no_historical_market_data': retry_end_day_if_no_historical_market_data}, error_str=" - No " + "historical" + " coin data for: " + coin + " on date: " + str(stop_day + timedelta(hours=7)), empty_data={})
            # sell_price_in_btc, other_notes_extra = [coin_data['market_data']['current_price']['btc'], None] if ('market_data' in coin_data and 'btc' in coin_data['market_data']['current_price']) else [sell_price/binance_pairs_with_price_current['BTCUSDT'], "sUsing BPrice"]
            coin_data = _fetch_data(get_coin_data, params={'coin': coin, 'date': (stop_day + timedelta(hours=7)).strftime('%d-%m-%Y'), 'historical': True, 'retry_current_if_no_historical_market_data': retry_end_day_if_no_historical_market_data}, error_str=" - No " + "historical" + " coin data for: " + coin + " on date: " + str(stop_day + timedelta(hours=7)), empty_data={'market_data':{'current_price':{'usd':float("NaN")}}}) # maybe refactor empty_data here and in get_kucoin_assets()
            sell_price, trade_notes = coin_data['market_data']['current_price']['usd'] if ('market_data' in coin_data) and ('current_price' in coin_data['market_data']) and ('usd' in coin_data['market_data']['current_price']) else float("NaN"), None # other_notes if not other_notes_extra else other_notes_extra[:2] + other_notes_extra[7:9] + str(other_notes), None # only concatenate other_notes strings while back_testing since MDI issue notes only occur during back_testing, should be taken care of if back_testing and then real time trading, other_notes_extra[:2] + other_notes_extra[7:9] gives you sUBP allows to see both notes # precautionary trade_notes while back_testing should always be None
        else: # no need to worry about back running (if back running and algorithm has gotten to the current day) - stop_day.date() == datetime.now().date()
            #  binance_btc_24h_vol_in_btc , float(_fetch_data(binance_client.get_ticker, params={'symbol': symbol_pair}, error_str=" - Binance get ticker error for symbol pair: " + symbol_pair + " on date: " + str(datetime.now().date()), empty_data={})['quoteVolume']) # *binance_pairs_with_price_current['BTCUSDT'] # maybe refactor - add back binance_btc_24h_vol_in_btc if want to check for pump and dump but complicates matters when checking for buying and selling
            # coin_data = _fetch_data(get_coin_data, params={'coin': coin}, error_str=" - No " + "" + " coin data for: " + coin + " on: " + str(datetime.now()), empty_data={})
            # sell_price_in_btc, other_notes = [coin_data['market_data']['current_price']['btc'], None] if ('market_data' in coin_data and 'btc' in coin_data['market_data']['current_price']) else [binance_pairs_with_price_current[symbol_pair], "sUsing BPrice"] # sell_price, coin_data['market_data']['current_price']['usd'], ('usd' and , binance_pairs_with_price_current[symbol_pair]*binance_pairs_with_price_current['BTCUSDT'], # maybe refactor and add MDI Issue note to other_notes (but only if other_notes not occupied) # assuming selling at 17 PST and that order is filled near coingecko price (maybe refactor)
            quantity, price, price_in_btc, kucoin_coin_usdt_order, kucoin_coin_usdt_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="sell", quantity=quantity, paper_trading=(True if position == 'long-p' else False)) # binance_coin_btc_order, binance_coin_btc_open_orders,  # paper_trading
            sell_price, sell_price_in_btc, sell_date, other_notes = price, price_in_btc, datetime.now(), None
            roi_in_btc = (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc
        portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + sell_price*quantity # keep variable balance here so don't have to add more code for when not back_testing, in general balance used for when retrieving value from portfolio, quantity used when calculating value or value returned after submitting an order # (sell_price / btc_price)
        # coin_data already retrieved in current_date, current_price, current_roi # can use np.append(coin, portfolio['open'].loc[coin, [...]].to_numpy())
        symbol, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc = portfolio['open'].loc[coin, ['symbol', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_max_price(btc)']]
        portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, sell_date, sell_price, sell_price_in_btc, roi_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'trade_notes', 'other_notes']).append(pd.Series([coin, sell_date, sell_price, sell_price_in_btc, roi_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin) # 'binance_btc_24h_vol(btc)', binance_btc_24h_vol_in_btc, 'binance_btc_24h_vol(btc)',
    for coin, market_cap_rank_change in coins_to_buy: # coins_market_cap_rank_change_by_factor.items()
        if portfolio['balance'][BASE_PAIR] >= INVEST_MIN and (coin not in coins_to_avoid): # can add max open positions and a waiting list to reflect real trading: # assuming always enforcing BTC_INVEST_MIN # maybe refactor, logic here and not in run_portfolio_algorithm to keep logic simple (even though makes tickers_to_buy/sell lists longer) # maybe refactor if insufficient balance and signals are indicating a buy can add positions as a long-p then buy when balance opens up
            invest = INVEST if (portfolio['balance'][BASE_PAIR] >= INVEST) else portfolio['balance'][BASE_PAIR]
            if back_testing:
                coin_data = _fetch_data(get_coin_data, params={'coin': coin, 'date': (stop_day + timedelta(hours=7)).strftime('%d-%m-%Y'), 'historical': True, 'retry_current_if_no_historical_market_data': retry_end_day_if_no_historical_market_data}, error_str=" - No " + "historical" + " coin data for: " + coin + " on date: " + str(stop_day + timedelta(hours=7)), empty_data={})
            else:
                coin_data = _fetch_data(get_coin_data, params={'coin': coin}, error_str=" - No " + "" + " coin data for: " + coin + " on: " + str(datetime.now()), empty_data={}) # retrieving coin_data even when not back_testing as a double check for market cap rank and to retreive symbol, input price_in_btc for function binance_check_24h_vol_and_price_in_btc
            # error with some coins (bitbay), if these 2 conditions aren't meant usually indicate larger issues with the coin, further if error retreiving market cap rank whole basis for algorithm falls apart (market cap rank is meaningless)
            if back_testing and not (('market_data' in coin_data) and coin_data['market_data']['market_cap']['usd'] and coin_data['market_data']['current_price']['btc']): # refactor can probably get rid of coin_data['market_data']['market_cap']['usd'] / 'usd'/'btc' in coin_data['market_data']['market_cap']/['current_price']
                print("Error retreiving initial market data for coin: " + coin + " on date: " + stop_day.strftime('%Y-%m-%d'))
            else: # don't add coin if issue retreiving market_data
                # can add other exchanges
                if back_testing:
                    symbol, symbol_pair = coin_data['symbol'], coin_data['symbol'].upper() + '-USDT' # maybe refactor name to btc_symbol_pair or just symbol_pair like other instances
                else:
                    if coin not in coins_id_to_symbol:
                        continue
                    symbol, symbol_pair = coins_id_to_symbol[coin], coins_id_to_symbol[coin].upper() + '-USDT'
                if symbol_pair in kucoin_pairs_with_price_and_vol_current: # binance_pairs_with_price_current # not retrieving new prices since whole function should execute (if done over one DAYS period) quickly
                    if back_testing:
                        price_in_btc, price = coin_data['market_data']['current_price']['btc'], coin_data['market_data']['current_price']['usd'] # maybe refactor -  assuming that if 'market_data' in coin_data and coin_data['market_data']['market_cap']['usd'] ('usd' and 'btc') in coin_data['market_data']['current_price'] also in there
                    else:
                        price, btc_price = kucoin_pairs_with_price_and_vol_current[symbol_pair]['price'], kucoin_pairs_with_price_and_vol_current['BTC-USDT']['price']
                        price_in_btc = price / btc_price
                    if (price > invest): # simpler to put this logic here rather than in binance_trade_coin_btc() (and make it continue here if trade_notes == "BTrade Error" or something similar) # maybe refactor - don't want to buy fractions of a coin for now
                        continue
                    if back_testing: # maybe refactor and put this logic into function binance_trade_coin_btc, maybe also include binance_check_24h_vol_and_price_in_btc in back_testing purchases
                        buy_date, kucoin_usdt_24h_vol, quantity, trade_notes = stop_day, float("NaN"), math.floor(invest / price) if invest > 10 else math.ceil(invest / price), None # btc_price / price # assuming buying at 17 PST and that order is filled near coingecko price (maybe refactor) # precautionary keep > 0.001 in case BTC_INVEST_MIN is set below this amount # can get historical total_volume (exchange-weighted 24h_vol) with coin_data['market_data']['total_volume']['usd'] but can't get historical binance_btc_24h_vol (Binance symbol_pair 24h_vol) therefore doesn't match / reflect stocks.py
                    else:
                        kucoin_usdt_24h_vol = kucoin_pairs_with_price_and_vol_current[symbol_pair]['24h_volume'] # float("NaN") # binance_btc_24h_vol_in_btc = float("NaN") # float(_fetch_data(binance_client.get_ticker, params={'symbol': symbol_pair}, error_str=" - Binance get ticker error for symbol pair: " + symbol_pair + " on date: " + str(datetime.now().date()), empty_data={'quoteVolume': "NaN"})['quoteVolume']) # *binance_pairs_with_price_current['BTCUSDT'] # don't check for - if stop_day.date() == datetime.now().date() else None since no back running # a bit inaccurate (can make accurate to hour or minute)
                        kucoin_usdt_24h_vol_too_low, kucoin_price_mismatch = kucoin_check_24h_vol_and_price_in_usdt(symbol_pair=symbol_pair, kucoin_usdt_24h_vol=kucoin_usdt_24h_vol, price=price, kucoin_price=price) if (kucoin_usdt_24h_vol > 0) else [True, True] # refactor not checking CoinGecko price since issue with API as of 2023 so kucoin_price_mismatch is 0
                        # binance_btc_24h_vol_in_btc_too_low, binance_price_in_btc_mismatch = binance_check_24h_vol_and_price_in_btc(symbol_pair=symbol_pair, binance_btc_24h_vol_in_btc=binance_btc_24h_vol_in_btc, price_in_btc=price_in_btc, binance_price_in_btc=binance_pairs_with_price_current[symbol_pair]) if (binance_btc_24h_vol_in_btc > 0) else [True, True] # *binance_pairs_with_price_current['BTCUSDT']
                        if kucoin_usdt_24h_vol_too_low or kucoin_price_mismatch: # binance_btc_24h_vol_in_btc_too_low, binance_price_in_btc_mismatch
                            continue
                        quantity, price, price_in_btc, kucoin_coin_usdt_order, kucoin_coin_usdt_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="buy", usdt_invest=invest, price_in_btc=price_in_btc, paper_trading=paper_trading) # binance_coin_btc_order, binance_coin_btc_open_orders # maybe refactor and change binance_coin_btc... to binance_btc_..., binance_coin_btc may be good to reflect importance (exchange order)
                        buy_date = datetime.now() # if not back_testing buying when run the algorithm, also if back running need to use datetime.now() and if real time running datetime.now() is closer to time order is processed due to api request limits, processing, etc.
                    if BUY_DATE_GTRENDS_15D:
                        coin_search_term = coin if not re.search('-', coin) else coin.split("-")[0]  # precautionary returns coin or coin symbol, assuming coins are unique to tickers / other similar search terms
                        google_trends = _fetch_data(get_google_trends_pt, params={'kw_list': [coin_search_term], 'from_date': stop_day - timedelta(days=15), 'to_date': stop_day}, error_str=" - No " + "google trends" + " data for coin search term: " + coin_search_term + " from: " + str(stop_day - timedelta(days=15)) + " to: " + str(stop_day), empty_data=pd.DataFrame())
                        google_trends_slope = trendline(google_trends.sort_values('date', inplace=False, ascending=True)[coin_search_term]) if not google_trends.empty else float("NaN") # sort_values is precautionary, should already be ascending:  # , reverse_to_ascending=True
                    else:
                        google_trends_slope = 0
                    portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] - price*quantity # btc value not entirely accurate in real time and doesn't take into account distribution tokens but close enough to prevent trades from executing if underbudget, also don't check assets since want to allocate full btc value to coin # (price / btc_price) # a bit more accurate than using just btc_invest since rounding for quantity: quantity = math.floor(btc_invest*btc_price / price)
                    portfolio['open'].loc[coin, ['symbol', 'position', 'balance', 'buy_price', 'buy_date', 'buy_price(btc)', 'current_date', 'current_price(btc)', 'current_roi(btc)', 'rank_rise_d', 'gtrends_15d', 'kucoin_usdt_24h_vol', 'tsl_armed', 'trade_notes']] = [symbol, ('long' if not paper_trading else 'long-p'), quantity] + [price] + [buy_date, price_in_btc]*2 + [0, market_cap_rank_change, google_trends_slope, kucoin_usdt_24h_vol, False, trade_notes] # 'binance_btc_24h_vol(btc)'
    return portfolio

def run_portfolio_rr(portfolio, start_day=None, end_day=None, rr_sell=True, paper_trading=True, back_testing=False): # start_day and end_day are datetime objects # can get rid of back_testing parameter and add logic like start_day.date() < (end_day - timedelta(days=DAYS)).date(), # maybe refactor rr_buy/sell to algo_buy/sell if add more algorithms
    print("running run_portfolio_rr()")
    UP_MOVE, DOWN_MOVE = portfolio['constants']['up_down_move'], -portfolio['constants']['up_down_move']
    DAYS = portfolio['constants']['days']
    COINS_TO_ANALYZE, RANK_RISE_D_BUY_LIMIT = portfolio['constants']['coins_to_analyze'], portfolio['constants']['rank_rise_d_buy_limit'] # limit here is capitalized since it is a portfolio constant
    # binance_pairs_with_price_current = {pair_price['symbol']: float(pair_price['price'] if ('price' in pair_price) and pair_price['price'] else "NaN") for pair_price in _fetch_data(binance_client.get_all_tickers, params={}, error_str=" - Binance get all tickers error on: " + str(datetime.now()), empty_data=[])} # maybe refactor and change to a different api source to figure out which symbol_pairs are listed on Binance, for now this is ok, a bit buggy / outdated
    kucoin_pairs_with_price_and_vol_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={})
    end_day = end_day if end_day else datetime.now().replace(hour=17, minute=0, second=0, microsecond=0) # better to be on utc time, PST 17h is 24h UTC time, CoinGecko historical saves in UTC time # maybe refactor and make start/stop/end_datetime instead of start/stop/end_day
    start_day = start_day if start_day else end_day - timedelta(days=DAYS) # not this - datetime.strptime('2020_02_24 17:00:00', '%Y_%m_%d %H:%M:%S') - since back_testing=False (default)
    stop_day = start_day + timedelta(days=DAYS) # if running in real time stop_day should be almost equivalent (minus processing times) to datetime.now() # maybe refactor and make it stop_day = start_day - timedelta(days=DAYS) so easier to restart from last date, but then have to worry about data before start_day, have to worry about other logic in this function, other algorithms
    if (back_testing and not paper_trading) or (not back_testing and (stop_day.date() != datetime.now().date())): # ((start_day.date() < (end_day - timedelta(days=DAYS)).date()) or (end_day.date() < datetime.now().date())) #  precautionary - if back_testing, doesn't matter if paper_trading is set to True or False, just, don't allow back running
        print("Error (backtesting and not paper trading) or back running")
        return portfolio
    while stop_day.date() <= end_day.date():
        if not (portfolio['open']['current_date'] >= stop_day).any(): # in case re-run existing portfolio over same days to avoid back running (and conserve time): avoid selling existing coins incorrectly to TSL (too early) due to tsl_max_price set on future day or selling/buying existing/new coins incorrectly with algorithm logic # assuming datetime is always in 17:00:00
            if back_testing:
                portfolio = update_portfolio_postions_back_testing(portfolio=portfolio, stop_day=stop_day, end_day=end_day, kucoin_pairs_with_price_and_vol_current=kucoin_pairs_with_price_and_vol_current)
            if rr_sell or (portfolio['balance']['usd'] >= portfolio['constants']['usd_invest_min']):
                df_coins_interval_start, df_coins_interval_stop = get_saved_coins_data(date=(stop_day - timedelta(days=DAYS)).strftime('%Y-%m-%d')).iloc[:COINS_TO_ANALYZE], get_saved_coins_data(date=stop_day.strftime('%Y-%m-%d')).iloc[:COINS_TO_ANALYZE] # maybe refactor and make option to limit amount of coins to analyze
                # buy if coin increases in market cap rank by UP_MOVE over DAYS, sell if coin decreases by DOWN_MOVE over DAYS
                if not (df_coins_interval_start.empty or df_coins_interval_stop.empty):
                    # can also add google trends, reddit possibly chart first coordinate with price timestamp
                    coins_to_buy, coins_to_sell = [], [] # multi-dimensional array [coin, market_cap_rank_change] # coins_market_cap_rank_change_by_factor = Counter()
                    for coin in df_coins_interval_stop.index:
                        new_market_cap_rank = df_coins_interval_stop.loc[coin, 'Market Cap Rank']
                        try: # if else statement same number of lines
                            market_cap_rank_change = df_coins_interval_start.loc[coin, 'Market Cap Rank'] - new_market_cap_rank
                        except Exception as e: # print(str(e) + " - Could not get historical saved market cap rank for: " + coin)
                            market_cap_rank_change = min(len(df_coins_interval_start), len(df_coins_interval_stop)) - new_market_cap_rank if math.isclose(len(df_coins_interval_stop), len(df_coins_interval_start), rel_tol=((UP_MOVE/2)/max(len(df_coins_interval_start), len(df_coins_interval_stop)))) else float("NaN") # min() and max() to be conservative - leads to lower rank_rise and lower rel_tol, assuming same_symbol_coins are up to date # len(df_coins_interval_start) - new_market_cap_rank because # don't add UP_MOVE/DOWN_MOVE to be safe # rel_tol is relative to the larger absolute value of len(df_coins_interval_stop) or len(df_coins_interval_start) # len(df_coins_interval_stop) == len(df_coins_interval_start)
                        if (coin not in portfolio['open'].index) and (market_cap_rank_change >= UP_MOVE) and (market_cap_rank_change <= RANK_RISE_D_BUY_LIMIT): # rr_buy and
                            coins_to_buy.append([coin, market_cap_rank_change])
                        elif rr_sell and (coin in portfolio['open'].index) and (portfolio['open'].loc[coin, 'trade_notes'] in ["Filled", "~Filled", None]) and (market_cap_rank_change <= DOWN_MOVE): # can add short logic # not accounting for if there is a market data issue (MDI when backtesting) - if sell price and roi doesn't reflect actual, can try to postpone selling by a day # (market_cap_rank_change <= DOWN_MOVE) and
                            coins_to_sell.append([coin, market_cap_rank_change]) # coins_market_cap_rank_change_by_factor[coin] = market_cap_rank_change
                    for coin in list(set(df_coins_interval_start.index.values) - set(df_coins_interval_stop.index.values)): # important to keep this logic for coins which are delisted or name / id changes
                        if rr_sell and (coin in portfolio['open'].index):
                            # if coin not in new dataframe assume it has fallen out of top coins: min(len(df_coins_interval_start), len(df_coins_interval_stop)) - DOWN_MOVE (to be safe, and DOWN_MOVE assumed to be negative value)
                            coins_to_sell.append([coin, df_coins_interval_start.loc[coin, 'Market Cap Rank'] - (min(len(df_coins_interval_start), len(df_coins_interval_stop)) - DOWN_MOVE)]) # if rr_sell else None # market_cap_rank_change unused and inaccurate but still saving # coins_market_cap_rank_change_by_factor[coin] = df_coins_interval_start.loc[coin, 'Market Cap Rank'] - (len(df_coins_interval_start) - DOWN_MOVE)
                    if (coins_to_buy or coins_to_sell):
                        portfolio = update_portfolio_buy_and_sell_coins(portfolio=portfolio, coins_to_buy=coins_to_buy, coins_to_sell=coins_to_sell, stop_day=stop_day, end_day=end_day, paper_trading=paper_trading, back_testing=back_testing, kucoin_pairs_with_price_and_vol_current=kucoin_pairs_with_price_and_vol_current)
        else:
            print("skipping " +  str(stop_day) + " since portfolio has already run on this date")
        stop_day = stop_day + timedelta(days=1)
    return portfolio

def get_kucoin_assets(account_type="trade", other_coins_symbol_to_id=None, pages=10):
    # main_account, trade_account = {}, {}
    trade_assets = pd.DataFrame(columns=['symbol','balance','balance_locked','current_date','current_price','current_value','current_price(btc)','current_value(btc)','other_notes']).astype({'symbol':'object','balance':'float64','balance_locked':'float64','current_date':'datetime64[ns]','current_price':'float64','current_value':'float64','current_price(btc)':'float64','current_value(btc)':'float64','other_notes':'object'})
    accounts = _fetch_data(kucoin_client.get_accounts, params={}, error_str=" - Kucoin get account error on: " + str(datetime.now()), empty_data={}) # account gets updated after each trade # maybe refactor and include binance_client here and in other functions as a parameter
    coins_data = _fetch_data(get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={})
    coins_symbol_to_id = {**{'btc': 'bitcoin', 'bnb': 'binancecoin', 'fet': 'fetch-ai', 'kmd': 'komodo', 'cnd': 'cindicator', 'coti': 'coti', 'tfuel': 'theta-fuel', 'tomo': 'tomochain', 'gto': 'gifto', 'btg': 'bitcoin-gold'}, **{symbol_and_market_data['symbol']: coin_id for coin_id, symbol_and_market_data in coins_data.items()}}
    if other_coins_symbol_to_id:
        coins_symbol_to_id = {**coins_symbol_to_id, **other_coins_symbol_to_id} # maybe refactor and always add assets symbols & ids to coins_symbol_to_id, not sure about processing time: dict(zip(list(assets['symbol']), list(assets.index.values)))
    kucoin_pairs_with_price_and_vol_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={})
    for account in accounts:
        # if account['type'] == 'main' and float(account['balance']) > 0.0:
            # main_account[account['currency']] = {'balance': float(account['balance']), 'available': float(account['available']), 'holds': float(account['holds'])}
        if account['type'] == account_type and float(account['balance']) > 0.0:
            symbol = account['currency'].lower()
            balance_free, balance_locked = float(account['available']), float(account['holds'])
            price, btc_price = 1.0 if account['currency'] == "USDT" else kucoin_pairs_with_price_and_vol_current[account['currency'] + '-USDT']['price'], kucoin_pairs_with_price_and_vol_current['BTC-USDT']['price'] # maybe refactor add fail safes
            price_in_btc = price / btc_price
            coin = coins_symbol_to_id[symbol] if symbol in coins_symbol_to_id else symbol
            trade_assets.loc[coin, ['symbol','balance','balance_locked','current_date','current_price','current_value','current_price(btc)','current_value(btc)']] = [symbol, balance_free, balance_locked, datetime.now(), price, price*(balance_free+balance_locked), price_in_btc, price_in_btc*(balance_free+balance_locked)] # trade_account = {'balance': float(account['balance']), 'available': float(account['available']), 'holds': float(account['holds'])}
    return trade_assets

# assets 'FET', 'KMD' leftover from qtrading and cryptohopper trades (unable to trade such a small amount), 'TFUEL' because THETA funds in your account on May 2020, Unsure about 'TOMO' but small amount and not always in top 250 so needed since sometimes: 504 Server Error: Gateway Time-out, 'GTO' and 'BTG' because not part of portfolio (part of arbitrage) keep getting KeyError: 'btg'/'gto' when have 504 Server Error: Gateway Time-out
def get_binance_assets(other_coins_symbol_to_id=None, pages=10): # maybe refactor, don't pass in portfolio since assets should have current open positions in portfolio and new added positions should be in Binance top 250, but possible if run function without assets previously loaded and a coin in assets on Binance is no longer in Binance top 250 (algorithm should sell at 17PST if coin falls out of top 250 but still possible)
    print("getting binance assets") # maybe refactor to "running get_binance_assets()"
    assets = pd.DataFrame(columns=['symbol','balance','balance_locked','current_date','current_price','current_value','current_price(btc)','current_value(btc)','other_notes']).astype({'symbol':'object','balance':'float64','balance_locked':'float64','current_date':'datetime64[ns]','current_price':'float64','current_value':'float64','current_price(btc)':'float64','current_value(btc)':'float64','other_notes':'object'})
    account = _fetch_data(binance_client.get_account, params={}, error_str=" - Binance get account error on: " + str(datetime.now()), empty_data={}) # account gets updated after each trade # maybe refactor and include binance_client here and in other functions as a parameter
    if not account or not ('balances' in account): # only case if Binance server error, precautionary check - 'balances' in account
        print("Error retrieving account from Binance")
        return assets
    binance_pairs_with_price_current = get_binance_pairs()
    coins_symbol_to_id = {**{'btc': 'bitcoin', 'bnb': 'binancecoin', 'fet': 'fetch-ai', 'kmd': 'komodo', 'cnd': 'cindicator', 'coti': 'coti', 'tfuel': 'theta-fuel', 'tomo': 'tomochain', 'gto': 'gifto', 'btg': 'bitcoin-gold'}, **{symbol_and_market_data['symbol']: coin_id for coin_id, symbol_and_market_data in _fetch_data(get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={}).items()}}
    if other_coins_symbol_to_id:
        coins_symbol_to_id = {**coins_symbol_to_id, **other_coins_symbol_to_id} # maybe refactor and always add assets symbols & ids to coins_symbol_to_id, not sure about processing time: dict(zip(list(assets['symbol']), list(assets.index.values)))
    for asset in account['balances']:
        balance_free, balance_locked = float(asset['free'] if ('free' in asset) and asset['free'] else "NaN"), float(asset['locked'] if ('locked' in asset) and asset['locked'] else "NaN") # locked balance means it's an order pending # precautionay checking for ('free'/'locked' in asset) and asset['free'/'locked'] # "NaN" here and below so that doesn't throw error when adding to to assets DataFrame
        if balance_free > 0:
            symbol_pair, symbol = asset['asset'] + 'BTC', asset['asset'].lower()
            # btc/coin prices are quoted in the price of the given exchange not coingecko, and converted to usd with exchange usdt/btc (not the way coingecko does it)
            price_in_btc = 1.0 if symbol == 'btc' else binance_pairs_with_price_current[symbol_pair] if symbol_pair in binance_pairs_with_price_current else float("NaN")
            price = price_in_btc*binance_pairs_with_price_current['BTCUSDT'] if 'BTCUSDT' in binance_pairs_with_price_current else float("NaN")
            coin = coins_symbol_to_id[symbol] if symbol in coins_symbol_to_id else symbol # maybe refactor - cheap fix for now
            assets.loc[coin, ['symbol','balance','balance_locked','current_date','current_price','current_value','current_price(btc)','current_value(btc)']] = [symbol, balance_free, balance_locked, datetime.now(), price, price*(balance_free+balance_locked), price_in_btc, price_in_btc*(balance_free+balance_locked)]
            if balance_locked > 0:
                print(asset['asset'] + " has locked balance of: " + str(balance_locked))
    return assets

def portfolio_align_balance_with_exchange(portfolio, exchange_assets, exchange):
    BASE_PAIR = portfolio['constants']['base_pair']
    base_pair_id = 'tether' if BASE_PAIR == 'usdt' else 'bitcoin'
    if base_pair_id not in exchange_assets.index:
        portfolio_balance_previous, portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR], 0
        print("Portfolio Available " + BASE_PAIR.upper() + " Balance (before correction): " + str(portfolio_balance_previous) + ", (after correction): " + str(portfolio['balance'][BASE_PAIR]))
    elif (base_pair_id in exchange_assets.index) and (exchange_assets.loc[base_pair_id, 'balance'] != portfolio['balance'][BASE_PAIR]): # maybe refactor and check for balance locked # quick fix to keep portfolio['balance']['usd'] accurate and conservative since alpaca_account.buying_power fluctuating (think due to margin alpaca_account)
        portfolio_balance_previous, portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR], exchange_assets.loc[base_pair_id, 'balance']
        print("Portfolio Available " + BASE_PAIR.upper() + " Balance (before correction): " + str(portfolio_balance_previous) + ", (after correction): " + str(portfolio['balance'][BASE_PAIR]))
    print("portfolio aligned balance " + BASE_PAIR + " with " + exchange + ", " + "Portfolio Available " + BASE_PAIR.upper() + " Balance: " + str(portfolio['balance'][BASE_PAIR]))
    return portfolio

# can also use rate of return (takes into account time), a little bit deceiving if add new investment which has 0% return intuition says it shouldn't draw ROI down but it does since cost of investment increases but net value of investments - cost of investment stays the same
def portfolio_calculate_roi(portfolio, open_positions=True, sold_positions=False, avoid_paper_positions=False):
    value_of_current_investments, value_of_sold_investments, cost_of_investments = 0, 0, 0 # maybe refactor here and below to avoid divide by zero errors
    if open_positions:
        for coin in portfolio['open'].index:
            if avoid_paper_positions and (portfolio['open'].loc[coin, 'position'] == 'long-p'):
                continue
            current_price_in_btc, buy_price_in_btc, balance = portfolio['open'].loc[coin, ['current_price(btc)', 'buy_price(btc)', 'balance']] # maybe refactor and multiply columns and sum
            value_of_current_investments += current_price_in_btc*balance
            cost_of_investments += buy_price_in_btc*balance
    if sold_positions: # maybe refactor and use portfolio['balance']['btc']
        for idx in portfolio['sold'].index:
            if avoid_paper_positions and (portfolio['sold'].loc[idx, 'position'] == 'long-p'):
                continue
            sell_price_in_btc, buy_price_in_btc, balance = portfolio['sold'].loc[idx, ['sell_price(btc)', 'buy_price(btc)', 'balance']] # maybe refactor and multiply columns and sum
            value_of_sold_investments += sell_price_in_btc*balance
            cost_of_investments += buy_price_in_btc*balance
    if cost_of_investments: # maybe refactor here and below, to deal with if only paper_trades issue (divide by zero)
        return (value_of_current_investments + value_of_sold_investments - cost_of_investments) / cost_of_investments
    else:
        return float("NaN")


# maybe refactor, pause buying / terminate program
def portfolio_panic_sell(portfolio, df_matching_open_positions): # , paper_trading - paper_trading would be precautionary since function shouldn't be called if paper trading # , , idx_start, idx_end):
    BASE_PAIR = portfolio['constants']['base_pair']
    for coin,row in df_matching_open_positions.iterrows(): # if don't use iterrows(): coin = df_matching_open_positions.index[0]
        symbol_pair, other_notes = row['symbol'].upper() + '-USDT', 'Panic Sell' # 'BTC'
        position, buy_price_in_btc, quantity = row[['position', 'buy_price(btc)', 'balance']] # portfolio['open'].loc[coin, ['buy_price(btc)', 'balance']]
        quantity, price, price_in_btc, kucoin_coin_usdt_order, kucoin_coin_usdt_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="sell", quantity=quantity, paper_trading=(True if position == 'long-p' else False), other_notes=other_notes) # binance_coin_btc_order, binance_coin_btc_open_orders,  # paper_trading
        sell_price_in_btc, sell_price = price_in_btc, price # maybe refactor and remove sell_date, place datetime.now() in portfolio['sold'], portfolio['open'] = ... line, good here for now since panic sells seem to have a longer delay (1.5-2.5 seconds) than other sells (1-1.5 seconds)
        roi_in_btc = (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc
        portfolio['balance'][BASE_PAIR] = (portfolio['balance'][BASE_PAIR] + sell_price*quantity) if BASE_PAIR == 'usdt' else (portfolio['balance'][BASE_PAIR] + sell_price_in_btc*quantity) # here and other locations where making calculations after alpaca_trade_ticker(): quantity should always == balance when quantity specified in binance_trade_coin_btc() since if quantity given then that quantity is used no matter what # (sell_price / btc_price)
        symbol, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc = row[['symbol', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_max_price(btc)']]
        portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, datetime.now(), sell_price, sell_price_in_btc, roi_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'trade_notes', 'other_notes']).append(pd.Series([coin, datetime.now(), sell_price, sell_price_in_btc, roi_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin)
    return portfolio
    # don't add retry logic for now, this would mean that I would have to keep the program running after panic_sell() finishes running, which would not be normal, can add retry_binance_open_orders_in_portfolio() if change my mind

def retry_exchange_open_orders_in_portfolio(portfolio, exchange_open_orders, exchange_client, exchange, open_order_price_difference_limit=0.15):
    exchange_pairs_with_price_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={}) if exchange == "kucoin" else get_binance_pairs()
    BASE_PAIR = portfolio['constants']['base_pair']
    for open_order in exchange_open_orders:
        symbol, side = open_order['symbol'].split("-")[0].lower(), open_order['side']
        if exchange == "kucoin":
            symbol_pair, original_quantity, executed_quantity, order_id, order_time = open_order['symbol'], float(open_order['size']), float(open_order['dealSize']), open_order['id'], datetime.fromtimestamp(open_order['createdAt']/1000)
            price = exchange_pairs_with_price_current[symbol_pair]['price']
        else:
            symbol_pair, original_quantity, executed_quantity, order_id, order_time = open_order['symbol'], float(open_order['origQty']), float(open_order['executedQty']), open_order['orderId'], datetime.fromtimestamp(open_order['time']/1000) # binance exchange original_quantity should be same here and below in portfolio['open'/'sold'].loc[coin, [... call
            price_in_btc = exchange_pairs_with_price_current[symbol_pair] if symbol_pair in exchange_pairs_with_price_current else float("NaN")
        df_matching_open_positions = portfolio['open'][(portfolio['open']['position'] == 'long') & (portfolio['open']['symbol'] == symbol) & (portfolio['open']['trade_notes'].isin(["Not filled", "Partially filled", "~Filled"]))]
        df_matching_sold_positions = portfolio['sold'][(portfolio['sold']['position'] == 'long') & (portfolio['sold']['symbol'] == symbol) & (portfolio['sold']['trade_notes'].isin(["Not filled", "Partially filled", "~Filled"])) & (portfolio['sold']['sell_date'] <= order_time + timedelta(minutes=10)) & (portfolio['sold']['sell_date'] >= order_time - timedelta(minutes=10))]
        params = {'order_id': order_id} if exchange == "kucoin" else {'symbol': symbol_pair, 'orderId': order_id}
        if not df_matching_open_positions.empty:
            coin = df_matching_open_positions.index[0]
            buy_price, buy_price_in_btc, original_quantity = portfolio['open'].loc[coin, ['buy_price', 'buy_price(btc)', 'balance']]
            balance = original_quantity - executed_quantity # , executed_quantity = , original_quantity - remaining_quantity
            if exchange == "kucoin":
                incremental_invest = (price - buy_price)*balance
                price_differential = (price - buy_price) / buy_price
            else:
                incremental_invest = (price_in_btc - buy_price_in_btc)*balance
                price_differential = (price_in_btc - buy_price_in_btc) / buy_price_in_btc
            if (incremental_invest <= portfolio['balance'][BASE_PAIR]) and (price_differential <= open_order_price_difference_limit):
                resp = _fetch_data(exchange_client.cancel_order, params=params, error_str=" - " + exchange.capitalize() + " cancel order error for symbol pair: " + symbol_pair + " and order ID: " + str(order_id) + " on: " + str(datetime.now()), empty_data={}) # maybe refactor unnecessary if order['fills']
                resp_status = resp['cancelledOrderIds'] if exchange == "kucoin" else resp['status'] == 'CANCELED'
                if resp and resp_status: # maybe refactor and add error for logic if order is not cancelled # cancelled is more British English, canceled is more American English, Binance uses canceled, grammarly.com/blog/canceled-vs-cancelled
                    original_price_in_btc, original_price = buy_price_in_btc, buy_price
                    quantity, price, price_in_btc, exchange_coin_pair_order, exchange_coin_pair_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, side=side, quantity=balance, paper_trading=False, other_notes="Retrying open order for coin " + coin + " bought on " + str(order_time)) if exchange == "kucoin" else binance_trade_coin_btc(symbol_pair=symbol_pair, side=side, quantity=balance, paper_trading=False, other_notes="Retrying open order for coin " + coin + " bought on " + str(order_time)) #
                    new_price_in_btc, new_price = (price_in_btc*quantity + original_price_in_btc*executed_quantity) / original_quantity, (price*quantity + original_price*executed_quantity) / original_quantity
                    incremental_invest = (price - buy_price)*quantity if BASE_PAIR == 'usdt' else (price_in_btc - buy_price_in_btc)*quantity # incremental_btc_invest = (price_in_btc - buy_price_in_btc)*quantity # maybe refactor and take out recalculation of incremental_btc_invest, only recalculate since price_in_btc is a bit more recent
                    portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] - incremental_invest
                    portfolio['open'].loc[coin, ['buy_date', 'buy_price', 'buy_price(btc)', 'trade_notes', 'other_notes']] = [datetime.now(), new_price, new_price_in_btc, trade_notes, "Retried order"] # update buy_date in case new order is incomplete # not tracking how many times retrying order too much logic for unlikely situation (unlikely that will need to retry more than once if adjust price after an hour) # No need to update current_price, current_roi, tsl_armed since in portfolio_trading() skipping positions
        if not df_matching_sold_positions.empty: # maybe refactor and add precautionary check - shouldn't have to check len() == 1 since symbol, trade_notes and order_time time frame (+/- 10 minutes)
            idx = df_matching_sold_positions.index[0]
            coin, sell_price, sell_price_in_btc, buy_price_in_btc, original_quantity = portfolio['sold'].loc[idx, ['coin', 'sell_price', 'sell_price(btc)', 'buy_price(btc)', 'balance']]
            balance = original_quantity - executed_quantity
            if exchange == "kucoin":
                price_differential = (price - sell_price) / sell_price
            else:
                price_differential = (price_in_btc - sell_price_in_btc) / sell_price_in_btc
            if price_differential >= -open_order_price_difference_limit: # (price_in_btc - sell_price_in_btc) / sell_price_in_btc # *binance_pairs_with_price_current['BTCUSDT'] # maybe refactor don't need abs() since new price < old price
                resp = _fetch_data(exchange_client.cancel_order, params=params, error_str=" - " + exchange.capitalize() + " cancel order error for symbol pair: " + symbol_pair + " and order ID: " + str(order_id) + " on: " + str(datetime.now()), empty_data=[]) # maybe refactor unnecessary if order['fills']
                resp_status = resp['cancelledOrderIds'] if exchange == "kucoin" else resp['status'] == 'CANCELED'
                if resp and resp_status: # cancelled is more British English, canceled is more American English, Binance uses canceled
                    original_price_in_btc, original_price = sell_price_in_btc, sell_price
                    quantity, price, price_in_btc, exchange_coin_pair_order, exchange_coin_pair_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, side=side, quantity=balance, paper_trading=False, other_notes="Retrying open order for coin " + coin + " sold on " + str(order_time)) if exchange == "kucoin" else binance_trade_coin_btc(symbol_pair=symbol_pair, side=side, quantity=balance, paper_trading=False, other_notes="Retrying open order for coin " + coin + " sold on " + str(order_time)) #
                    new_price_in_btc, new_price = (price_in_btc*quantity + original_price_in_btc*executed_quantity) / original_quantity, (price*quantity + original_price*executed_quantity) / original_quantity
                    new_roi_in_btc = (new_price_in_btc - buy_price_in_btc) / buy_price_in_btc # maybe refactor to (be consistent with other sell_price_in_btc's) new_sell_price_in_btc = new_price_in_btc and (new_sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc
                    decreased_return = (sell_price - price)*quantity if BASE_PAIR == 'usdt' else (sell_price_in_btc - price_in_btc)*quantity # maybe refactor and add abs(), should always be positive if still open order and using limit order and even if negative (if the price suddenly drops in between checking for open orders and price) logic should still work
                    portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] - decreased_return
                    portfolio['sold'].loc[idx, ['sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'trade_notes', 'other_notes']] = [datetime.now(), new_price, new_price_in_btc, new_roi_in_btc, trade_notes, "Retried order"] # maybe refactor and move "Retried Order" notes into trade_notes somehow # update sell_date in case new order is incomplete even if new executed quantity is less than original executed quantity
    return portfolio

def retry_exchange_trade_error_or_paper_orders_in_portfolio(portfolio, exchange, df_matching_open_positions, df_matching_sold_positions, paper_trading, exchange_trade_error_or_paper_order_price_difference_limit=0.15):
    BASE_PAIR = portfolio['constants']['base_pair']
    INVEST_MIN = portfolio['constants'][BASE_PAIR.lower() + '_invest_min'] # BTC_INVEST, portfolio['constants']['btc_invest'],
    exchange_pairs_with_price_current = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={}) if exchange == "kucoin" else get_binance_pairs()
    error_message = "KTrade Error" if exchange == "kucoin" else "BTrade Error"
    for coin,row in df_matching_open_positions.iterrows(): # if not df_matching_open_positions.empty:
        symbol_pair = row['symbol'].upper() + ("-" if exchange == "kucoin" else "") + BASE_PAIR.upper()
        buy_price, buy_price_in_btc, balance, buy_date = row[['buy_price', 'buy_price(btc)', 'balance', 'buy_date']]
        if exchange == "kucoin":
            price = exchange_pairs_with_price_current[symbol_pair]['price'] if symbol_pair in exchange_pairs_with_price_current else float("NaN")
            price_differential = (price - buy_price) / buy_price
        else:
            price_in_btc = exchange_pairs_with_price_current[symbol_pair] if symbol_pair in exchange_pairs_with_price_current else float("NaN")
            price_differential = (price_in_btc - buy_price_in_btc) / buy_price_in_btc
        if (portfolio['balance'][BASE_PAIR] >= INVEST_MIN) and (price_differential <= exchange_trade_error_or_paper_order_price_difference_limit):
            invest = buy_price*balance if exchange == "kucoin" else buy_price_in_btc*balance
            invest = invest if (invest <= portfolio['balance'][BASE_PAIR]) else portfolio['balance'][BASE_PAIR]
            quantity, price, price_in_btc, exchange_coin_pair_order, exchange_coin_pair_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="buy", usdt_invest=invest, paper_trading=paper_trading, other_notes="Retrying " + (error_message if row['trade_notes'] == error_message else "Paper") + " order for coin " + coin + " bought on " + str(buy_date)  + " on: " + str(datetime.now())) if exchange == "kucoin" else binance_trade_coin_btc(symbol_pair=symbol_pair, trade="buy", btc_invest=invest, paper_trading=paper_trading, other_notes="Retrying " + (error_message if row['trade_notes'] == error_message else "Paper") + " order for coin " + coin + " bought on " + str(buy_date) + " on: " + str(datetime.now()))
            portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] - (price*quantity if exchange == "kucoin" else price_in_btc*quantity)
            portfolio['open'].loc[coin, ['position', 'buy_date', 'buy_price', 'buy_price(btc)', 'balance', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']] = [('long' if not paper_trading else 'long-p'), datetime.now(), price, price_in_btc, quantity, False, float("NaN"), trade_notes, ("Retried order-e" if row['trade_notes'] == error_message else "Retried order-p")]
    for idx,row in df_matching_sold_positions.iterrows():
        symbol_pair = row['symbol'].upper() + ("-" if exchange == "kucoin" else "") + BASE_PAIR.upper()
        sell_price, sell_price_in_btc, coin, balance, sell_date, buy_price_in_btc = row[['sell_price', 'sell_price(btc)', 'coin', 'balance', 'sell_date', 'buy_price(btc)']]
        if exchange == "kucoin":
            price = exchange_pairs_with_price_current[symbol_pair]['price'] if symbol_pair in exchange_pairs_with_price_current else float("NaN")
            price_differential = (price - sell_price) / sell_price
        else:
            price_in_btc = exchange_pairs_with_price_current[symbol_pair] if symbol_pair in exchange_pairs_with_price_current else float("NaN")
            price_differential = (price_in_btc - sell_price_in_btc) / sell_price_in_btc
        if price_differential >= -exchange_trade_error_or_paper_order_price_difference_limit:
            quantity, price, price_in_btc, exchange_coin_pair_order, exchange_coin_pair_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="sell", quantity=balance, paper_trading=False, other_notes="Retrying " + error_message + " order for coin " + coin + " sold on " + str(sell_date)) if exchange == "kucoin" else binance_trade_coin_btc(symbol_pair=symbol_pair, trade="sell", quantity=balance, paper_trading=False, other_notes="Retrying " + error_message + " order for coin " + coin + " sold on " + str(sell_date))
            roi_in_btc = (price_in_btc - buy_price_in_btc) / buy_price_in_btc
            portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + (price*quantity if exchange == "kucoin" else price_in_btc*quantity)
            portfolio['sold'].loc[idx, ['sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'trade_notes', 'other_notes']] = [datetime.now(), price, price_in_btc, roi_in_btc, trade_notes, "Retried order-e"]
    return portfolio

def portfolio_trading(portfolio, exchange, paper_trading=True, portfolio_usdt_value_negative_change_from_max_limit=-0.3, portfolio_current_roi_restart={'engaged': False, 'limit': 0.15}, download_and_save_coins_data=False): # refactor to mimick run_portfolio_rr # maybe add short logic # maybe refactor buying_disabled/paper_trading to be None/False as default and then change within function (or if specified) based on certain conditions # maybe refactor name of this variable and similar here and below to portfolio_current_roi_in_btc_restart
    DAYS = portfolio['constants']['days']
    STOP_LOSS = portfolio['constants']['sl']
    TRAILING_STOP_LOSS_ARM, TRAILING_STOP_LOSS_PERCENTAGE = portfolio['constants']['tsl_a'], portfolio['constants']['tsl_p']
    BASE_PAIR = portfolio['constants']['base_pair']
    while True:
        print("<< " + str(datetime.now()) + ", paper trading: " + str(paper_trading) + ", portfolio btc value (-)change from max limit: " + str(portfolio_usdt_value_negative_change_from_max_limit) + ", portfolio current roi restart: " + str(portfolio_current_roi_restart) + ", download and save coins data: " + str(download_and_save_coins_data) + " >>") #  + ", buying disabled: " + str(buying_disabled)
        start_time = time.time()
        if (datetime.utcnow().hour == 12) and (datetime.utcnow().minute < 4):
            twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': "Q Trading @crypto: running on " + str(datetime.now()) + " :)"}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None)
        if (datetime.utcnow().hour == 0) and (datetime.utcnow().minute < 12): # (datetime.utcnow().hour == 0) and (datetime.utcnow().minute < 4): # since runs every 4 minutes
            todays_date = datetime.now()
            df_coins_interval_today = get_saved_coins_data(date=todays_date.strftime('%Y-%m-%d'))
            if df_coins_interval_today.empty and download_and_save_coins_data:
                save_coins_data(date=todays_date.strftime('%Y-%m-%d')) # maybe refactor (especially if in timezone far off eastern), not using eastern since run late at night and could extend into next day (in eastern time) # On 07/06/2020: from 250 to 500 (pages=2) - binance btc pairs gain is 114-163, from 500 to 750/1000 (pages=3/4) - binance btc pairs gain is 163-167, but might include more exchanges in algorithm, also top 1-250/500 market cap was from $170B-$12M/$2M/$822K/$300K
            else:
                # df_coins_interval_today = get_saved_coins_data(date=todays_date.strftime('%Y-%m-%d'))
                while df_coins_interval_today.empty:
                    print("Sleeping 5min after checking for coins data on: " + str(datetime.now())) # mayb
                    time.sleep(5*60)
                    if datetime.now().minute >= 33: # implemented so that if no market data doesn't stop program from running normally # maybe refactor, 11 hours since if running on Friday next if statement might run on Saturday if data is not downloaded until 6am Saturday morning
                        break
                    df_coins_interval_today = get_saved_coins_data(date=todays_date.strftime('%Y-%m-%d'))
            print("Sleeping 1min after saving / checking for saved coins data on: " + str(datetime.now())) # maybe refactor to 2min
            time.sleep(1*60)
            if not paper_trading: # only align balance btc when not paper trading since when paper trading balance should be aligned with current (paper) trading not actual balance btc, aligning balance btc after switching over from paper trading to not paper trading helps to deal with delisted coins
                # assets = get_binance_assets(other_coins_symbol_to_id=dict(zip(list(portfolio['open']['symbol'].values) + list(portfolio['sold']['symbol'].values), list(portfolio['open'].index.values) + list(portfolio['sold']['coin'].values))), pages=4)
                assets = get_kucoin_assets(other_coins_symbol_to_id=dict(zip(list(portfolio['open']['symbol'].values) + list(portfolio['sold']['symbol'].values), list(portfolio['open'].index.values) + list(portfolio['sold']['coin'].values))))
                portfolio = portfolio_align_balance_with_exchange(portfolio, exchange_assets=assets, exchange=exchange) if not assets.empty else portfolio
            portfolio = run_portfolio_rr(portfolio=portfolio, start_day=(todays_date - timedelta(days=DAYS)), end_day=todays_date, paper_trading=paper_trading) # On 08/08/2020: rr algorithm went from analyzing top 250 coins by Market Cap to top 1000 coins by Market Cap # rr_buy=(True if not buying_disabled else False),
            save_portfolio_backup(portfolio) # very unlikely to fail before next save_portfolio_backup() but still saving because precautionary and updating portfolio
            twilio_message = _fetch_data(twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': "Q Trading @crypto: Coin data saved and run_portfolio_rr executed on: " + datetime.now().strftime('%Y-%m-%d') + " :)"}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None) # not sms messaging assets value since would require more (unnecessary) processing/logic since have Binance App on phone
        for coin in portfolio['open'].index:
            # better to have price from coingecko (crypto insurance companies use it, and it represents a wider more accurate picture of the price, also if price hits tsl/sl temporarily on one exchange might be due to a demand/supply anomaly), also common to trade to btc then send btc to another exchange and transfer to fiat there, issue: coingecko only updates every 4 minutes
            # coin_data, price_in_btc = _fetch_data(get_coin_data, params={'coin': coin}, error_str=" - No " + "" + " coin data for: " + coin + " on: " + str(datetime.now()), empty_data={}), None
            kucoin_pairs_with_price_and_vol_current, price_in_btc = _fetch_data(get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={}), None
            if kucoin_pairs_with_price_and_vol_current: # ('market_data' in coin_data) and coin_data['market_data']['market_cap']['usd'] and coin_data['market_data']['current_price']['btc']:
                btc_price, current_datetime = kucoin_pairs_with_price_and_vol_current['BTC-USDT']['price'], None
                try:
                    price = kucoin_pairs_with_price_and_vol_current[portfolio['open'].loc[coin, 'symbol'].upper() + "-USDT"]['price']
                    price_in_btc = price / btc_price
                except Exception as e:
                    price_in_btc = portfolio['open'].loc[coin, 'current_price(btc)'] # price / btc_price
                    price = price_in_btc * btc_price
                    current_datetime = portfolio['open'].loc[coin, 'current_date']
                    print(str(e) + " - Price issue(s) for coin: " + coin + " with symbol pair: " + str(portfolio['open'].loc[coin, 'symbol'].upper() + "-USDT"))
            #     price_in_btc = coin_data['market_data']['current_price']['btc']
            #     # print(coin + ": " + str(coin_data['market_data']['current_price']['usd']))
            else:
                print("Error retreiving Kucoin prices and volumes on: " + str(datetime.now()))
            if price_in_btc: # maybe refactor check for if 'position' == 'long'/'long-p' in case implement shorting, price to ensure price was calculated on coingecko
                if portfolio['open'].loc[coin, 'trade_notes'] in ["Not filled", "Partially filled", "KTrade Error"]: # maybe refactor quick fix for now since if using small TSL/SL sometimes price hits selling point before the ticker is bought, maybe refactor and only check for not in ['Filled', '~Filled'] - think computationally the same, maybe refactor and move up to right below for coin in portfolio['open'].index:
                    continue
                position, buy_price_in_btc, tsl_armed, tsl_max_price_in_btc, balance = portfolio['open'].loc[coin, ['position', 'buy_price(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'balance']]
                price_in_btc_change = (price_in_btc - buy_price_in_btc) / buy_price_in_btc
                symbol_pair = portfolio['open'].loc[coin, 'symbol'].upper() + '-USDT'
                if not tsl_armed and price_in_btc_change >= TRAILING_STOP_LOSS_ARM:
                    tsl_armed, tsl_max_price_in_btc = True, price_in_btc
                if tsl_armed:
                    if price_in_btc > tsl_max_price_in_btc:
                        tsl_max_price_in_btc = price_in_btc
                    tsl_price_in_btc_change = (price_in_btc - tsl_max_price_in_btc) / tsl_max_price_in_btc
                    if tsl_price_in_btc_change <= TRAILING_STOP_LOSS_PERCENTAGE: # should check if price on coingecko is equal/close to price in binance
                        print("<<<< COIN SOLD due to TSL >>>>")
                        other_notes = 'Sell by TSL'
                        quantity, price, price_in_btc, kucoin_coin_usdt_order, kucoin_coin_usdt_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="sell", quantity=balance, price_in_btc=price_in_btc, paper_trading=(True if position == 'long-p' else False), other_notes=other_notes + " at ~roi " + str(price_in_btc_change)) # ~ roi since roi calculated with CoinGecko price but real roi is with Binance price # paper_trading
                        sell_price, sell_price_in_btc = price, price_in_btc # sell_price, = price, coin_data['market_data']['current_price']['btc'],  # tsl_max_price * (1 + TRAILING_STOP_LOSS_PERCENTAGE) # maybe refactor - check if 'btc' in coin_data['market_data']['current_price'], should be if 'usd' in it, logic to check for it a bit cumbersome, also not sure if need to relabel price_in_btc as sell_price_in_btc (but looks good to be consistent with logic throughout)
                        portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + sell_price*quantity
                        symbol, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d = portfolio['open'].loc[coin, ['symbol', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d']]
                        portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, datetime.now(), sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).append(pd.Series([coin, datetime.now(), sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, tsl_max_price_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin)
                        continue
                elif price_in_btc_change <= STOP_LOSS: # should check if price on coingecko is equal/close to price in binance
                    print("<<<< COIN SOLD due to SL >>>>")
                    other_notes = 'Sell by SL'
                    quantity, price, price_in_btc, kucoin_coin_usdt_order, kucoin_coin_usdt_open_orders, trade_notes = kucoin_trade_coin_usdt(symbol_pair=symbol_pair, coin=coin, trade="sell", quantity=balance, price_in_btc=price_in_btc, paper_trading=(True if position == 'long-p' else False), other_notes=other_notes + " at ~roi " + str(price_in_btc_change)) # paper_trading
                    sell_price, sell_price_in_btc = price, price_in_btc # sell_price, = price, coin_data['market_data']['current_price']['btc'], # buy_price * (1 + STOP_LOSS)
                    portfolio['balance'][BASE_PAIR] = portfolio['balance'][BASE_PAIR] + sell_price*quantity
                    symbol, buy_date, buy_price, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d = portfolio['open'].loc[coin, ['symbol', 'buy_date', 'buy_price', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d']]
                    portfolio['sold'].loc[len(portfolio['sold'])], portfolio['open'] = [coin, symbol, position, buy_date, buy_price, buy_price_in_btc, quantity, datetime.now(), sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, kucoin_usdt_24h_vol, gtrends_15d, rank_rise_d, tsl_max_price_in_btc, trade_notes, other_notes], portfolio['open'].drop(coin) # portfolio['sold'], portfolio['open'] = portfolio['sold'].append(portfolio['open'].loc[coin].drop(['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).append(pd.Series([coin, datetime.now(), sell_price, sell_price_in_btc, (sell_price_in_btc - buy_price_in_btc) / buy_price_in_btc, tsl_max_price_in_btc, trade_notes, other_notes], index=['coin', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'])), ignore_index=True), portfolio['open'].drop(coin)
                    continue
                current_datetime = current_datetime if current_datetime else datetime.now()
                portfolio['open'].loc[coin, ['current_date', 'current_price(btc)', 'current_roi(btc)', 'tsl_armed', 'tsl_max_price(btc)']] = [current_datetime, price_in_btc, price_in_btc_change, tsl_armed, tsl_max_price_in_btc]
                # print("[ " + coin + ": " + " price change: " + str(price_change) + ", tsl armed: " + str(tsl_armed) + ", tsl max price: " + str(tsl_max_price) + ", execution time: " + str(time.time() - start_time) + " ]")
        if (datetime.utcnow().minute >= 30) and (datetime.utcnow().minute < 34): # runs once per hour at the end of the hour (since if save data or run algorithm at beginning of hour may have conflict since saving data and running algorithm takes time)
            if not paper_trading:
                assets = get_kucoin_assets(other_coins_symbol_to_id=dict(zip(list(portfolio['open']['symbol'].values) + list(portfolio['sold']['symbol'].values), list(portfolio['open'].index.values) + list(portfolio['sold']['coin'].values)))) # assets = get_binance_assets(...) # precautionary to have portfolio['sold'] values since coins should be sold completely (unless fractions remain due to distribution or if some remain due to incomplete order) (would show up as balance_locked)
                if not assets.empty:
                    portfolio, portfolio_usdt_value = portfolio_align_balance_with_exchange(portfolio, exchange_assets=assets, exchange=exchange), assets['current_value'].sum() # portfolio_align_balance_btc_with_binance(portfolio, binance_assets=assets) # and assets.loc['bitcoin', 'balance_locked'] == 0 # simple way to make sure bitcoin balance is correct every hour and to prevent orders
                    print(str(assets.drop(['other_notes'], axis=1)) + "\nTotal Current Value: " + str(assets['current_value'].sum()) + "\nTotal Current Value (BTC): " + str(assets['current_value(btc)'].sum()) + "\nExecution time: " + str(time.time() - start_time) + "\n")
                    print("Sleeping 2min after getting assets on: " + str(datetime.now())) # maybe refactor to 2min * make sure to make sure < 32min (next 30min ie 11:30am - current time ie 10:55am = 35/4 = 8.75 -> 0.75:31. 0.5:32, 0.25:33, 0:34)
                    time.sleep(2*60)
                else:
                    portfolio_usdt_value = float("NaN")
            else:
                portfolio_usdt_value = float("NaN") # portfolio_calculate_btc_value_while_paper_trading(portfolio) # float("NaN") since don't want portfolio_panic_sell() to execute while paper trading (if paper trading ride out the bad conditions) and if issue calculating assets might be a larger issue at hand and don't want to pause
            # arbitrage_pairs = kucoin_usdt_check_arbitrages(pages=4) # 4 pages gets you 190/~203 BTC pairs, anything above 4 is very incremental
            # print("Arbitrage pairs within +/- 50%: " + str(Counter({key: value for key,value in arbitrage_pairs.items() if abs(value) <= 0.5})) + "\n") # unrealistic that any arbitrage opportunities outside of 50% would exist, easy way to deal with coin scams, low volume traded coins, other logic issues
            kucoin_open_orders = _fetch_data(kucoin_client.get_orders, params={'status': 'active'}, error_str=" - Kucoin open orders error " + " on: " + str(datetime.now()), empty_data={'items':[]})['items'] # binance_open_orders = None # _fetch_data(binance_client.get_open_orders, params={}, error_str=" - Binance open orders error on: " + str(datetime.now()), empty_data=[]) # for coin in assets[assets['balance_locked'] > 0].index: # if assets['balance_locked'].any(): - balance_locked not the way since if btc is locked don't know what you're buying just know that you're using btc to buy it
            if kucoin_open_orders: # maybe refactor and looked at assets balance_locked, see if full balance is gone, if any locked make partial
                print("Kucoin open orders: " + str(kucoin_open_orders))
                portfolio = retry_exchange_open_orders_in_portfolio(portfolio=portfolio, exchange=exchange, exchange_client=kucoin_client, exchange_open_orders=kucoin_open_orders) # , paper_trading=paper_trading
                kucoin_open_orders = _fetch_data(kucoin_client.get_orders, params={'status': 'active'}, error_str=" - Kucoin open orders error " + " on: " + str(datetime.now()), empty_data={'items':[]})['items']
                print("Kucoin open orders (after): " + str(kucoin_open_orders) + "\nExecution time: " + str(time.time() - start_time) + "\n")
                kucoin_open_orders_coin_symbol = [open_order['symbol'].lower().split("-")[0] for open_order in kucoin_open_orders] # "btc"
                for coin in portfolio['open'][(portfolio['open']['position'] == 'long') & (~portfolio['open']['symbol'].isin(kucoin_open_orders_coin_symbol)) & (portfolio['open']['trade_notes'].isin(["Not filled", "Partially filled"]))].index:
                    portfolio['open'].loc[coin, 'trade_notes'] = "Filled"
                for idx in portfolio['sold'][(portfolio['sold']['position'] == 'long') & (~portfolio['sold']['symbol'].isin(kucoin_open_orders_coin_symbol)) & (portfolio['sold']['trade_notes'].isin(["Not filled", "Partially filled"]))].index:
                    portfolio['sold'].loc[idx, 'trade_notes'] = "Filled"
            else: # update orders completed but listed as incomplete incorrectly by binance_trade_coin_btc
                for coin in portfolio['open'].index:
                    if (portfolio['open'].loc[coin, 'position'] == "long") and (portfolio['open'].loc[coin, 'trade_notes'] in ["Not filled", "Partially filled"]): # no "BTrade Error" here since most likely the order did not go through at all
                        portfolio['open'].loc[coin, 'trade_notes'] = "Filled"
                for idx in portfolio['sold'].index:
                    if (portfolio['sold'].loc[idx, 'position'] == "long") and (portfolio['sold'].loc[idx, 'trade_notes'] in ["Not filled", "Partially filled"]):
                        portfolio['sold'].loc[idx, 'trade_notes'] = "Filled"
            # can also add updates for if assets go above or below a certain value
            df_matching_ktrade_error_open_positions, df_matching_ktrade_error_sold_positions = portfolio['open'][(portfolio['open']['position'] == 'long') & (portfolio['open']['trade_notes'] == "KTrade Error")], portfolio['sold'][(portfolio['sold']['position'] == 'long') & (portfolio['sold']['trade_notes'] == "KTrade Error")] # maybe refactor - checking outside of function because don't want function to be called unless it needs to be
            if not df_matching_ktrade_error_open_positions.empty or not df_matching_ktrade_error_sold_positions.empty:
                portfolio = retry_exchange_trade_error_or_paper_orders_in_portfolio(portfolio=portfolio, exchange=exchange, df_matching_open_positions=df_matching_ktrade_error_open_positions, df_matching_sold_positions=df_matching_ktrade_error_sold_positions, paper_trading=paper_trading)
            # not used when backtesting but ok since want portfolio that performs best through bad conditions and good conditions
            if not paper_trading and (portfolio_usdt_value > portfolio['max_value'][BASE_PAIR]): # maybe refactor not paper_trading quick fix # portfolio['balance']['max']['btc']
                portfolio['max_value'][BASE_PAIR] = portfolio_usdt_value
            if not paper_trading and ((portfolio_usdt_value - portfolio['max_value'][BASE_PAIR]) / portfolio['max_value'][BASE_PAIR] <= portfolio_usdt_value_negative_change_from_max_limit):
                df_matching_negative_current_roi_open_positions = portfolio['open'][(portfolio['open']['position'] == 'long') & (portfolio['open']['current_roi(btc)'] < 0)].sort_values('current_roi(btc)', inplace=False, ascending=True) # want to sell the most negative roi positions first
                portfolio = portfolio_panic_sell(portfolio=portfolio, df_matching_open_positions=df_matching_negative_current_roi_open_positions) # , paper_trading=paper_trading # portfolio=portfolio, paper_trading=True, idx_start=len(portfolio['open']) - 1, idx_end=len(portfolio['open']))
                paper_trading, portfolio_current_roi_restart['engaged'] = True, True
            if paper_trading and portfolio_current_roi_restart['engaged'] and (portfolio_calculate_roi(portfolio) > portfolio_current_roi_restart['limit']):
                assets = get_kucoin_assets(other_coins_symbol_to_id=dict(zip(list(portfolio['open']['symbol'].values) + list(portfolio['sold']['symbol'].values), list(portfolio['open'].index.values) + list(portfolio['sold']['coin'].values)))) # assets = get_binance_assets(...) # checking again for assets since possible retry_binance_open_orders_in_portfolio() or retry_exchange_trade_error_or_paper_orders_in_portfolio() executed orders and assets are altered
                if not assets.empty and (assets['current_value'].sum() >= portfolio['max_value'][BASE_PAIR]*(1+portfolio_usdt_value_negative_change_from_max_limit)): # precautionary, prioritizes portfolio sl over restarting real trading, prevents potential downward spiral but requires reset of portfolio_usdt_value_negative_change_from_max_limit unless there is enough momentum upon first restart (from paper to real trading)
                    print("Going from paper trading to real trading on: " + str(datetime.now()))
                    paper_trading, portfolio_current_roi_restart['engaged'] = False, False
                    df_matching_positive_current_roi_paper_open_positions = portfolio['open'][(portfolio['open']['position'] == 'long-p') & (portfolio['open']['current_roi(btc)'] > 0)].sort_values('current_roi(btc)', inplace=False, ascending=False) # maybe refactor - changed to only buy positive positions since after studying positive positions show best momentum (not most negative / relatively cheapest) (in the order of best momentum) - (to assets closest to 0 current_roi(btc))
                    portfolio = portfolio_align_balance_with_exchange(portfolio, exchange_assets=assets, exchange=exchange) # portfolio_align_balance_btc_with_binance(portfolio, binance_assets=assets)
                    portfolio = retry_exchange_trade_error_or_paper_orders_in_portfolio(portfolio=portfolio, exchange=exchange, df_matching_open_positions=df_matching_positive_current_roi_paper_open_positions, df_matching_sold_positions=pd.DataFrame(), paper_trading=paper_trading, exchange_trade_error_or_paper_order_price_difference_limit=10) # exchange_trade_error_or_paper_order_price_difference_limit=10 so that there is no upper limit
        # 'binance_btc_24h_vol(btc)' inspect below
        print(str(portfolio['open'].drop(['position', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'], axis=1)) + "\n" + str(portfolio['open'].drop(['symbol', 'buy_date', 'buy_price', 'buy_price(btc)', 'balance', 'current_date', 'current_price(btc)', 'current_roi(btc)'], axis=1)) + \
            "\nCurrent ROI (BTC) (Real): " + str(portfolio_calculate_roi(portfolio, avoid_paper_positions=True)) + "\nCurrent ROI (BTC) (All): " + str(portfolio_calculate_roi(portfolio)) + "\nExecution time: " + str(time.time() - start_time) + "\n" + \
            (str(portfolio['sold'].tail(40).drop(['symbol', 'buy_price(btc)', 'sell_price(btc)', 'kucoin_usdt_24h_vol', 'rank_rise_d', 'tsl_max_price(btc)', 'gtrends_15d', 'other_notes'], axis=1)) + \
            "\nSold ROI (BTC) (Real): " + str(portfolio_calculate_roi(portfolio, open_positions=False, sold_positions=True, avoid_paper_positions=True)) + "\nSold ROI (BTC) (All): " + str(portfolio_calculate_roi(portfolio, open_positions=False, sold_positions=True)) + \
            "\nPortfolio ROI (BTC) (Real): " + str(portfolio_calculate_roi(portfolio, open_positions=True, sold_positions=True, avoid_paper_positions=True)) + "\nPortfolio ROI (BTC) (All): " + str(portfolio_calculate_roi(portfolio, open_positions=True, sold_positions=True)) + "\nPortfolio Available " + BASE_PAIR.upper() + " Balance: " + str(portfolio['balance'][BASE_PAIR]) + "\n" if (datetime.utcnow().minute >= 30) and (datetime.utcnow().minute < 34) else ""))
        save_portfolio_backup(portfolio, remove_old_portfolio=(True if ((datetime.now().hour == 0) and (datetime.now().minute < 4)) else False)) # remove old portfolio always at beginning of next day (since portfolios are saved in local time, issue if local time is utc time then save_coins_data() will take too long for this logic to execute) (which is why not removing after run_portfolio_rr() executed) # save every 4 minutes for now, in case something happens
        time.sleep(240.0 - ((time.time() - start_time) % 240.0))

# as of 09/28/2020 changed portfolio_constants naming of file from (example) 100_100_15 to 100_-100_15
def save_portfolio_backup(portfolio, remove_old_portfolio=False): # can add logic for different types of portfolio i.e. rr with different kinds of parameters i.e. different up and down moves
    portfolio_constants = "_".join([str(value) if key != 'up_down_move' else str(value) + "_" + str(-value) for key,value in list(portfolio['constants'].items())]) # maybe refactor if implement different algorithms, for now all algorithms (currently only rr) have equal up_move and down_move and implement both up_move and down_move # if portfolio['constants']['type'] == 'rr' else "_".join([str(value) for key,value in list(portfolio['constants'].items())])
    if remove_old_portfolio: # (datetime.now().hour == 0) and (datetime.now().minute < 4)
        if os.path.exists('data/crypto/saved_portfolio_backups/' + 'portfolio_' + portfolio_constants + '_to_' + (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') + '.pckl'):
            os.remove('data/crypto/saved_portfolio_backups/' + 'portfolio_' + portfolio_constants + '_to_' + (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') + '.pckl')
    f = open('data/crypto/saved_portfolio_backups/' + 'portfolio_' + portfolio_constants + '_to_' + datetime.now().strftime('%Y-%m-%d') + '.pckl', 'wb') # 2020_06_02, format is '%Y-%m-%d'
    pd.to_pickle(portfolio, f)
    f.close()
    print("portfolio saved")
    return portfolio

def get_saved_portfolio_backup(portfolio_name): # portfolio name is portfolio_ + constants, like: portfolio_50_20_-0.3_0.5_-0.2_0.1_0.01_True_False_False # date is a string in format '%Y-%m-%d'
    try:
        f = open('data/crypto/saved_portfolio_backups/' + portfolio_name + '.pckl', 'rb')
        portfolio = pd.read_pickle(f)
        f.close()
    except Exception as e:
        print(str(e) + " - No saved portfolio backup with name: " + portfolio_name)
        # refactor better to have 'exchange', 'exchange_24h_vol', 'total_24h_vol', 'binance_btc_24h_vol(btc)' column works for now, maybe add column for 'price/volume_trend' (to eliminate coin pumps/pumps and dumps), social metrics trends (reddit subscribers, alexa rank, ...) # for column dtypes: both didn't work - dtype=[np.datetime64, np.float64, np.datetime64, np.float64]) # dtype=np.dtype([('datetime64','float64','datetime64','float6')])) # no need for portfolio['open_orders'] since tracking assets which has balance_locked (in order) # maybe refactor 'open' index to allow for multiple 'long' positions for the same coin but have to worry about portfolio['open'].loc[idx, ...], maybe refactor and change 'balance' to 'quantity' since portfolio not holding (meant to hold) onto assets for long term and each asset is not being refilled/sold incompletely (at least not intentionally) # if add short positions can change 'sold' to 'closed'
        portfolio = { # 100_100_15_[-0.3, 0.5, -0.2]_0.2_1_1000_1000
            'constants': {'base_pair': 'usdt', 'type': 'rr', 'up_down_move': 10, 'days': 10, 'sl': -0.15, 'tsl_a': 0.05, 'tsl_p': -0.0125, 'usdt_invest': 1000, 'usdt_invest_min': 100, 'coins_to_analyze': 1000, 'rank_rise_d_buy_limit': 1000, 'buy_date_gtrends_15d': True, 'end_day_open_positions_gtrends_15d': False, 'end_day_open_positions_kucoin_usdt_24h_vol': False, 'start_balance': {'usdt': 5000}, 'start_day': '2020-02-25'}, # assuming always enforcing btc_invest_min # maybe refactor move btc_invest and btc_invest_min out of constants since could be changing more frequently # maybe refactor coins_to_analyze to num_coins_to_analyze (but then have to worry about it being top num coins etc easier like this coins_to_analyze implicitly implies top x coins by market cap) # 'end_day_open_positions_binance_btc_24h_vol' # base_pair is for trading (balance, max_value, usdt_invest, usdt_invest_min, start_balance, back_testing), roi is in btc, keep track of both prices (usdt, btc) for roi calculation and optics
            'balance': {'usdt': 5000}, # 'btc': 1.0 # {'btc': 1.0, 'max': {'btc': 1.0}}
            'max_value': {'usdt': 5700}, # 1.07 is btc balance in Binance on 9/14/2020
            'open': pd.DataFrame(columns=['symbol', 'position', 'buy_date', 'buy_price', 'buy_price(btc)', 'balance', 'current_date', 'current_price(btc)', 'current_roi(btc)', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).astype({'symbol': 'object', 'position': 'object', 'buy_date': 'datetime64[ns]', 'buy_price': 'float64', 'buy_price(btc)': 'float64', 'balance': 'float64', 'current_date': 'datetime64[ns]', 'current_price(btc)': 'float64', 'current_roi(btc)': 'float64', 'kucoin_usdt_24h_vol': 'float64', 'gtrends_15d': 'float64', 'rank_rise_d': 'float64', 'tsl_armed': 'bool', 'tsl_max_price(btc)': 'float64', 'trade_notes': 'object', 'other_notes': 'object'}), # 'binance_btc_24h_vol(btc)'
            'sold': pd.DataFrame(columns=['coin', 'symbol', 'position', 'buy_date', 'buy_price', 'buy_price(btc)', 'balance', 'sell_date', 'sell_price', 'sell_price(btc)', 'roi(btc)', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_max_price(btc)', 'trade_notes', 'other_notes']).astype({'coin': 'object', 'symbol': 'object', 'position': 'object', 'buy_date': 'datetime64[ns]', 'buy_price': 'float64', 'buy_price(btc)': 'float64', 'balance': 'float64', 'sell_date': 'datetime64[ns]', 'sell_price': 'float64', 'sell_price(btc)': 'float64', 'roi(btc)': 'float64', 'kucoin_usdt_24h_vol': 'float64', 'gtrends_15d': 'float64', 'rank_rise_d': 'float64', 'tsl_max_price(btc)': 'float64', 'trade_notes': 'object', 'other_notes': 'object'}) # 'binance_btc_24h_vol(btc)'
        }
    return portfolio
