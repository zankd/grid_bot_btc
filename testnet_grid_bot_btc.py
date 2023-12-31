import ccxt
import time
import csv
from datetime import datetime
import config
from decimal import Decimal, ROUND_DOWN

# Binance testnet
exchange = ccxt.binance({
    'apiKey': config.TAPI_KEY,
    'secret': config.TAPI_SECRET,
})
exchange.set_sandbox_mode(True)

# Define strategy parameters
symbol = 'BTC/USDT'
max_open_orders = 4
fixed_grid_size = 20  # USD
quantity = 0.0030

# Retrieve the initial BTC/USDT price
ticker = exchange.fetch_ticker(symbol)
initial_price = ticker['last']

# Initialize grid_size as a global variable
grid_size = fixed_grid_size

# Define grid_count
grid_count = 4

def print_red(message):
    print("\033[31m" + message + "\033[0m")

def calculate_grid_size(current_price, order_quantity):
    # Calculate grid_size based on the adjusted order quantity
    adjusted_quantity = order_quantity * (1 + fixed_grid_size / current_price)
    return adjusted_quantity * current_price / (1 + fixed_grid_size / current_price)

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

def cancel_all_orders():
    try:
        # Fetch all open orders
        open_orders = exchange.fetch_open_orders(symbol)

        # Cancel each open order
        for order in open_orders:
            order_id = order['id']
            exchange.cancel_order(order_id, symbol)
            print(f"Canceled order: {order_id}")

    except Exception as e:
        print(f"Error canceling orders: {e}")

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

def place_initial_orders(initial_price):
    print("Placing initial orders...")

    # Cancel all existing orders
    cancel_all_orders()

    # Place 2 initial buy orders
    buy_price_1 = round(initial_price - grid_size, 2)
    buy_price_2 = round(initial_price - 2 * grid_size, 2)

    place_order('BUY', buy_price_1, quantity)
    place_order('BUY', buy_price_2, quantity)

    # Place 2 initial sell orders
    sell_price_1 = round(initial_price + grid_size, 2)
    sell_price_2 = round(initial_price + 2 * grid_size, 2)

    place_order('SELL', sell_price_1, quantity)
    place_order('SELL', sell_price_2, quantity)

def print_initial_info():
    # Print initial information
    ticker = exchange.fetch_ticker(symbol)
    initial_price = ticker['last']

    # Calculate grid prices
    lower_grid_price = round(initial_price - 2 * grid_size, 2) 
    upper_grid_price = round(initial_price + 2 * grid_size, 2)  

    print(f'Calculated Lower Grid Price: {lower_grid_price:.2f} USDT')
    print(f'Calculated Upper Grid Price: {upper_grid_price:.2f} USDT')

    print(f'Initial Position of Each Grid:')
    for i in range(-grid_count // 2, grid_count // 2 + 1):
        price = round(initial_price + i * grid_size, 2)
        print(f'Grid at {price:.2f} USDT')

# Initialize last_buy_grid and last_sell_grid before using them
last_buy_grid = 0
last_sell_grid = 0

# Initialize a variable to control the loop
running = True

def execute_adjustable_grid(initial_price):
    global last_buy_grid, last_sell_grid, grid_size, running, quantity

    try:
        # Print initial information
        print_initial_info()

        # Place initial orders
        print("Placing initial orders...")
        place_initial_orders(initial_price)

        while running:
            # Print BTC price every 5 minutes in red
            ticker = exchange.fetch_ticker(symbol)
            last_price = ticker['last']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print_red(f'BTC/USDT Price: {last_price}')

            # Fetch existing buy and sell orders
            existing_buy_orders = [order for order in exchange.fetch_open_orders(symbol) if order['side'] == 'buy']
            existing_sell_orders = [order for order in exchange.fetch_open_orders(symbol) if order['side'] == 'sell']

            # Place buy orders only when the price crosses a new upper grid line
            current_grid = round((last_price - initial_price) / grid_size)
            if current_grid > last_buy_grid and current_grid != 0:
                # Use the current upper grid line price
                price = round(initial_price + current_grid * grid_size, 2)

                # Check if there is no existing buy order at the same price
                if not any(order['price'] == price for order in existing_buy_orders):
                    place_order('BUY', price, quantity)
                    log_trade(timestamp, 'BUY', price, quantity)

                last_buy_grid = current_grid

            # Place sell orders only when the price crosses a new upper grid line
            elif current_grid < last_sell_grid and current_grid != 0:
                # Use the current upper grid line price
                price = round(initial_price + current_grid * grid_size, 2)

                # Check if there is no existing sell order at the same price
                if not any(order['price'] == price for order in existing_sell_orders):
                    place_order('SELL', price, quantity)
                    log_trade(timestamp, 'SELL', price, quantity)

                last_sell_grid = current_grid

            # Check if existing sell orders have been filled
            for sell_order in existing_sell_orders:
                if sell_order not in exchange.fetch_open_orders(symbol):
                    # Sell order is no longer in the list of open orders, log the trade and place a new sell order
                    price = sell_order['price']
                    quantity = sell_order['quantity']
                    log_trade(timestamp, 'SELL', price, quantity)

                    # Place a new sell order at the next upper grid line
                    if len(existing_sell_orders) < max_open_orders:
                        new_price = round(price + grid_size, 2)
                        if not any(order['price'] == new_price for order in existing_sell_orders):
                            # Use the original quantity for sell orders
                            place_order('SELL', new_price, quantity)
                            log_trade(timestamp, 'SELL', new_price, quantity)

                            # Print the new grid line
                            print(f'New Grid Line: {new_price:.2f} USDT')

            time.sleep(60)

    except Exception as e:
        print(f"Error in execution: {e}")

def log_trade(timestamp, side, price, quantity):
    try:
        # Fetch the latest ticker information
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # Calculate profit
        if side == 'BUY':
            profit = current_price - price
        else:
            profit = price - current_price

        # Log the trade information along with profit
        with open('gridinf_trades.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            # Add titles to the CSV file if it's empty
            if file.tell() == 0:
                writer.writerow(['Timestamp', 'Side', 'Price', 'Quantity', 'Profit'])
            writer.writerow([timestamp, side, price, quantity, profit])
            
            # Print the profit for each trade
            print(f"Trade logged - Timestamp: {timestamp}, Side: {side}, Price: {price}, Quantity: {quantity}, Profit: {profit}")

    except Exception as e:
        print(f"Error logging trade: {e}")

# Print available funds
print_available_funds()

# Execute the strategy with the initial price
execute_adjustable_grid(initial_price)
