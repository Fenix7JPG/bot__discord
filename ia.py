
import cohere
from collections import deque
import random

class IA():
    def __init__(self,api):
        self.api_key = api
        self.co = cohere.Client(self.api_key)
        self.historial = deque(maxlen=29)
        self.instruction = "Instrucción: Eres un manager tímido y torpe pero competente. Tu tono es humilde, educado y ligeramente inseguro, pero siempre profesional."

    def chat(self,message):
        historial = []
        #if self.instruction:
            #historial.append(self.instruction)
        historial.extend(self.historial)
        
        self.historial.append({"role": "USER", "message": message})
        response = self.co.chat(
            model="command-a-03-2025",
            message=message,
            chat_history=historial, # pasamos todo menos el último, que ya está en "message"
            preamble=self.instruction
            
        )
        bot_reply = response.text.strip()
        self.historial.append({"role": "CHATBOT", "message": bot_reply})

        return bot_reply
    def actu(self,message):
        historial = []
        if self.instruction:
            historial.append(self.instruction)
        historial.extend(self.historial)
        self.historial.append({"role": "USER", "message": message})

        if random.randint(0,20) == 20:
            
            response = self.co.chat(
                model="command-a-03-2025",
                message= "Analiza la conversación. Si crees que aporta valor responder, devuelve 'SI'. Si no es necesario participar, devuelve 'NO'. No escribas nada más.",
                chat_history=historial, # pasamos todo menos el último, que ya está en "message"
                preamble=self.instruction
                max_tokens=2,
            )
            bot_reply = response.text.strip()
            if bot_reply.upper() == "SI":
                response = self.co.chat(
                    model="command-a-03-2025",
                    message=message,
                    preamble=self.instruction
                    chat_history=historial, # pasamos todo menos el último, que ya está en "message"
                    
                )
                bot_reply = response.text.strip()
                self.historial.append({"role": "CHATBOT", "message": bot_reply})
                return bot_reply
        return None












