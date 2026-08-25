

async def connect_lavalink(self):
    await self.bot.wait_until_ready()
    print("🔄 Intentando conectar a Lavalink...")
    try:
        node = wavelink.Node(
            uri="https://lavalinkv4.serenetia.com/v4/websocket",
            password="https://dsc.gg/ajidevserver"
        )
        print("🔄 Nodo creado, conectando pool...")
        await wavelink.Pool.connect(nodes=[node], client=self.bot)
        print("✅ Lavalink conectado")
    except Exception as e:
        print("❌ Error conectando Lavalink:", e)