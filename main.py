import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from binance.client import Client
import time

# Replace with your actual bot token and Binance API keys
TELEGRAM_BOT_TOKEN = '7735488510:AAGwP9wah6sPjjRN52SdLjS_YqTncvnn3Sw'
BINANCE_API_KEY = 'wDQiuxDfgbu5sHNgszLHSQ6dTtrIE0OALZvK5derXgckFWUPwzF4CFlrr42sIH1M'
BINANCE_API_SECRET = 'HjTFbSOjjwAB6cL7uId0ltguIF40beDXcFQqd6XPNc6b6heSlOsUn9WoyFRRbo1L'

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
binance_client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# Global variables to store user data
user_data = {}

# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    balance_button = InlineKeyboardButton("Balance", callback_data="balance")
    trade_button = InlineKeyboardButton("Trade", callback_data="trade")
    markup.add(balance_button, trade_button)
    bot.send_message(message.chat.id, "Welcome! Choose an option:", reply_markup=markup)

# Handle callback queries for menu options
@bot.callback_query_handler(func=lambda call: True)
def menu_handler(call):
    if call.data == "balance":
        show_balance(call)
    elif call.data == "trade":
        show_trade_menu(call)
    elif call.data.startswith("trade_"):
        handle_token_trade(call)
    elif call.data == "back":
        send_welcome(call.message)

# Show Binance balance
def show_balance(call):
    try:
        account_info = binance_client.get_account()
        balances = account_info['balances']
        balance_message = "Your balances:\n"
        for balance in balances:
            if float(balance['free']) > 0:  # Show only non-zero balances
                balance_message += f"{balance['asset']}: {balance['free']}\n"
                markup = InlineKeyboardMarkup()
        back_button = InlineKeyboardButton("Back", callback_data="back")
        markup.add(back_button)
        
        bot.send_message(call.message.chat.id, balance_message, reply_markup=markup)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error fetching balance: {str(e)}")
   

# Show trade menu
def show_trade_menu(call):
    markup = InlineKeyboardMarkup()
    tokens = ["BTC", "ETH", "BNB", "DOGE", "SOL"]
    for token in tokens:
        markup.add(InlineKeyboardButton(token, callback_data=f"trade_{token}"))
    back_button = InlineKeyboardButton("Back", callback_data="back")
    markup.add(back_button)
    bot.send_message(call.message.chat.id, "Select a token to trade:", reply_markup=markup)

# Handle token trade
def handle_token_trade(call):
    token = call.data.split("_")[1]
    user_data[call.message.chat.id] = {"token": token}
    bot.send_message(call.message.chat.id, f"How much USD do you want to spend on {token}? (e.g., 50)")

@bot.message_handler(func=lambda message: message.chat.id in user_data and "token" in user_data[message.chat.id])
def handle_amount_input(message):
    try:
        usd_amount = float(message.text)
        if usd_amount <= 0:
            raise ValueError("Amount must be greater than 0.")
        user_data[message.chat.id]["usd_amount"] = usd_amount

        token = user_data[message.chat.id]["token"]
        bot.send_message(message.chat.id, f"Analyzing the market for {token}. Please wait...")

        # Monitor market price for 2 minutes and decide to buy
        monitor_and_trade(message.chat.id, token, usd_amount)
    except ValueError:
        bot.send_message(message.chat.id, "Invalid amount. Please enter a valid number.")

def monitor_and_trade(chat_id, token, usd_amount):
    try:
        symbol = f"{token}USDT"
        initial_price = float(binance_client.get_symbol_ticker(symbol=symbol)["price"])

        # Monitor price for 2 minutes
        start_time = time.time()
        bought = False
        while time.time() - start_time < 120:
            current_price = float(binance_client.get_symbol_ticker(symbol=symbol)["price"])
            if current_price < initial_price:
                # Buy the token
                quantity = usd_amount / current_price
                order = binance_client.create_order(
                    symbol=symbol,
                    side="BUY",
                    type="MARKET",
                    quantity=round(quantity, 6)  # Adjust quantity precision
                )
                bot.send_message(chat_id, f"Successfully bought {round(quantity, 6)} {token} at price {current_price} USD.")
                bought = True
                break
            time.sleep(5)  # Check price every 5 seconds

        if not bought:
            bot.send_message(chat_id, f"Could not buy {token} within 2 minutes as the price didn't drop.")

        # Monitor price for 1 minute to decide to sell
        if bought:
            start_time = time.time()
            while time.time() - start_time < 60:
                current_price = float(binance_client.get_symbol_ticker(symbol=symbol)["price"])
                if current_price > initial_price:
                    # Sell the token
                    order = binance_client.create_order(
                        symbol=symbol,
                        side="SELL",
                        type="MARKET",
                        quantity=round(quantity, 6)
                    )
                    bot.send_message(chat_id, f"Successfully sold {round(quantity, 6)} {token} at price {current_price} USD.")
                    return
                time.sleep(5)

            bot.send_message(chat_id, f"Held {token} as the price didn't increase within 1 minute.")

    except Exception as e:
        bot.send_message(chat_id, f"Error during trading: {str(e)}")

# Start polling
bot.polling()
