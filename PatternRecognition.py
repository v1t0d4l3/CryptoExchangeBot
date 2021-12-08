from Utils.CryptoCom import CryptoCom
import talib
import numpy as np
import pandas
import os
import datetime
from dotenv import load_dotenv
from Utils.Telegram import Telegram
import mysql.connector as Database
load_dotenv()

crypto = CryptoCom(os.getenv("API_KEY"),os.getenv("SECRET_KEY"),os.getenv("BASE_URL"),os.getenv("NONCE_FIX"))
telegram = Telegram(os.getenv("TELEGRAM_RECEIVER_ID"),os.getenv("TELEGRAM_BOT_TOKEN"))



def openMysqlConnection():
    dbConnect = Database.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_SCHEMA")
    )
    return dbConnect

def executeDbReadQuery(query):
    mydb = openMysqlConnection()
    cursor = mydb.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    mydb.close()
    return result

def executeDbWriteQuery(query):
    try:
        mydb = openMysqlConnection()
        cursor = mydb.cursor()
        cursor.execute(query)
        cursor.close()
        mydb.commit()
        mydb.close()
    except Exception as e:
        print(e)


################
### STRATEGY ###
################
instruments = crypto.getInstruments()['result']['instruments']

# Instruments Count for my stable coin
instrumentsCount=0
for instr in instruments:
    if instr['quote_currency'] in os.getenv("AVAILABLE_STABLE_COIN") and instr['instrument_name'] not in os.getenv("BLOCKED_INSTRUMENTS"): # Abilito solo determinate stable coin ed escludo a priori alcuni strumenti
        instrumentsCount = instrumentsCount+1

baseCurrencyCapital = 2000
for instr in instruments: #Instruments iteration
    # Filter on stable coin
    if instr['quote_currency'] in os.getenv("AVAILABLE_STABLE_COIN") and instr['instrument_name'] not in os.getenv("BLOCKED_INSTRUMENTS"): # Abilito solo determinate stable coin ed escludo a priori alcuni strumenti
        
        instrument_name = instr['instrument_name']
        quote_currency = instr['quote_currency']
        base_currency = instr['base_currency']
        price_decimals = instr['price_decimals']
        quantity_decimals = instr['quantity_decimals']

        #if instrument_name != "BTC_USDT" and instrument_name != "ETH_USDT":
        #    continue

        #Check budget for the transaction
        #baseCurrencyCapital = crypto.getAccountSummary(quote_currency)['result']['accounts'][0]['available']
        openOrders = executeDbReadQuery("SELECT count(1) FROM "+os.getenv("TABLE_NAME")+" WHERE instrument LIKE '%_"+str(quote_currency)+"' AND sell_date IS NULL")[0][0]
        budget = baseCurrencyCapital/(instrumentsCount-openOrders)

        # Check if already bought pair
        order = executeDbReadQuery("SELECT * FROM "+os.getenv("TABLE_NAME")+" WHERE instrument='"+str(instrument_name)+"' AND sell_date IS NULL LIMIT 1")

        if order != []:
            position = "BUY"
            order_id = order[0][0]
            buy_date = order[0][2]
            buy_price = order[0][4]
        else:
            position = "SELL"


        midTimeframe = crypto.getCandlestick(instrument_name,os.getenv("LONG_TIMEFRAME"))
        df = pandas.DataFrame(midTimeframe['result']['data'])
        liqLenght = 50
        df["bbupper"], df["bbmiddle"], df["bblower"] = talib.BBANDS(df.c, timeperiod=50,nbdevup=1.25,nbdevdn=1.25,matype=0)
        j=liqLenght
        while j > 9:
            df["SMA"+str(j)] = talib.SMA(df["c"],timeperiod=j)
            j = j-1

        df.dropna(inplace = True)
        df.head()

        if os.getenv("DRY_RUN") == "True":
            from random import randint
            buyPrice = 0
            
            for i in range(len(df)):
                if i<30:
                    continue

                date = df.values[i][0]/1000
                open = df.values[i][1]
                high = df.values[i][2]
                low = df.values[i][3]
                close = df.values[i][4]
                volume = df.values[i][5]

                bbupper = df.values[i][6]
                bbmiddle = df.values[i][7]
                bblower = df.values[i][8]
                
                rocCalc = close - df.values[i-30][4]

                buy=False
                sell=False
                if position == "SELL" and rocCalc>0 and close >= bbupper:
                    liqDays = liqLenght
                    buy=True
                    

                if position=="BUY":
                    liqDays = liqDays-1
                    if(liqDays>9):
                        takeProfitLevel=df.values[i][df.columns.get_loc("SMA"+str(liqDays))]
                    else:
                        takeProfitLevel=df.values[i][df.columns.get_loc("SMA10")]
                    if takeProfitLevel>bbupper:
                        sell=True

                if position == "SELL":
                    if buy==True:
                        position="BUY"
                        buyPrice=close
                        orderDate = datetime.datetime.fromtimestamp(int(date))
                        print("COMPRO "+instrument_name+" IL "+str(orderDate)+" AL PREZZO DI "+str(close))
                        baseCurrencyCapital = baseCurrencyCapital-budget
                        orderId = randint(1000000000,9999999999)
                        executeDbWriteQuery("INSERT INTO "+os.getenv("TABLE_NAME")+" (order_id,instrument,buy_date,buy_price) VALUES ('"+str(orderId)+"','"+str(instrument_name)+"','"+str(orderDate)+"',"+str(buyPrice)+")")




                if position == "BUY":
                    if sell == True: #and buyPrice<close:
                        position="SELL"
                        liqDays = liqLenght
                        gain = (((close-buyPrice)/buyPrice))
                        baseCurrencyCapital = baseCurrencyCapital+(budget*gain)+budget
                        buyPrice=0
                        orderDate = datetime.datetime.fromtimestamp(int(date))
                        print("VENDO "+instrument_name+" IL "+str(orderDate)+" AL PREZZO DI "+str(close))
                        print("---> Gain: "+str(round(gain*100,2))+"%")
                        executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET sell_date='"+str(orderDate)+"', sell_price="+str(close)+", current_price="+str(close)+" WHERE order_id='"+str(orderId)+"'")
                    else:
                        executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET current_price="+str(close)+" WHERE order_id='"+str(orderId)+"'")

            if position == "BUY":
                executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET current_price="+str(close)+" WHERE order_id='"+str(orderId)+"'")

print("FINALE: "+str(baseCurrencyCapital))