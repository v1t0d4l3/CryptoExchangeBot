# Simple [Crypto.com](https://platinum.crypto.com/r/32t8qj9mjq "Crypto.com") Exchange Trading Bot

This is an experimental trading bot on the [Crypto.com](https://platinum.crypto.com/r/32t8qj9mjq "Crypto.com") Exchange platform.

It's quite simple to understand. Once you have chosen a stable coin (eg USDT) it scans all the currency pairs (currently around 100), avoiding the ones that are too recent, and analyzes them one by one. If it makes a transaction it sends a message on Telegram.

The amount of each transaction depends on how much money are allocated on the stable coin and how many pairs is analyzing without those already purchased.
For example:

<pre>
USDT Available: 10000 $
Total pairs: 100
Pairs already purchased: 20

10000 / (100 - 20) = 125 $
</pre>

**You'll never sell if you are losing money. But if you prefer you can disable this check in code.**

It makes use of a multi time frame strategy based on EMACross (12,50) and MACD (12,26,9) as indicators.

A multiple time frame analysis is the process of viewing the same currency pair under different time frames. In the released setup I use three different charts:

- 1 day to estabilish a long term bull trend;
- 4 hours to check if price is rising or is having a strong correction;
- 1 hour to find a good entry point.

4 hours chart is used to find the exit point too.

With this approach I hope to avoid false signals.

## Disclaimer
1. This is an **EXPERIMENTAL** project.
2. I'm not responsible for anything done with this bot.
3. You use it at your own risk.
4. I'm not responsible for any money you lose!

## Setup

### Prerequisites
1. A [Crypto.com](https://platinum.crypto.com/r/32t8qj9mjq "Crypto.com") account. Obviously! Click on [this link](https://platinum.crypto.com/r/32t8qj9mjq "Crypto.com") to earn 25$ on subscription. ;-)
2. Python 3.9.x
3. MySQL or MariaDB database
4. A lowcost server to schedule

### Python Packages
1. numpy
2. pandas
3. TA-Lib
4. pytz
5. python-dotenv
6. mysql-connector

### Installation Step

1. Create a Telegram Bot and get Token ([instructions here](https://www.siteguarding.com/en/how-to-get-telegram-bot-api-token))
2. Retrieve your Telegram chat ID ([instructions here](https://www.alphr.com/find-chat-id-telegram/))
3. Get you [Crypto.com](https://platinum.crypto.com/r/32t8qj9mjq "Crypto.com") API KEY and API SECRET
4. Install database importing "tableDump.sql" file and save your connection data
5. Rename .env.dist file to .env and put all previous information here

<pre>
#Telegram Bot Params
TELEGRAM_RECEIVER_ID = ''                       <--- Your Telegram Chat ID
TELEGRAM_BOT_TOKEN = ''                         <--- Your Telegram Bot Token

#Crypto.com Exchange API Data
BASE_URL = "https://api.crypto.com/v2/"
API_KEY = ""                                    <--- Your Crypto.com API KEY
SECRET_KEY = ""                                 <--- Your Crypto.com API SECRET
NONCE_FIX = 3600

#MySQL Database Table Data
DB_HOST = "localhost"                           <---
DB_USER = "root"                                <---
DB_PASS = "password"                            <---
DB_SCHEMA = "exchange"                          
TABLE_NAME = "crypto_orders"
</pre>

6. Make a test executing
<pre>python3 run.py</pre>
7. If everything is ok you can schedule the script. In my case every 5 minutes.
<pre>
crontab -e

*/5 * * * * python3 /your/path/CryptoExchangeBot/run.py > /your/log/path/crypto-report.log
</pre>

8. Wait for Telegram messages and don't leave Bot alone! ;-)