# speterlin-crypto

A Python package for a suite of quant-trading opportunities in crypto with API integration: Kucoin Exchange & Binance Exchange for storing crypto assets (cold storage) and spot and derivatives trading (hot storage), Coin Market Cap (CMC) & CoinGecko (CG) & Google Trends for data collection.

Please see [quant-trading](https://github.com/speterlin/quant-trading) for writing scripts, backtesting, other analysis. Make sure to install package like this (with python>=3.12 and latest pip) in your environment or (recommended) virtual environment:
```python
pip install speterlin-crypto
```
And then import package like this:
```python
import speterlin_crypto.module1 as crypto
```

For the following calls set up your Python virtual environment shell (where you quant trade or analyze crypto) and import packages like in [quant-trading#Python script for Crypto](https://github.com/speterlin/quant-trading?tab=readme-ov-file#python-script-for-crypto-programscryptocrypto_kucoin_your_username)

## Get and analyze your saved Portfolio

```python
portfolio = crypto.get_saved_portfolio_backup("portfolio_usdt_rr_10_-10_20_-0.3_0.5_-0.2_1000_100_1000_1000_True_False_False_{'usdt': 10000}_2023-03-12_to_" + datetime.now().strftime('%Y-%m-%d'))

# View open positions in two rows
print(str(portfolio['open'].drop(['position', 'kucoin_usdt_24h_vol', 'gtrends_15d', 'rank_rise_d', 'tsl_armed', 'tsl_max_price(btc)', 'trade_notes', 'other_notes'], axis=1)) + "\n" + str(portfolio['open'].drop(['symbol',
'buy_date', 'buy_price', 'buy_price(btc)', 'balance', 'current_date', 'current_price(btc)', 'current_roi(btc)'], axis=1)))

# View sold positions
portfolio['sold'].tail(40).drop(['symbol', 'buy_price(btc)', 'sell_price(btc)', 'kucoin_usdt_24h_vol', 'rank_rise_d', 'tsl_max_price(btc)', 'gtrends_15d', 'other_notes'], axis=1)
```

## Check Assets

```python
assets = crypto.get_kucoin_assets()
print(str(assets) + "\nTotal Current Value: " + str(assets['current_value'].sum()) + "\nTotal Current Value (BTC): " + str(assets['current_value(btc)'].sum()))`
```

## Market calls

```python
coin, symbol_pair = 'hyperliquid', 'HYPE-USDT'
kucoin_pairs_with_price_and_vol_current = crypto._fetch_data(crypto.get_kucoin_pairs, params={}, error_str=" - Kucoin get tickers error on: " + str(datetime.now()), empty_data={})
price, btc_price = kucoin_pairs_with_price_and_vol_current[symbol_pair]['price'] if symbol_pair in kucoin_pairs_with_price_and_vol_current else float("NaN"), kucoin_pairs_with_price_and_vol_current['BTC-USDT']['price']
price_in_btc = price / btc_price
```

## Get and save todays CMC data

Single coin detailed data:
```python
coin_id = 'hyperliquid'
coin_data = crypto._fetch_data(crypto.get_coin_data, params={'coin': coin_id}, error_str=" - No " + "" + " coin data for: " + coin_id + " on: " + str(datetime.now()), empty_data={})
```

All (or limited - in this case 10 pages ~1000 coins) CMC coins (takes roughly 20-30 minutes to save):
```python
# with detailed data for each coin - recommended (calls below function and then above function on each coin)
todays_date = datetime.now()
crypto.save_coins_data(date=todays_date.strftime('%Y-%m-%d'))

# with basic data for each coin
pages=10
coins = crypto._fetch_data(crypto.get_coins_markets_coinmarketcap, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={})
```

## Retrieve past saved CMC data

```python
df_coins_2025_11_17 = crypto.get_saved_coins_data(date='2025-11-17')
# View the 17 saved data points on hyperliquid
df_coins_2025_11_17.loc['hyperliquid']
```

## Get todays other (CoinGecko & Google Trends) data

```python
# Standard library imports
import re

# Third Party imports
import pandas as pd

coin, stop_day = 'hyperliquid', datetime.now()

#CoinGecko
pages=10
coins = crypto._fetch_data(crypto.get_coins_markets_coingecko, params={'pages': pages}, error_str=" - No " + "" + " coins markets data with pages: " + str(pages) + " on: " + str(datetime.now()), empty_data={})

# #get_coin_data_coingecko CoinGecko returns 403 forbidden error even with headers, need to purchase API plan

# 15 days Google Trends of a Ticker
coin_search_term = coin if not re.search('-', coin) else coin.split("-")[0]
google_trends = crypto._fetch_data(crypto.get_google_trends_pt, params={'kw_list': [coin_search_term], 'from_date': stop_day - timedelta(days=15), 'to_date': stop_day}, error_str=" - No " + "google trends" + " data for coin search term: " + coin_search_term +
 " from: " + str(stop_day - timedelta(days=15)) + " to: " + str(stop_day), empty_data=pd.DataFrame())
google_trends_slope = crypto.trendline(google_trends.sort_values('date', inplace=False, ascending=True)[coin_search_term]) if not google_trends.empty else float("NaN")
```

## AI Analysis

Yet to implement AI analysis with crypto

## Algorithms

Crypto has more volatility (higher risk, higher spikes in trading volume, higher swings in prices) than stocks, therefore algorithm limits are different than in [speterlin-stocks](https://github.com/speterlin/speterlin-stocks) and you have default parameters such as `'rank_rise_d_buy_limit': 1000` (limit outliers from entering your portfolio - ie prevent likely pump&dump scheme coins that jump more than 1000 ranks over interval days) in `portfolio['constants']` (see `examples/example.py`) and `portfolio_current_roi_restart={'engaged': False, 'limit': 0.15}` (ensure that portfolio has gained >=15% - 2x the value from `speterlin-stocks` - in paper_trading before entering real trading) in `crypto.portfolio_trading()` call.

```python
portfolios = {
  'rr': 'Relative Rank - Buy or sell coins depending if their Market Cap relative rank has moved above or below a threshold over the past interval days (ie buy if Market Cap rank has increased 50 over the past 10 days, sell if in portfolio and Market Cap rank has decreased 50 over the past 10 days)'
}
```

## Send message to your Phone via Twilio

```python
twilio_message = crypto._fetch_data(crypto.twilio_client.messages.create, params={'to': twilio_phone_to, 'from_': twilio_phone_from, 'body': "Q Trading @crypto: running on " + str(datetime.now()) + " :)"}, error_str=" - Twilio msg error to: " + twilio_phone_to + " on: " + str(datetime.now()), empty_data=None)
```
