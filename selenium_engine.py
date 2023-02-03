from seleniumwire import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from seleniumwire.utils import decode

from threading import Thread
from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer

import urllib.parse
import random
import time
import json


def train_from_file():
    chatbot = ChatBot(
        "OmegleBot",
        #storage_adapter='chatterbot.storage.SQLStorageAdapter',
        logic_adapters=[
            'chatterbot.logic.BestMatch'
        ],
        database_uri='mysql+pymysql://root:123HTX@localhost/test?charset=utf8mb4'
    )
    trainer = ListTrainer(chatbot)

    with open("dataset.py", "r") as file:
        data = [i for i in file.readlines() if i.startswith("[")]

    for idx, i in zip(range(len(data)), data):
        try: 
            print("Training", idx, "...")
            trainer.train(json.loads(i))
        except:
            print(f"Failed training {idx} as {i}")


class Driver:
    def __init__(self, train: bool = False, read_only: bool = False) -> None:
        self.id = None
        self.server = None
        self.connected = False
        self.last_msg_ts = time.time()
        self.messages = []

        self.skips = [
            "https://exgirl.monster",
            "Hey, check out our new xxx chat lt.ke/uhvEI",
            "Hi\u2009",
            "Hi\u2008",
            "Hi\u2007",
            "Hi\u2006",
            "Hi\u2005",
            "Hi\u2004",
            "Hi\u2003",
            "Hi\u2002",
            "Hi\u2001",
        ]

        self.confidence_lmt = 0.33
        self.idle = [
            "mmh",
            "yeh",
            "hm",
            "mmhm",
            ";)",
        ]

        self.training = train

        if self.training:
            print("Training enabled!")

        self.chatbot = ChatBot(
            "OmegleBot",
            read_only=read_only,
            #storage_adapter='chatterbot.storage.SQLStorageAdapter',
            logic_adapters=[
                'chatterbot.logic.BestMatch'
            ],
            database_uri='mysql+pymysql://root:123HTX@localhost/test?charset=utf8mb4'
        )
        self.trainer = ListTrainer(self.chatbot)

        self.browser = webdriver.Firefox()
        self.browser.response_interceptor = self.catch_messages
        self.browser.request_interceptor = self.interceptor

        self.start()

        while True:
            time.sleep(1)
            if time.time() - self.last_msg_ts > 45 and not self.training:
                print("Disconnecting due to timeout, ", round(time.time() - self.last_msg_ts, 2), "seconds passed with no response")
                self.disconnect()

    def wait_click(self, selector) -> bool:
        try:
            btn = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located(selector))
        except TimeoutException:
            print("Timed out.")
            return False
        
        btn.click()
        return True

    def filter_ctx(self, msg: str) -> bool:
        """Filter outgoing messages to make sure it does not ask for snap etc"""
        if "snap" in msg.lower():
            return False
        elif "telegram" in msg.lower():
            return False
        elif "kik" in msg.lower():
            return False

        return True

    def disconnect(self):
        """Reconnect to a new person"""
        self.last_msg_ts = time.time()
        print("\n~~ DISCONNECTING ~~\n")
        try:
            WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'disconnectbtn'))).click()
            for i in range(3):
                btn = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'disconnectbtn')))
                time.sleep(0.3)

                if "Stop" in btn.text:
                    return
                else:
                    btn.click()
        except TimeoutException:
            print("Timed out disconnection.")
            return 
        self.last_msg_ts = time.time()

    def send_message(self, message):
        """Send a message as the bot, sending a message takes at least 2.3 seconds"""
        try:
            try:
                chatbox = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'chatmsg')))
            except TimeoutException:
                print("Timed out sending message.")
                return False
            
            for i in range(3):
                if chatbox.get_attribute('value').encode('utf-8') == b"":
                    chatbox.send_keys(message[0])
                    time.sleep(0.5+0.2*len(message))
                    chatbox.send_keys(message[1:])
                    time.sleep(.1)
                    self.wait_click((By.CLASS_NAME, "sendbtn"))
                    break
                else:
                    print("Failed to send message, message field is not empty! Retrying in 3 seconds...")
                    time.sleep(3)
        except StaleElementReferenceException:
            pass

    def start(self):
        """Start the bot by connecting to omegle"""
        self.last_msg_ts = time.time()

        self.browser.get('https://www.omegle.com/')

        # Click the connect button
        self.wait_click((By.ID, 'textbtn'))

        # The age checkboxes
        self.wait_click((By.XPATH, "/html/body/div[8]/div/p[1]/label/input"))
        self.wait_click((By.XPATH, "/html/body/div[8]/div/p[2]/label/input"))
        # Confim button
        self.wait_click((By.XPATH, "/html/body/div[8]/div/p[3]/input"))

        # Wait untill the chat is open
        self.wait_click((By.CLASS_NAME, 'disconnectbtn'))

        self.last_msg_ts = time.time()
        print("Ready!")
             
    def catch_messages(self, request, response):
        """Catch http requsets reciveing information from omegle"""
        try:
            if not self.connected:
                body = decode(request.body, request.headers.get('Content-Encoding', 'identity')).decode()
                if "id=" in body:
                    self.id = urllib.parse.unquote(body)[3:]
                    server = request.url.split(".")[0][8:]

                    self.server = server

                    with open("out.txt", "a") as file:
                        if len(self.messages) > 5:
                            print("SAVEING", self.messages)
                            file.write(json.dumps(self.messages)+"\n")
                            print("SAVED")
                        else:
                            print("DROPPING CHAT, too little data")
                    self.messages = []

                    print("\nAstablished connection")
                    print("-"*25)
                    print("ID:", self.id)
                    print("SERVER:", self.server)
                    print("")

                    self.connected = True
                else:
                    return

            if f'{self.server}.omegle.com/events' in request.url:
                self.last_msg_ts = time.time()
                body = json.loads(decode(response.body, response.headers.get('Content-Encoding', 'identity')).decode())
                for event in body:
                    if event[0] == "strangerDisconnected":
                        print("Disconnected!")
                        self.connected = False
                        self.disconnect()
                    elif event[0] == "gotMessage":
                        print("Stranger:",event[1])
                        self.messages.append(str(event[1]))

                        # Bros before hoes
                        if ("f" in event[1].lower() or event[1].lower() in self.skips) and len(self.messages) == 1:
                            print("Bros before hoes")
                            self.disconnect()
                        # If we are currently in a trainng session
                        elif not self.training :
                            # If the message is too long we cant use it for training
                            if len(str(event[1])) < 255:
                                statement = self.chatbot.get_response(str(event[1]))
                                print("Confidence:", statement.confidence*100, "%")

                                if statement.confidence == 0 and len(self.messages) < 3:
                                    print("Looks like a malforemed response or a posible bot, skipping..")
                                    self.disconnect()
                                    return
                                # If the confidence is too low we send a malforemd response, this is set in the init function
                                if statement.confidence < self.confidence_lmt:
                                    print(f"Confidence too low, message '{statement}' ignored.")
                                    statement = random.choice(self.idle)
                                elif not self.filter_ctx(str(statement)):
                                    print(f"Context filter triggered on message '{statement}.")
                                    statement = random.choice(self.idle)

                                # As to not block more incomming requests we send the message in the background
                                Thread(target=self.send_message, args=(str(statement),)).start()
                            else:
                                print("Message too long")
                        
                    else:
                        # print(event)
                        pass

            elif f'{self.server}.omegle.com/send' in request.url:
                body = decode(request.body, request.headers.get('Content-Encoding', 'identity')).decode()
                msg = urllib.parse.unquote(body.split("&")[0][4:])
                print("You:" if self.training else "Bot:", msg)
                self.messages.append(msg)

            elif f'{self.server}.omegle.com/disconnect' in request.url:
                print("Disconnected!")
                self.connected = False
        except UnicodeDecodeError:
            pass

    def interceptor(self, request):
        if f'{self.server}.omegle.com/send' in request.url:
            body = decode(request.body, request.headers.get('Content-Encoding', 'identity')).decode()
            msg = urllib.parse.unquote(body.split("&")[0][4:])

            if msg.startswith("!stop"):
                if not self.training:
                    self.training = True
                    print("Training enabled! Bot responses turned off")
                request.abort()

            elif msg.startswith("!start"):
                if self.training:
                    self.training = False
                    print("Training disabled! Bot responses turned on")
                request.abort()



if __name__ == "__main__":
    if input("Train now? ") == "y":
        train_from_file()

    # driver = Driver(train=True, read_only=False)
    driver = Driver(train=False, read_only=True)

