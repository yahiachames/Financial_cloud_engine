import requests

url = "https://finnhub.io/api/v1/stock/market-status?exchange=US&token=d4k9h09r01qvpdoiqjdgd4k9h09r01qvpdoiqje0"
response = requests.get(url)
market_status = response.json()
print(market_status)