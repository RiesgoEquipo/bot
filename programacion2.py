import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon import events
import sys
from keep_alive import keep_alive
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import asyncio
import matplotlib.pyplot as plt
import io
import pytz
import calendar
import aiohttp

# Inicializar el bot
keep_alive()

# Configura la consola para utilizar UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Cargar las variables de entorno
string_session = os.getenv('STRING_SESSION')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
group_id_to_monitor1 = int(os.getenv('GROUP_ID_TO_MONITOR1'))
group_id_to_monitor2 = int(os.getenv('GROUP_ID_TO_MONITOR2'))
group_id_to_monitor3 = int(os.getenv('GROUP_ID_TO_MONITOR3'))
group_id_to_forward = int(os.getenv('GROUP_ID_TO_FORWARD'))

client = TelegramClient(StringSession(string_session), api_id, api_hash)

# Contadores
withdrawals_count = defaultdict(int)
withdrawals_hourly_count = defaultdict(int)
last_reset_time = datetime.now(timezone.utc)

chile_tz = pytz.timezone('America/Santiago')

status_urls = {
    "Truora": "https://status.truora.com",
    "Kushki": "https://status.kushkipagos.com",
    "Transbank": "https://status.transbankdevelopers.cl"
}

# Función para gráfico de retiros
def plot_withdrawals_graph(hourly_data):
    hours = list(hourly_data.keys())
    counts = list(hourly_data.values())

    plt.figure(figsize=(8, 5))
    plt.bar(hours, counts, color='blue')
    plt.xlabel('Hora del día')
    plt.ylabel('Cantidad de veces el panel al día')
    plt.title('Panel al día hora a hora')

    buffer = io.BytesIO()
    plt.savefig(buffer, format='jpg')
    buffer.seek(0)
    return buffer

# Reporte diario de retiros
async def send_daily_withdrawals_report():
    while True:
        now_utc = datetime.now(timezone.utc)
        now_chile = now_utc.astimezone(chile_tz)

        if now_chile.hour == 0 and now_chile.minute == 0:
            if withdrawals_hourly_count:
                buffer = plot_withdrawals_graph(withdrawals_hourly_count)
                await client.send_message(group_id_to_forward, "Informe diario de 'PANEL AL DIA'")
                await client.send_file(group_id_to_forward, buffer, caption="FRECUENCIA DE PANEL AL DIA POR HORA")
                withdrawals_hourly_count.clear()

        await asyncio.sleep(60)

# Verifica servicios externos
async def check_services_status():
    down_services = []
    async with aiohttp.ClientSession() as session:
        for name, url in status_urls.items():
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        down_services.append(f"{name} (HTTP {response.status})")
            except Exception:
                down_services.append(f"{name} (Error de conexión)")
    return down_services

# Monitoreo periódico
async def monitor_services():
    last_status = set()
    while True:
        now_chile = datetime.now(timezone.utc).astimezone(chile_tz)

        down_services = await check_services_status()
        current_status = set(down_services)

        if current_status != last_status:
            if down_services:
                msg = "⚠️ *Servicios caídos detectados:*\n" + "\n".join(f"- {s}" for s in down_services)
            else:
                msg = "✅ Todos los servicios están activos nuevamente."

            await client.send_message(group_id_to_forward, msg, parse_mode='Markdown')
            last_status = current_status

        if now_chile.hour == 8 and now_chile.minute == 30:
            msg = "📊 *Estado diario de servicios a las 8:30am:*\n"
            if down_services:
                msg += "⚠️ Caídos:\n" + "\n".join(f"- {s}" for s in down_services)
            else:
                msg += "✅ Todos están operativos."

            await client.send_message(group_id_to_forward, msg, parse_mode='Markdown')
            await asyncio.sleep(60)

        await asyncio.sleep(300)

# Manejador de mensajes
@client.on(events.NewMessage(chats=[group_id_to_monitor1, group_id_to_monitor2, group_id_to_monitor3]))
async def handler(event):
    immediate_keywords = ["error", "action"]
    global last_reset_time
    message = event.message.text or event.message.message
    message = message.lower().strip()

    # 🟢 Comando status
    if message == "status":
        down_services = await check_services_status()
        if down_services:
            msg = "⚠️ *Servicios caídos actualmente:*\n" + "\n".join(f"- {s}" for s in down_services)
        else:
            msg = "✅ Todos los servicios están operativos."
        await event.reply(msg, parse_mode='Markdown')
        return

    # 🚨 Alertas por keywords
    if any(keyword in message for keyword in immediate_keywords):
        new_message = f"**¡ALERTA!** Se ha detectado una incidencia:\n\n{message}"
        await client.send_message(group_id_to_forward, new_message, parse_mode='Markdown')
        print(f"Mensaje con alerta enviado desde {event.chat_id} al grupo {group_id_to_forward}")

    print(f"Mensaje recibido: {message}")

    # 📊 Lógica de retiros
    withdrawals_keywords = [
        "no new customers on waiting list withdrawals under 100k",
        "no new customers on waiting list withdrawals under 300k"
    ]

    if any(keyword in message for keyword in withdrawals_keywords):
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour

        if current_time - last_reset_time >= timedelta(hours=1):
            withdrawals_count.clear()
            last_reset_time = current_time

        for keyword in withdrawals_keywords:
            if keyword in message:
                withdrawals_count[keyword] += 1
                withdrawals_hourly_count[current_hour] += 1
                print(f"Contador de retiros para {keyword}: {withdrawals_count[keyword]}")

        total_withdrawals = sum(withdrawals_count[keyword] for keyword in withdrawals_keywords)
        if total_withdrawals >= 3:
            await client.send_message(group_id_to_forward, "bot de retiros no encuentra retiros en cola")
            print(f"Mensaje de alerta enviado al grupo {group_id_to_forward}")
            withdrawals_count.clear()

# Main
async def main():
    await client.start()
    client.loop.create_task(send_daily_withdrawals_report())
    client.loop.create_task(monitor_services())
    print("🤖 Bot en funcionamiento...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
