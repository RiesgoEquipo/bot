import os
import sys
import io
import asyncio
import requests
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from telethon import events
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from keep_alive import keep_alive
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
import pytz

# 🌐 ZONA HORARIA
chile_tz = pytz.timezone('America/Santiago')

# 🚀 INICIALIZACIÓN
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

client = TelegramClient(StringSession(string_session), api_id, api_hash)

# -----------------------------------
# 🔍 FUNCIONES PARA SHERLOCK
# -----------------------------------
def buscar_usuario_con_sherlock(nick):
    try:
        result = subprocess.run(["sherlock", nick], capture_output=True, text=True, timeout=500)
        return result.stdout
    except Exception as e:
        return f"Error al ejecutar Sherlock: {e}"

# -----------------------------------
# 📊 FUNCIONES PARA ESTADO DE SERVICIOS
# -----------------------------------
def get_truora_status():
    try:
        url = "https://stats.uptimerobot.com/api/getMonitorList/VG3Y9Cgwwq?page=1"
        response = requests.get(url, timeout=5)
        data = response.json()
        counts = data.get("statistics", {}).get("counts", {})
        up, down, paused = counts.get("up", 0), counts.get("down", 0), counts.get("paused", 0)

        emoji = "🟢" if down == 0 else "🟡" if up > 0 else "🔴"
        return f"{emoji} *Truora*: {up} arriba, {down} abajo, {paused} pausado(s)"
    except Exception as e:
        return f"⚠️ *Truora*: Error al consultar ({str(e)})"

def get_astropay_status():
    try:
        response = requests.get("https://status.astropay.com/api/v2/status.json", timeout=5)
        data = response.json()
        desc = data["status"]["description"]
        emoji = {
            "none": "🟢", "minor": "🟡", "major": "🔴", "critical": "❌"
        }.get(data["status"]["indicator"], "❓")
        return f"{emoji} *AstroPay*: {desc}"
    except Exception as e:
        return f"⚠️ *AstroPay*: Error al consultar estado ({e})"

def get_kushki_status():
    try:
        url = "https://status.kushkipagos.com"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        status = soup.find("span", class_="component-status").text.strip()
        emoji = "🟢" if "operational" in status.lower() else "🟡" if "degraded" in status.lower() else "🔴"
        return f"{emoji} *Kushki*: {status}"
    except Exception as e:
        return f"⚠️ *Kushki*: Error al consultar ({e})"

def get_transbank_status():
    try:
        response = requests.get("https://status.transbank.cl/", timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        status = soup.find("span", class_="component-status").text.strip()
        emoji = "🟢" if "operativo" in status.lower() else "🔴"
        return f"{emoji} *Transbank*: {status}"
    except Exception as e:
        return f"⚠️ *Transbank*: Error al consultar ({e})"

# -----------------------------------
# 📎 COMANDO /NICK PARA SHERLOCK
# -----------------------------------
@client.on(events.NewMessage(pattern=r'^/nick\s+(.+)', chats=[group_id_to_forward]))
async def kuroro_sherlock_handler(event):
    nick = event.pattern_match.group(1).strip()
    resultado = buscar_usuario_con_sherlock(nick)
    mensaje = f"🔎 Resultados de Sherlock para `{nick}`:\n\n```{resultado}```" if resultado else f"No se encontraron resultados para `{nick}`."
    await client.send_message(event.chat_id, mensaje, parse_mode="Markdown")

# -----------------------------------
# ⚙️ COMANDO /SERVICIOS PARA VER STATUS
# -----------------------------------
@client.on(events.NewMessage(pattern=r'^/servicios$', chats=[group_id_to_forward]))
async def servicios_handler(event):
    statuses = [
        get_truora_status(),
        get_astropay_status(),
        get_kushki_status(),
        get_transbank_status()
    ]
    await client.send_message(event.chat_id, "\n".join(statuses), parse_mode="Markdown")

# -----------------------------------
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

# -----------------------------------
# 🚀 EJECUCIÓN
# -----------------------------------
client.start()
client.run_until_disconnected()
