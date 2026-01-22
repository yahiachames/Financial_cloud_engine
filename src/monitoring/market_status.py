import requests

def check_market_status():
    """
    Fetches the current US Market Status from Finnhub API.
    
    Returns:
        dict: JSON response containing market status.
    """
    try:
        url = "https://finnhub.io/api/v1/stock/market-status?exchange=US&token=d4k9h09r01qvpdoiqjdgd4k9h09r01qvpdoiqje0"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        market_status = response.json()
        print(market_status)
        return market_status
    except Exception as e:
        print(f"Error fetching market status: {e}")
        return None

if __name__ == "__main__":
    check_market_status()