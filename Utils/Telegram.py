import requests

class Telegram:

    __botToken = ''
    __receiverId = ''

    def __init__(self,receiverId,botToken):
        self.__receiverId = receiverId
        self.__botToken = botToken

    def sendTelegramMessage(self,message):
        send_text = 'https://api.telegram.org/bot' + self.__botToken + '/sendMessage?chat_id=' + self.__receiverId + '&parse_mode=Markdown&text=' + message+''
        response = requests.get(send_text)