import os
import sys
import requests
import asyncio
import imaplib
import email

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


keep_alive()
sys.stdout.reconfigure(encoding='utf-8')


# VARIABLES DE ENTORNO
string_session = os.getenv('STRING_SESSION')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

group_id_to_monitor1 = int(os.getenv('GROUP_ID_TO_MONITOR1'))
group_id_to_monitor2 = int(os.getenv('GROUP_ID_TO_MONITOR2'))
group_id_to_monitor3 = int(os.getenv('GROUP_ID_TO_MONITOR3'))

group_id_to_forward = int(os.getenv('GROUP_ID_TO_FORWARD'))

gmail_user = os.getenv("GMAIL_USER")
gmail_pass = os.getenv("GMAIL_PASS")


client = TelegramClient(StringSession(string_session), api_id, api_hash)


allowed_groups = [
    group_id_to_forward,
    group_id_to_monitor3
]


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
        return f"⚠️ *Truora*: Error ({e})"


def get_astropay_status():
    try:
        response = requests.get(
            "https://status.astropay.com/api/v2/status.json", timeout=5)

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
        return f"⚠️ *AstroPay*: Error ({e})"


def get_kushki_status():
    try:
        response = requests.get(
            "https://status.kushkipagos.com/api/v2/status.json", timeout=5)

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
        return f"⚠️ *Kushki*: Error ({e})"


def get_transbank_status():
    try:
        response = requests.get(
            "https://status.transbankdevelopers.cl/api/v2/status.json", timeout=5)

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
        return f"⚠️ *Transbank*: Error ({e})"


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
        response = requests.get(
            "https://app.cryptoprocessing.com/api/v2/ping", timeout=5)

        if response.status_code == 200:
            return "🟢 *CoinPaid*: Activo"
        else:
            return f"🔴 *CoinPaid*: HTTP {response.status_code}"

    except Exception as e:
        return f"⚠️ *CoinPaid*: Error ({e})"


@client.on(events.NewMessage(pattern=r'^/servicios$', chats=allowed_groups))
async def check_services_status(event):

    statuses = [
        get_truora_status(),
        get_astropay_status(),
        get_kushki_status(),
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

        await event.respond(
            f"🔎 Resultados de Sherlock para `{nick}`:\n\n```{resultado}```",
            parse_mode="Markdown"
        )

    else:
        await event.respond(f"❌ No se encontraron resultados para `{nick}`.")


# 📧 LEER CUERPO DEL CORREO
def extraer_cuerpo_email(msg):

    cuerpo = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()

            if content_type == "text/plain":
                cuerpo = part.get_payload(decode=True).decode(errors="ignore")
                return cuerpo

            if content_type == "text/html":
                html = part.get_payload(decode=True).decode(errors="ignore")
                soup = BeautifulSoup(html, "lxml")
                return soup.get_text()

    else:
        cuerpo = msg.get_payload(decode=True).decode(errors="ignore")

    return cuerpo


# 📧 REVISAR GMAIL
async def revisar_correos_gmail():

    try:

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_user, gmail_pass)
        mail.select("inbox")

        status, mensajes = mail.search(
            None,
            '(UNSEEN SUBJECT "Casino High Win Alert")'
        )

        for num in mensajes[0].split():

            status, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            cuerpo = extraer_cuerpo_email(msg)

            cuerpo = cuerpo.strip()[:3000]

            await client.send_message(group_id_to_forward, cuerpo)

        mail.logout()

    except Exception as e:
        print("Error leyendo Gmail:", e)


async def loop_correos():

    while True:

        await revisar_correos_gmail()

        await asyncio.sleep(15)


async def main():

    await client.start()

    print("Bot en funcionamiento...")

    client.loop.create_task(loop_correos())

    await client.run_until_disconnected()


with client:

    client.loop.run_until_complete(main())

