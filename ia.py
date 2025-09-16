import cohere
from collections import deque


class IA():
    def __init__(self,api):
        self.api_key = api
        self.co = cohere.Client(self.api_key)
        self.historial = deque(maxlen=29)
    def chat(self,message):
        self.historial.append({"role": "USER", "message": message})
        response = self.co.chat(
            model="command-a-03-2025",
            message=message,
            chat_history=self.historial # pasamos todo menos el último, que ya está en "message"
        )
        bot_reply = response.text.strip()
        self.historial.append({"role": "CHATBOT", "message": bot_reply})
        return bot_reply

