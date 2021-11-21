from Utils.CryptoCom import CryptoCom
from Utils.Telegram import Telegram
import mysql.connector as Database
import os
import talib
import pytz
import time
import datetime
import pandas
import numpy as np
from dotenv import load_dotenv

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

def applyTechIndicator(df):

    #df.dropna(inplace = True)
    #df.head()

    df["EMA_FAST"] = talib.EMA(df["c"], timeperiod=int(os.getenv("EMA_FAST_TIME")))
    df["EMA_SLOW"] = talib.EMA(df["c"], timeperiod=int(os.getenv("EMA_SLOW_TIME")))
    df["MACD"], df["MACDSignal"],df['MACDHist'] = talib.MACD(df.c, fastperiod=int(os.getenv("MACD_FAST")), slowperiod=int(os.getenv("MACD_SLOW")), signalperiod=int(os.getenv("MACD_SIGNAL")))
    df['MACD_NOT_NAN'] = np.where((df.MACD != None),1,0)
    df['MACD_GT_ZERO'] = np.where((df.MACD > 0),1,0)
    df['MACD_GT_SIGNAL'] = np.where((df.MACD>=df.MACDSignal),1,0)
    df['EMAF_GT_EMAS'] = np.where((df.EMA_FAST >= df.EMA_SLOW),1,0)
    df['EMAF_LT_PRICE'] = np.where(df.EMA_FAST<df.c,1,0)

    df.dropna(inplace = True)
    df.head()

    return df

def isBuy(macdNotNull, macdGtZero,macdGtSignal,fastEmaGtSlowEma,fastEmaLtPrice=None):
    returnVal = False
    if macdNotNull==1 and macdGtZero==1 and macdGtSignal==1 and fastEmaGtSlowEma==1:
        
        returnVal = True

        if fastEmaLtPrice != None and fastEmaLtPrice != 1:
            returnVal = False

    return returnVal

################
### STRATEGY ###
################
instruments = crypto.getInstruments()['result']['instruments']

# Instruments Count for my stable coin
instrumentsCount=0
for instr in instruments:
    if instr['quote_currency'] in os.getenv("AVAILABLE_STABLE_COIN") and instr['instrument_name'] not in os.getenv("BLOCKED_INSTRUMENTS"): # Abilito solo determinate stable coin ed escludo a priori alcuni strumenti
        instrumentsCount = instrumentsCount+1


for instr in instruments: #Instruments iteration

    # Filter on stable coin
    if instr['quote_currency'] in os.getenv("AVAILABLE_STABLE_COIN") and instr['instrument_name'] not in os.getenv("BLOCKED_INSTRUMENTS"): # Abilito solo determinate stable coin ed escludo a priori alcuni strumenti
        
        instrument_name = instr['instrument_name']
        quote_currency = instr['quote_currency']
        base_currency = instr['base_currency']
        price_decimals = instr['price_decimals']
        quantity_decimals = instr['quantity_decimals']

        #Check budget for the transaction
        baseCurrencyCapital = crypto.getAccountSummary(quote_currency)['result']['accounts'][0]['available']
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

        longTimeframe = crypto.getCandlestick(instrument_name,os.getenv("LONG_TIMEFRAME"))

        dfLong = pandas.DataFrame(longTimeframe['result']['data'])
        dfLong = applyTechIndicator(dfLong)
        if not dfLong.empty and len(dfLong) >= int(os.getenv("EMA_SLOW_TIME")): # Check if pair has long history
            # Get some useful data on last candle
            print(instrument_name)
            
            candleTime = dfLong.values[-1][0]
            price = dfLong.values[-1][4]
            macdNotNull = dfLong.values[-1][11]
            macdGtZero = dfLong.values[-1][12]
            macdGtSignal = dfLong.values[-1][13]
            fastEmaGtSlowEma = dfLong.values[-1][14]
            fastEmaLtPrice = dfLong.values[-1][15]

            if position == "SELL":
                print("---> Verify long term trend")
                if isBuy(macdNotNull,macdGtZero,macdGtSignal,fastEmaGtSlowEma):
                    
                    midTimeframe = crypto.getCandlestick(instrument_name,os.getenv("MID_TIMEFRAME"))
                    dfMid = pandas.DataFrame(midTimeframe['result']['data'])
                    dfMid = applyTechIndicator(dfMid)

                    candleTime = dfMid.values[-1][0]
                    price = dfMid.values[-1][4]
                    macdNotNull = dfMid.values[-1][11]
                    macdGtZero = dfMid.values[-1][12]
                    macdGtSignal = dfMid.values[-1][13]
                    fastEmaGtSlowEma = dfMid.values[-1][14]
                    fastEmaLtPrice = dfMid.values[-1][15]
                    print("--->---> Verify mid term trend")
                    if isBuy(macdNotNull,macdGtZero,macdGtSignal,fastEmaGtSlowEma):
                        shortTimeframe = crypto.getCandlestick(instrument_name,os.getenv("SHORT_TIMEFRAME"))
                        dfShort = pandas.DataFrame(shortTimeframe['result']['data'])
                        dfShort = applyTechIndicator(dfShort)

                        candleTime = dfShort.values[-1][0]
                        price = dfShort.values[-1][4]
                        macdNotNull = dfShort.values[-1][11]
                        macdGtZero = dfShort.values[-1][12]
                        macdGtSignal = dfShort.values[-1][13]
                        fastEmaGtSlowEma = dfShort.values[-1][14]
                        fastEmaLtPrice = dfShort.values[-1][15]
                        print("--->---> Verify short term trend")
                        if isBuy(macdNotNull,macdGtZero,macdGtSignal,fastEmaGtSlowEma, fastEmaLtPrice):
                            print("--->--->--->---> BUY")
                            buyQty = round(budget/price,quantity_decimals)
                            orderResult = crypto.createOrder(instrument_name,"BUY","MARKET",None,buyQty)
                            if orderResult['error_code'] == 0:
                                orderId = orderResult['result']['order_id']
                                orderDetail = crypto.getOrderDetail(orderId)
                                avgPrice = orderDetail['result']['order_info']['avg_price']
                                orderDate = datetime.datetime.fromtimestamp(int(candleTime/1000))
                                executeDbWriteQuery("INSERT INTO "+os.getenv("TABLE_NAME")+" (order_id,instrument,buy_date,buy_price) VALUES ('"+str(orderId)+"','"+str(instrument_name)+"','"+str(orderDate)+"',"+str(avgPrice)+")")
                                message = "I bought "+str(instrument_name).replace('_','-')+" at "+str(avgPrice,2)+" dollars."
                                telegram.sendTelegramMessage(message)
                            else:
                                message = "Error while buying "+str(instrument_name).replace('_','-')+": ["+str(orderResult['error_code'])+"] - "+str(orderResult['error_message']).replace('_','-')
                                telegram.sendTelegramMessage(message)
            else:
                print("---> Verify if it's time to sell")
                midTimeframe = crypto.getCandlestick(instrument_name,os.getenv("MID_TIMEFRAME"))
                dfMid = pandas.DataFrame(midTimeframe['result']['data'])
                dfMid = applyTechIndicator(dfMid)

                candleTime = dfMid.values[-1][0]
                price = dfMid.values[-1][4]
                macdNotNull = dfMid.values[-1][11]
                macdGtZero = dfMid.values[-1][12]
                macdGtSignal = dfMid.values[-1][13]
                fastEmaGtSlowEma = dfMid.values[-1][14]
                fastEmaLtPrice = dfMid.values[-1][15]

                #gain = ((price/buy_price)-1)-0.008
                gain = (((price-buy_price)/buy_price))-0.008
                print("---> Current Gain: "+str(round(gain*100,2))+"%")

                if fastEmaGtSlowEma == 0 and price > buy_price and gain >= 0.01: # Never sell if you are losing money. Sell only if gain is over 1%
                    print("--->---> SELL")
                    sellQty = crypto.getAccountSummary(base_currency)['result']['accounts'][0]['available']
                    quantity = round(sellQty,quantity_decimals)
                    charLen = len(str(quantity))
                    qtyFromStr = float(str(sellQty)[0:charLen])
                    if(quantity>qtyFromStr):
                        quantity=qtyFromStr
                    
                    sellQty = quantity

                    orderResult = crypto.createOrder(instrument_name,"SELL","MARKET",None,sellQty)
                    if orderResult['error_code'] == 0:
                        orderId = orderResult['result']['order_id']
                        orderDetail = crypto.getOrderDetail(orderId)
                        avgPrice = orderDetail['result']['order_info']['avg_price']
                        orderDate = datetime.datetime.fromtimestamp(int(candleTime/1000))
                        executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET sell_date='"+str(orderDate)+"', sell_price="+str(avgPrice)+", current_price="+str(avgPrice)+" WHERE order_id='"+order_id+"'")
                        message = "I sold "+str(instrument_name).replace('_','-')+" at "+str(avgPrice,2)+" dollars."
                        telegram.sendTelegramMessage(message)
                    else:
                        message = "Error while selling "+str(instrument_name).replace('_','-')+": ["+str(orderResult['error_code'])+"] - "+str(orderResult['error_message']).replace('_','-')
                        telegram.sendTelegramMessage(message)
                else:
                    print("---> Update current price...")
                    executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET current_price="+str(price)+" WHERE order_id='"+order_id+"'")