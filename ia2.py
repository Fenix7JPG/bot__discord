from llama_cpp import Llama

# modelo quantizado para CPU
llm = Llama(model_path="mistral-7b-instruct.Q4_K_M.gguf")  

respuesta = llm(
    "Responde en español: ¿Qué opinas de los gatos?",
    max_tokens=200,
    stop=["</s>"]
)
print(respuesta["choices"][0]["text"])
