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
import requests
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
no_aplica_count = 0
withdrawals_count = defaultdict(int)  # Contador para "withdrawals"
withdrawals_hourly_count = defaultdict(int)  # Para almacenar los conteos por hora
no_aplica_weekday_count = defaultdict(int)  # Contador de "no aplica" por día de la semana (0: lunes, 1: martes, etc.)
last_reset_time = datetime.now(timezone.utc)

chile_tz = pytz.timezone('America/Santiago')

# Funciones para los gráficos de barras
def plot_withdrawals_graph(hourly_data):
    """Genera un gráfico de barras con los conteos de withdrawals por hora."""
    hours = list(hourly_data.keys())
    counts = list(hourly_data.values())

    plt.figure(figsize=(8, 5))
    plt.bar(hours, counts, color='blue')  # Gráfico de barras
    plt.xlabel('Hora del día')
    plt.ylabel('Cantidad de veces el panel al dia')
    plt.title('Panel al dia hora a hora')

    buffer = io.BytesIO()
    plt.savefig(buffer, format='jpg')
    buffer.seek(0)
    return buffer

def plot_no_aplica_weekday_graph(weekday_data):
    """Genera un gráfico de barras con la cantidad de 'no aplica' por día de la semana."""
    days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    counts = [weekday_data[i] for i in range(7)]  # Obtener las frecuencias para cada día

    plt.figure(figsize=(8, 5))
    plt.bar(days, counts, color='blue')  # Gráfico de barras
    plt.xlabel('Día de la semana')
    plt.ylabel('Cantidad de "no aplica"')
    plt.title('Frecuencia de "no aplica" por día de la semana - Último mes')

    buffer = io.BytesIO()
    plt.savefig(buffer, format='jpg')
    buffer.seek(0)
    return buffer

# Funciones de reporte
async def send_daily_withdrawals_report():
    """Envía un gráfico de 'withdrawals' cada medianoche."""
    while True:
        now_utc = datetime.now(timezone.utc)
        now_chile = now_utc.astimezone(chile_tz)

        # Comprobar si es medianoche en la zona horaria de Chile (00:00 hora local)
        if now_chile.hour == 0 and now_chile.minute == 0:
            if withdrawals_hourly_count:
                # Crear un gráfico basado en el conteo por hora
                buffer = plot_withdrawals_graph(withdrawals_hourly_count)

                # Enviar el gráfico y el mensaje resumen
                await client.send_message(group_id_to_forward, "Informe diario de 'PANEL AL DIA'")
                await client.send_file(group_id_to_forward, buffer, caption="FRECUENCIA DE PANEL AL DIA' POR HORA")

                # Reiniciar el contador de withdrawals
                withdrawals_hourly_count.clear()

        # Esperar un minuto antes de volver a verificar
        await asyncio.sleep(60)

def is_last_business_day_of_month(date):
    """Comprueba si la fecha es el último día hábil del mes."""
    month_calendar = calendar.monthcalendar(date.year, date.month)
    last_week = month_calendar[-1]
    second_last_week = month_calendar[-2]

    # Buscar el último día hábil (de lunes a viernes)
    for day in reversed(last_week):
        if day != 0 and calendar.weekday(date.year, date.month, day) < 5:
            return date.day == day
    for day in reversed(second_last_week):
        if day != 0 and calendar.weekday(date.year, date.month, day) < 5:
            return date.day == day
    return False

async def send_monthly_no_aplica_report():
    """Enviar un gráfico con el conteo mensual de 'no aplica' al finalizar el último día hábil."""
    while True:
        now_chile = datetime.now(timezone.utc).astimezone(chile_tz)

        if is_last_business_day_of_month(now_chile) and now_chile.hour == 23 and now_chile.minute == 59:
            if no_aplica_weekday_count:
                # Crear el gráfico del reporte mensual
                buffer = plot_no_aplica_weekday_graph(no_aplica_weekday_count)

                # Enviar el gráfico y el mensaje resumen
                await client.send_message(group_id_to_forward, "Informe mensual de 'no aplica'")
                await client.send_file(group_id_to_forward, buffer, caption="Gráfico mensual de 'no aplica' por día de la semana")

                # Reiniciar el contador mensual
                no_aplica_weekday_count.clear()

        # Esperar un minuto antes de volver a verificar
        await asyncio.sleep(60)

# Manejador de nuevos mensajes
@client.on(events.NewMessage(chats=[group_id_to_monitor1, group_id_to_monitor2, group_id_to_monitor3]))
async def handler(event):
    immediate_keywords = ["error", "action"]
    global no_aplica_count, last_reset_time
    message = event.message.text or event.message.message
    message = message.lower()
    if any(keyword in message for keyword in immediate_keywords):
        new_message = f"**¡ALERTA!** Se ha detectado una incidencia:\n\n{message}"
        await client.send_message(group_id_to_forward, new_message, parse_mode='Markdown')
        print(f"Mensaje con alerta enviado desde {event.chat_id} al grupo {group_id_to_forward}")

    print(f"Mensaje recibido: {message}")

    # Contador de "no aplica"
    if "no aplica" in message:
        no_aplica_count += 1
        current_day_of_week = datetime.now(timezone.utc).astimezone(chile_tz).weekday()
        no_aplica_weekday_count[current_day_of_week] += 1
        print("Contador 'no aplica':", no_aplica_count)

    # Palabras clave que activan el contador de retiros
    withdrawals_keywords = [
        "no new customers on waiting list withdrawals under 100k",
        "no new customers on waiting list withdrawals under 300k"
    ]

    # Manejo de palabras clave para el contador de retiros
    if any(keyword in message for keyword in withdrawals_keywords):
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour

        if current_time - last_reset_time >= timedelta(hours=1):
            withdrawals_count.clear()  # Reiniciar el contador cada hora
            last_reset_time = current_time

        for keyword in withdrawals_keywords:
            if keyword in message:
                withdrawals_count[keyword] += 1
                withdrawals_hourly_count[current_hour] += 1
                print(f"Contador de retiros para {keyword}: {withdrawals_count[keyword]}")

        # Verificar si se han recibido tres mensajes
        total_withdrawals = sum(withdrawals_count[keyword] for keyword in withdrawals_keywords)
        if total_withdrawals >= 3:
            await client.send_message(group_id_to_forward, "bot de retiros no encuentra retiros")
            print(f"Mensaje de alerta enviado al grupO {group_id_to_forward}")
            withdrawals_count.clear()  # Reiniciar el contador después de enviar el mensaje
@client.on(events.NewMessage(pattern=r'^/nick\s+(.+)', chats=[group_id_to_forward]))
async def kuroro_sherlock_handler(event):
    try:
        nick = event.pattern_match.group(1).strip()
        resultado = buscar_usuario_con_sherlock(nick)
        if resultado:
            await client.send_message(event.chat_id, f"🔎 Resultados de Sherlock para `{nick}`:\n\n```{resultado}```", parse_mode="Markdown")
        else:
            await client.send_message(event.chat_id, f"No se encontraron resultados para `{nick}`.")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error al analizar con Sherlock: {e}")

def get_truora_status():
    try:
        url = "https://stats.uptimerobot.com/api/getMonitorList/VG3Y9Cgwwq?page=1"
        response = requests.get(url, timeout=5)
        data = response.json()

        # Acceder correctamente al campo de estadísticas
        counts = data.get("statistics", {}).get("counts", {})
        up = counts.get("up", 0)
        down = counts.get("down", 0)
        paused = counts.get("paused", 0)

        # Elegimos el emoji correcto
        if down == 0:
            emoji = "🟢"
        elif up > 0 and down > 0:
            emoji = "🟡"
        else:
            emoji = "🔴"

        return f"{emoji} *Truora*: {up} arriba, {down} abajo, {paused} pausado(s)"
    except Exception as e:
        return f"⚠️ *Truora*: Error al consultar ({str(e)})"



allowed_groups = [group_id_to_forward, group_id_to_monitor3]
@client.on(events.NewMessage(pattern=r'^/servicios$', chats=allowed_groups))
async def check_services_status(event):
    statuses = []

    # Truora con scraping
    truora_status = get_truora_status()
    statuses.append(truora_status)

    # Resto de servicios con API JSON
    other_services = {
        "Kushki": "https://status.kushkipagos.com/api/v2/status.json",
        "Transbank": "https://status.transbankdevelopers.cl/api/v2/status.json",
    }

    for name, url in other_services.items():
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            status = data['status']['description']
            emoji = "🟢" if "Operational" in status else "🟡" if "Degraded" in status else "🔴"
            statuses.append(f"{emoji} *{name}*: {status}")
        except Exception as e:
            statuses.append(f"⚠️ *{name}*: Error al consultar ({str(e)})")

    message = "**Estado actual de servicios de pasarelas:**\n\n" + "\n".join(statuses)
    await client.send_message(event.chat_id, message, parse_mode='Markdown')

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
    await client.send_message(event.chat_id, f"🔎 Buscando perfiles de Facebook para: `{nombre}`...", parse_mode="Markdown")
    try:
        links = buscar_perfil_facebook(nombre)
        if links:
            msg = "**Resultados de búsqueda de perfiles de Facebook:**\n\n"
            msg += "\n".join([f"{i+1}. {link}" for i, link in enumerate(links)])
            await client.send_message(event.chat_id, msg, parse_mode="Markdown")
        else:
            await client.send_message(event.chat_id, f"No se encontraron perfiles de Facebook para `{nombre}`.")
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error al buscar perfiles de Facebook: {e}")

# Main
async def main():
    await client.start()
    client.loop.create_task(send_daily_withdrawals_report())  # Tarea diaria de 'withdrawals'
    client.loop.create_task(send_monthly_no_aplica_report())  # Tarea mensual de 'no aplica'

    print("Monitoring...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())

