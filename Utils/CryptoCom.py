import time
import hmac
import hashlib
import requests
import json

class CryptoCom:

    __baseUrl = ""
    __apiKey = ""
    __apiSecret = ""
    __nonceFix = ""

    __getInstruments = "public/get-instruments"
    __getBook = "public/get-book"
    __getCandleStick = "public/get-candlestick"
    __getTicker = "public/get-ticker"
    __getPublicTrades = "public/get-trades"
    
    __getAccountSummary = "private/get-account-summary"
    __createOrder = "private/create-order"
    __cancelOrder = "private/cancel-order"
    __cancelAllOrders = "private/cancel-all-orders"
    __getOrderHistory = "private/get-order-history"
    __getOpenOrders = "private/get-open-orders"
    __getOrderDetail = "private/get-order-detail"
    __getTrades = "private/get-trades"

    __orderSideVal = {"BUY","SELL"}
    __orderTypesVal = {"LIMIT", "MARKET", "STOP_LOSS", "STOP_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}
    __timeInForceVal = {"GOOD_TILL_CANCEL","FILL_OR_KILL","IMMEDIATE_OR_CANCEL"}
    __execInstVal = {"POST_ONLY"}
    __allowedTimeframe = {"1m", "5m", "15m", "30m", "1h", "4h", "6h", "12h", "1D", "7D", "14D", "1M"}

    def __init__(self,apiKey,apiSecret,baseUrl,nonceFix=0):
        self.__apiKey = apiKey
        self.__apiSecret = apiSecret
        self.__baseUrl = baseUrl
        self.__nonceFix = nonceFix
        
    def __generateNonce(self):
        return int(time.time() * 1000)-int(self.__nonceFix)
    
    def __createSigPayload(self, request):
        # First ensure the params are alphabetically sorted by key
        paramString = ""

        if "params" in request:
            for key in sorted(request['params']):
                paramString += key
                paramString += str(request['params'][key])

        sigPayload = request['method'] + str(request['id']) + request['api_key'] + paramString + str(request['nonce'])

        sigPayloadRet = hmac.new(
            bytes(str(self.__apiSecret), 'utf-8'),
            msg=bytes(sigPayload, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        return sigPayloadRet

    def __createReturnJson(self,code,message=None,result=None):
        if message == None:
            retMsg = ''
        else:
            retMsg = message

        if result == None:
            retRes = ''
        else:
            retRes = result
            
        return {"error_code": code, "error_message": retMsg, "result": retRes}

    def __executeRequest(self, path, method, params={}):
        if method == "GET":
            paramString = ""
            for key in params:
                paramString += key
                paramString += "="+str(params[key])+"&"

            response = requests.get(self.__baseUrl+path+"?"+paramString)

        elif method == "POST":
            request = {
                "id": 11,
                "method": str(path),
                "api_key": self.__apiKey,
                "params": params,
                "nonce": self.__generateNonce()
            }

            request['sig'] = self.__createSigPayload(request)

            response = requests.post(self.__baseUrl+path, json=request, headers={'Content-Type':'application/json'})

        data = json.loads(response.text)

        if data['code'] != 0:
            return self.__createReturnJson(data['code'], data['message'])
            
        return self.__createReturnJson(0,None,data['result'])

    def getInstruments(self):
        return self.__executeRequest(self.__getInstruments, "GET")

    def getBook(self,ticker,depth=None):
        params = {
            "instrument_name": ticker
        }
        if depth != None:
            params['depth'] = depth

        return self.__executeRequest(self.__getBook, "GET", params)

    def getCandlestick(self, ticker, timeframe):

        if timeframe not in self.__allowedTimeframe:
            return self.__createReturnJson(9000, "Wrong timeframe. Allowed 1m, 5m, 15m, 30m, 1h, 4h, 6h, 12h, 1D, 7D, 14D, 1M")

        params = {
            "instrument_name": ticker,
            "timeframe": timeframe
        }
        return self.__executeRequest(self.__getCandleStick, "GET", params)

    def getTicker(self,ticker=None):
        params = {}
        if ticker != None:
            params = {
                "instrument_name": ticker
            }
        return self.__executeRequest(self.__getTicker, "GET", params)

    def getPublicTrades(self,ticker=None):
        params = {}
        if ticker != None:
            params = {
                "instrument_name": ticker
            }
        return self.__executeRequest(self.__getPublicTrades, "GET", params)

    def getAccountSummary(self,currency=None):
        
        params = {}
        if currency != None:
            params = {
                "currency": currency
            }

        return self.__executeRequest(self.__getAccountSummary, "POST", params)

    def createOrder(self,ticker,side,type,price=None,quantity=None,notional=None,client_oid=None,time_in_force=None,exec_inst=None,trigger_price=None):
        params = {}

        params['instrument_name'] = ticker

        if side not in self.__orderSideVal:
            return self.__createReturnJson(9000, "Order side allow these values: BUY, SELL")
        params['side'] = side

        if type not in self.__orderTypesVal:
            return self.__createReturnJson(9000, "Order type allow these values: LIMIT, MARKET, STOP_LOSS, STOP_LIMIT, TAKE_PROFIT, TAKE_PROFIT_LIMIT")
        params['type'] = type

        if type=="LIMIT":
            if quantity==None or price==None:
                return self.__createReturnJson(9000, "For LIMIT orders quantity and price are both mandatory")
            params['quantity'] = quantity
            params['price'] = price

            if time_in_force in self.__timeInForceVal:
                params['time_in_force'] = time_in_force
            else:
                return self.__createReturnJson(9000, "time_in_force allowed values are GOOD_TILL_CANCEL, FILL_OR_KILL, IMMEDIATE_OR_CANCEL")

            if exec_inst != None and exec_inst in self.__execInstVal:
                params['exec_inst'] = exec_inst
            else:
                return self.__createReturnJson(9000, "exec_inst allowed value is POST_ONLY")

        elif type=="MARKET":
            if side=="BUY":
                if quantity!=None and notional!=None:
                    return self.__createReturnJson(9000, "For BUY MARKET orders notional and quantity are mutually exclusive")
                else:
                    if quantity!=None:
                        params['quantity'] = quantity
                    if notional!=None:
                        params['notional'] = notional
            else:
                if quantity==None:
                    return self.__createReturnJson(9000, "For SELL MARKET orders quantity is mandatory")
                params['quantity'] = quantity

        elif type=="STOP_LIMIT" or type=="TAKE_PROFIT_LIMIT":
            if quantity==None or price==None or trigger_price==None:
                return self.__createReturnJson(9000, "For "+type+" orders quantity, price, trigger_price are mandatory")
            params['quantity'] = quantity
            params['price'] = price
            params['trigger_price'] = trigger_price

        elif type=="STOP_LOSS" or type=="TAKE_PROFIT":
            if side=="BUY":
                if notional==None or trigger_price==None:
                    return self.__createReturnJson(9000, "For BUY "+type+" orders notional and trigger_price are mandatory")
                params['notional'] = notional
                params['trigger_price'] = trigger_price
            else:
                if quantity==None or trigger_price==None:
                    return self.__createReturnJson(9000, "For SELL "+type+" orders quantity and trigger_price are mandatory")
                params['quantity'] = quantity
                params['trigger_price'] = trigger_price

        return self.__executeRequest(self.__createOrder,"POST",params)

    def cancelOrders(self,ticker,order_id=None):
        params = {}
        params["instrument_name"] = ticker

        if order_id != None:
            params["order_id"] = str(order_id)
            response = self.__executeRequest(self.__cancelOrder,"POST",params)
            return response['code']
        
        return self.__executeRequest(self.__cancelAllOrders,"POST",params)

    def getOrderHistory(self, ticker=None, start_ts=None, end_ts=None, page_size=None, page=None):
        params = {}
        if ticker != None:
            params['instrument_name'] = ticker
        if start_ts != None:
            params['start_ts'] = start_ts
        if end_ts != None:
            params['end_ts'] = end_ts
        if page_size != None:
            params['page_size'] = page_size
        if page != None:
            params['page'] = page

        return self.__executeRequest(self.__getOrderHistory,"POST",params)

    def getOpenOrders(self, ticker=None, page_size=None, page=None):
        params = {}
        if ticker != None:
            params['instrument_name'] = ticker
        if page_size != None:
            params['page_size'] = page_size
        if page != None:
            params['page'] = page

        return self.__executeRequest(self.__getOpenOrders,"POST",params)

    def getOrderDetail(self, order_id):
        params = {
            "order_id": order_id
        }

        return self.__executeRequest(self.__getOrderDetail,"POST",params)

    def getTrades(self, ticker=None, start_ts=None, end_ts=None, page_size=None, page=None):
        params = {}
        if ticker != None:
            params['instrument_name'] = ticker
        if start_ts != None:
            params['start_ts'] = start_ts
        if end_ts != None:
            params['end_ts'] = end_ts
        if page_size != None:
            params['page_size'] = page_size
        if page != None:
            params['page'] = page

        return self.__executeRequest(self.__getTrades,"POST",params)