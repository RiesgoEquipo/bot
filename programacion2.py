import os
import sys
import requests
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon import events
from keep_alive import keep_alive
from bs4 import BeautifulSoup
import subprocess
from serpapi import GoogleSearch

def buscar_usuario_con_sherlock(nick):
    try:
        result = subprocess.run(
            ["sherlock", nick],
            capture_output=True, text=True, timeout=500
        )
        return result.stdout
    except Exception as e:
        return f"Error al ejecutar Sherlock: {e}"

# Inicializar el bot
keep_alive()
sys.stdout.reconfigure(encoding='utf-8')

# 🔐 VARIABLES DE ENTORNO
string_session = os.getenv('STRING_SESSION')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
group_id_to_monitor1 = int(os.getenv('GROUP_ID_TO_MONITOR1'))
group_id_to_monitor2 = int(os.getenv('GROUP_ID_TO_MONITOR2'))
group_id_to_monitor3 = int(os.getenv('GROUP_ID_TO_MONITOR3'))
group_id_to_forward = int(os.getenv('GROUP_ID_TO_FORWARD'))
group_id_to_monitor4  = int(os.getenv('PETE'))
group_id_to_monitor5  = str(os.getenv('GIO'))


# Inicializar el cliente de Telegram
client = TelegramClient(StringSession(string_session), api_id, api_hash)

# Grupos permitidos para usar comandos
allowed_groups = [group_id_to_forward, group_id_to_monitor3,group_id_to_monitor4,group_id_to_monitor5]

# Funciones para obtener el estado de los servicios
def get_truora_status():
    try:
        url = "https://stats.uptimerobot.com/api/getMonitorList/VG3Y9Cgwwq?page=1"
        response = requests.get(url, timeout=5)
        data = response.json()
        counts = data.get("statistics", {}).get("counts", {})
        up = counts.get("up", 0)
        down = counts.get("down", 0)
        paused = counts.get("paused", 0)
        emoji = "🟢" if down == 0 else "🟡" if up > 0 else "🔴"
        return f"{emoji} *Truora*: {up} arriba, {down} abajo, {paused} pausado(s)"
    except Exception as e:
        return f"⚠️ *Truora*: Error al consultar ({str(e)})"

def get_astropay_status():
    try:
        response = requests.get("https://status.astropay.com/api/v2/status.json", timeout=5)
        data = response.json()
        description = data["status"]["description"]
        indicator = data["status"]["indicator"]
        emoji = {
            "none": "🟢",
            "minor": "🟡",
            "major": "🔴",
            "critical": "❌"
        }.get(indicator, "❓")
        return f"{emoji} *AstroPay*: {description}"
    except Exception as e:
        return f"⚠️ *AstroPay*: Error al consultar estado ({e})"

def get_kushki_status():
    try:
        response = requests.get("https://status.kushkipagos.com/api/v2/status.json", timeout=5)
        data = response.json()
        description = data["status"]["description"]
        indicator = data["status"]["indicator"]
        emoji = {
            "none": "🟢",
            "minor": "🟡",
            "major": "🔴",
            "critical": "❌"
        }.get(indicator, "❓")
        return f"{emoji} *Kushki*: {description}"
    except Exception as e:
        return f"⚠️ *Kushki*: Error al consultar estado ({e})"

def get_transbank_status():
    try:
        response = requests.get("https://status.transbankdevelopers.cl/api/v2/status.json", timeout=5)
        data = response.json()
        description = data["status"]["description"]
        indicator = data["status"]["indicator"]
        emoji = {
            "none": "🟢",
            "minor": "🟡",
            "major": "🔴",
            "critical": "❌"
        }.get(indicator, "❓")
        return f"{emoji} *Transbank*: {description}"
    except Exception as e:
        return f"⚠️ *Transbank*: Error al consultar estado ({e})"

def get_skinsback_status():
    try:
        response = requests.get("https://skinsback.com", timeout=5)
        if response.status_code == 200:
            return "🟢 *Skinsback*: Activo"
        else:
            return f"🔴 *Skinsback*: HTTP {response.status_code}"
    except Exception as e:
        return f"⚠️ *Skinsback*: Error ({e})"

def get_coinpaid_status():
    try:
        response = requests.get("https://app.cryptoprocessing.com/api/v2/ping", timeout=5)
        if response.status_code == 200:
            return "🟢 *CoinPaid*: Activo"
        else:
            return f"🔴 *CoinPaid*: HTTP {response.status_code}"
    except Exception as e:
        return f"⚠️ *CoinPaid*: Error ({e})"

# Comando /servicios para verificar el estado de los servicios
@client.on(events.NewMessage(pattern=r'^/servicios$', chats=allowed_groups))
async def check_services_status(event):
    statuses = [
        get_truora_status(),
        get_astropay_status(),
        """ error """
        get_kushki_status(),
        """ error """
        get_transbank_status(),
        get_skinsback_status(),
        get_coinpaid_status()
    ]
    message = "**Estado actual de servicio de pasarelas:**\n\n" + "\n".join(statuses)
    await client.send_message(event.chat_id, message, parse_mode='Markdown')

@client.on(events.NewMessage(pattern=r'^/nick\s+(.+)', chats=[group_id_to_forward]))
async def handler_sherlock(event):
    nick = event.pattern_match.group(1).strip()
    await event.respond("🔍 Buscando información...")
    resultado = buscar_usuario_con_sherlock(nick)
    if resultado:
        await event.respond(f"🔎 Resultados de Sherlock para `{nick}`:\n\n```{resultado}```", parse_mode="Markdown")
    else:
        await event.respond(f"❌ No se encontraron resultados para `{nick}`.")


def buscar_perfil_facebook(nombre):
    """Busca perfiles de Facebook usando SerpAPI y retorna una lista de enlaces."""
    api_key = "171d9aef80acd2ce6924cb403e3dc64fa8530a9577b6bf5e6fdd9f878b355b32"
    params = {
        "q": f"site:facebook.com {nombre}",
        "engine": "google",
        "api_key": api_key
    }
    search = GoogleSearch(params)
    resultados = search.get_dict()
    links = []
    for result in resultados.get("organic_results", []):
        if "facebook.com" in result.get("link", ""):
            links.append(result.get("link"))
    return links
@client.on(events.NewMessage(pattern=r'^/perfil\s+(.+)', chats=allowed_groups))
async def facebook_profile_search_handler(event):
    nombre = event.pattern_match.group(1).strip()
    await client.send_message(event.chat_id, f"🔎 Buscando perfiles de Facebook para: {nombre}...", parse_mode="Markdown")
    try:
        links = buscar_perfil_facebook(nombre)
        if links:
            msg = "**Resultados de búsqueda de perfiles de Facebook:**\n\n"
            msg += "\n".join([f"{i+1}. {link}" for i, link in enumerate(links)])
            await client.send_message(event.chat_id, msg, parse_mode="Markdown")
        else:
            await client.send_message(event.chat_id, f"No se encontraron perfiles de Facebook para {nombre}.")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error al buscar perfiles de Facebook: {e}")
# 📡 MONITOREO DE MENSAJES CON PALABRAS CLAVE
# -----------------------------------
@client.on(events.NewMessage(chats=[group_id_to_monitor1, group_id_to_monitor2, group_id_to_monitor3]))
async def handler(event):
    keywords = ["error", "action"]
    message = (event.message.text or event.message.message).lower()

    if any(k in message for k in keywords):
        alerta = f"**¡ALERTA!** Se ha detectado una incidencia:\n\n{message}"
        await client.send_message(group_id_to_forward, alerta, parse_mode='Markdown')
        print(f"🔔 Alerta reenviada desde {event.chat_id}")
# Función principal
async def main():
    await client.start()
    print("Bot en funcionamiento...")
    await client.run_until_disconnected()

# Ejecutar el bot
with client:
    client.loop.run_until_complete(main())
