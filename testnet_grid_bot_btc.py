import ccxt
import time
import csv
from datetime import datetime
from binance.client import Client
import config
from decimal import Decimal, ROUND_DOWN

# Instantiate the exchange for the Binance testnet
exchange = ccxt.binance({
    'apiKey': config.TAPI_KEY,
    'secret': config.TAPI_SECRET,
})
exchange.set_sandbox_mode(True)
client = Client(config.TAPI_KEY, config.TAPI_SECRET)

# Define strategy parameters
symbol = 'BTC/USDT'
max_open_orders = 4 
profit_percent = 0.01  # 1% profit per trade

# Define the number of grid lines
grid_count = 4

# Set grid_size to 40 USD
grid_size = 40

def print_red(message):
    print("\033[31m" + message + "\033[0m")

def print_available_funds():
    try:
        balances = exchange.fetch_balance()
        btc_balance = balances['total']['BTC']
        usdt_balance = balances['total']['USDT']

        print(f'Available Funds:')
        print(f'BTC: {btc_balance:.8f}')
        print(f'USDT: {usdt_balance:.8f}')

    except Exception as e:
        print(f"Error fetching account balances: {e}")

def print_initial_info():
    # Print initial information
    ticker = exchange.fetch_ticker(symbol)
    initial_price = ticker['last']

    # Calculate grid prices
    lower_grid_price = round(initial_price - grid_size * (grid_count // 2), 2)
    upper_grid_price = round(initial_price + grid_size * (grid_count // 2), 2)

    print(f'Calculated Lower Grid Price: {lower_grid_price} USDT')
    print(f'Calculated Upper Grid Price: {upper_grid_price} USDT')

    print(f'Initial Position of Each Grid:')
    for i in range(-grid_count // 2, grid_count // 2 + 1):
        price = round(initial_price + i * grid_size, 2)
        print(f'Grid at {price:.2f} USDT')

def place_initial_orders(initial_price):
    print("Placing initial orders...")

    # Place 2 initial buy orders
    buy_price_1 = round(initial_price - grid_size, 2)
    buy_price_2 = round(initial_price - 2 * grid_size, 2)
    quantity = (grid_size / initial_price) * (1 + profit_percent)

    place_order('BUY', buy_price_1, quantity)
    place_order('BUY', buy_price_2, quantity)

    # Place 2 initial sell orders
    sell_price_1 = round(initial_price + grid_size, 2)
    sell_price_2 = round(initial_price + 2 * grid_size, 2)

    place_order('SELL', sell_price_1, quantity)
    place_order('SELL', sell_price_2, quantity)

def execute_adjustable_grid(initial_price):
    try:
        # Print initial information
        print_initial_info()

        # Place initial orders
        print("Placing initial orders...")
        place_initial_orders(initial_price)

        while True:
            # Print BTC price every 5 minutes in red
            ticker = exchange.fetch_ticker(symbol)
            last_price = ticker['last']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print_red(f'BTC/USDT Price: {last_price}')

            # Place buy orders
            existing_buy_orders = [order for order in exchange.fetch_open_orders(symbol) if order['side'] == 'buy']
            if len(existing_buy_orders) < grid_count:
                quantity = (grid_size / last_price) * (1 + profit_percent)
                for i in range(-grid_count // 2, grid_count // 2 + 1):
                    price = round(initial_price + i * grid_size, 2)

                    # Check if there is no existing buy order at the same price
                    if not any(order['price'] == price for order in existing_buy_orders):
                        place_order('BUY', price, quantity)
                        log_trade(timestamp, 'BUY', price, quantity)

            # Place sell orders
            existing_sell_orders = [order for order in exchange.fetch_open_orders(symbol) if order['side'] == 'sell']
            if len(existing_sell_orders) < grid_count:
                quantity = (grid_size / last_price) * (1 + profit_percent)
                for i in range(-grid_count // 2, grid_count // 2 + 1):
                    price = round(initial_price + i * grid_size, 2)

                    # Check if there is no existing sell order at the same price
                    if not any(order['price'] == price for order in existing_sell_orders):
                        place_order('SELL', price, quantity)
                        log_trade(timestamp, 'SELL', price, quantity)

            time.sleep(60)

    except Exception as e:
        print(f"Error in execution: {e}")

def log_order_response(order_response):
    info = order_response.get('info', {})
    symbol = info.get('symbol', '')
    order_id = info.get('orderId', '')
    client_order_id = info.get('clientOrderId', '')
    price = info.get('price', '')
    orig_qty = info.get('origQty', '')
    executed_qty = info.get('executedQty', '')
    status = info.get('status', '')
    side = info.get('side', '')

    order_log = (
        f"Order response - Symbol: {symbol}, Order ID: {order_id}, "
        f"Client Order ID: {client_order_id}, Price: {price}, "
        f"Original Quantity: {orig_qty}, Executed Quantity: {executed_qty}, "
        f"Status: {status}, Side: {side}"
    )

    print(order_log)

def place_order(side, price, quantity):
    try:
        # Precision for BTC/USDT is 5 decimal 
        quantity_precision = 5
        quantity = Decimal(str(quantity)).quantize(Decimal('1E-' + str(quantity_precision)), rounding=ROUND_DOWN)

        order = exchange.create_limit_buy_order(symbol, quantity, price) if side == 'BUY' else \
                exchange.create_limit_sell_order(symbol, quantity, price)

        # Log the order response
        log_order_response(order)

        return order
    except ccxt.NetworkError as e:
        print(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        print(f"Exchange error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    return None


def log_trade(timestamp, side, price, quantity):
    with open('gridinf_trades.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        # Add titles to the CSV file if it's empty
        if file.tell() == 0:
            writer.writerow(['Timestamp', 'Side', 'Price', 'Quantity'])
        writer.writerow([timestamp, side, price, quantity])
        print(f"Trade logged - Timestamp: {timestamp}, Side: {side}, Price: {price}, Quantity: {quantity}")

# Retrieve the initial BTC/USDT price
ticker = exchange.fetch_ticker(symbol)
initial_price = ticker['last']

# Print available funds
print_available_funds()

# Execute the strategy with the initial price
execute_adjustable_grid(initial_price)
