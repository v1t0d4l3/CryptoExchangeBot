from Utils.CryptoCom import CryptoCom
from Utils.Telegram import Telegram
import mysql.connector as Database
import os
import talib
import datetime
import pandas
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

    liqLenght = int(os.getenv("BOLLINGER_SMA"))
    df["bbupper"], df["bbmiddle"], df["bblower"] = talib.BBANDS(df.c, timeperiod=int(os.getenv("BOLLINGER_SMA")),nbdevup=float(os.getenv("BOLLINGER_STD")),nbdevdn=float(os.getenv("BOLLINGER_STD")),matype=0)
    j=liqLenght
    while j >= int(os.getenv("MIN_SMA_SL")):
        df["SMA"+str(j)] = talib.SMA(df["c"],timeperiod=j)
        j = j-1
    df.dropna(inplace = True)
    df.head()

    return df

def bollingerBanditStrategy(df):
    df = applyTechIndicator(df)
    position = "SELL"
    buy=False
    sell=False
    for i in range(len(df)):
        if i<int(os.getenv("BACK_DAYS")):
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
        
        rocCalc = close - df.values[i-int(os.getenv("BACK_DAYS"))][4]

        buy=False
        sell=False
        if position == "SELL" and rocCalc>0 and close >= bbupper:
            liqDays = int(os.getenv("BOLLINGER_SMA"))
            buy=True
                    
        if position=="BUY":
            liqDays = liqDays-1
            if(liqDays>=int(os.getenv("MIN_SMA_SL"))):
                takeProfitLevel=df.values[i][df.columns.get_loc("SMA"+str(liqDays))]
            else:
                takeProfitLevel=df.values[i][df.columns.get_loc("SMA"+str(os.getenv("MIN_SMA_SL")))]
            if takeProfitLevel>bbupper:
                sell=True
    
    if buy:
        return "BUY"
    if sell:
        return "SELL"
    return False

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

        print(instrument_name)

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

        timeframe = crypto.getCandlestick(instrument_name,os.getenv("TIMEFRAME"))

        df = pandas.DataFrame(timeframe['result']['data'])
        action = bollingerBanditStrategy(df)
        
        if action:
            candleTime = df.values[-1][0]
            price = df.values[-1][4]
            if position == "BUY":
                if action == "SELL":
                    print("---> SELL")
                    sellQty = crypto.getAccountSummary(base_currency)['result']['accounts'][0]['available']
                    quantity = round(sellQty,quantity_decimals)
                    if(quantity_decimals==0):
                        quantity = int(quantity)
                    charLen = len(str(quantity))
                    qtyFromStr = float(str(sellQty)[0:charLen])
                    if(quantity>qtyFromStr):
                        quantity=qtyFromStr
                    sellQty = quantity
                    if(quantity_decimals==0):
                        sellQty = int(sellQty)
                    print("--->---> Quantity: "+str(sellQty))

                    orderResult = crypto.createOrder(instrument_name,"SELL","MARKET",None,sellQty)
                    if orderResult['error_code'] == 0:
                        orderId = orderResult['result']['order_id']
                        orderDetail = crypto.getOrderDetail(orderId)
                        avgPrice = orderDetail['result']['order_info']['avg_price']
                        print("--->---> Price: "+str(avgPrice))
                        orderDate = datetime.datetime.fromtimestamp(int(candleTime/1000))
                        executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET sell_date='"+str(orderDate)+"', sell_price="+str(avgPrice)+", current_price="+str(avgPrice)+" WHERE order_id='"+order_id+"'")
                        message = "I sold "+str(instrument_name).replace('_','-')+" at "+str(avgPrice)+" dollars."
                        print(telegram.sendTelegramMessage(message).content)
                    else:
                        message = "Error while selling "+str(instrument_name).replace('_','-')+": ["+str(orderResult['error_code'])+"] - "+str(orderResult['error_message']).replace('_','-')
                        print(telegram.sendTelegramMessage(message).content)
                        message = "sellQty: "+str(sellQty)+" - quantityRound: "+str(quantity)+" - qtyFromStr: "+str(qtyFromStr)+" - decimals: "+str(quantity_decimals)
                        print(telegram.sendTelegramMessage(message).content)
                else:
                    print("---> position: "+position+" | action: "+str(action))
                    print("---> Update Price")
                    executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET current_price="+str(price)+" WHERE order_id='"+order_id+"'")
            
            if position == "SELL":
                if action == "BUY":
                    print("---> BUY")
                    buyQty = round(budget/price,quantity_decimals)
                    if quantity_decimals==0:
                        buyQty = int(buyQty)
                    orderResult = crypto.createOrder(instrument_name,"BUY","MARKET",None,buyQty)
                    if orderResult['error_code'] == 0:
                        orderId = orderResult['result']['order_id']
                        orderDetail = crypto.getOrderDetail(orderId)
                        avgPrice = orderDetail['result']['order_info']['avg_price']
                        orderDate = datetime.datetime.fromtimestamp(int(candleTime/1000))
                        executeDbWriteQuery("INSERT INTO "+os.getenv("TABLE_NAME")+" (order_id,instrument,buy_date,buy_price) VALUES ('"+str(orderId)+"','"+str(instrument_name)+"','"+str(orderDate)+"',"+str(avgPrice)+")")
                        message = "I bought "+str(instrument_name).replace('_','-')+" at "+str(avgPrice)+" dollars."
                        print(telegram.sendTelegramMessage(message).content)
                    else:
                        message = "Error while buying "+str(instrument_name).replace('_','-')+": ["+str(orderResult['error_code'])+"] - "+str(orderResult['error_message']).replace('_','-')
                        print(telegram.sendTelegramMessage(message).content)
        else:
            print("---> position: "+position+" | action: "+str(action))
            if position == "BUY":
                price = df.values[-1][4]
                print("---> Update Price")
                executeDbWriteQuery("UPDATE "+os.getenv("TABLE_NAME")+" SET current_price="+str(buy_price)+" WHERE order_id='"+order_id+"'")