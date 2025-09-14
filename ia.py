from transformers import pipeline

# cargamos el modelo distilgpt2 (se descarga la primera vez)
generator = pipeline("text-generation", model="datificate/gpt2-small-spanish")

def generar_respuesta(prompt: str, max_new_tokens: int = 100) -> str:
    salida = generator(prompt, max_new_tokens=max_new_tokens, num_return_sequences=1)
    return salida[0]["generated_text"]

if __name__ == "__main__":
    print("🤖 IA cargada. Escribe 'salir' para terminar.\n")
    while True:
        entrada = input("Tú: ")
        if entrada.lower() in ["salir", "exit", "quit"]:
            print("👋 ¡Adiós!")
            break
        respuesta = generar_respuesta(entrada, max_new_tokens=80)
        print(f"IA: {respuesta}\n")
