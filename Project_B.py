# piython3 -- Weather Application using API

# importing the libraries
from tkinter import *
from tkinter import messagebox
import datetime
import json
import os
from queue import Empty, Queue
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from accuweather_mcp import detect_location

# necessary details
root = Tk()
root.title("Weather App")
root.geometry("620x900")
root.minsize(500, 700)
root['background'] = "#eef3f9"

BASE_DIR = Path(__file__).resolve().parent
temperature_unit = StringVar(value="metric")
selected_timezone_offset_hours = 0.0
selected_timezone_name = "UTC"


def get_api_key():
    env_key = os.getenv("ACCUWEATHER_API_KEY", "")
    env_key = env_key.strip().strip('"').strip("'")
    if env_key:
        return env_key

    key_file = BASE_DIR / "api_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip().strip('"').strip("'")

    return ""


def ensure_api_key():
    try:
        api_key = get_api_key()
    except (OSError, UnicodeError):
        messagebox.showerror("API key error", "Could not read api_key.txt.", parent=root)
        return ""
    if not api_key:
        messagebox.showerror(
            "API key missing",
            "Set ACCUWEATHER_API_KEY or put your AccuWeather key in api_key.txt beside Project_B.py.",
            parent=root,
        )
    return api_key


def accuweather_get(path, parameters):
    url = "https://dataservice.accuweather.com" + path + "?" + urlencode(parameters)
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def weather_icon(code):
    if code in (1, 2, 5, 30):
        return "☀️"
    if code in (3, 4, 6):
        return "⛅"
    if code in (7, 8, 35, 36, 38):
        return "☁️"
    if code == 11:
        return "🌫️"
    if code in (12, 13, 14, 18, 26, 39, 40):
        return "🌧️"
    if code in (15, 16, 17, 41, 42):
        return "⛈️"
    if code in (19, 20, 21, 22, 23, 24, 25, 29, 31, 43, 44):
        return "❄️"
    if code == 32:
        return "🌬️"
    if code in (33, 34, 37):
        return "🌙"
    return "—"


def use_metric_units():
    return temperature_unit.get() != "imperial"


def temperature_symbol():
    return "°C" if use_metric_units() else "°F"


def temperature_field_name():
    return "Metric" if use_metric_units() else "Imperial"


def format_utc_offset(offset_hours):
    total_minutes = int(round(float(offset_hours) * 60))
    sign = "+" if total_minutes >= 0 else "-"
    abs_minutes = abs(total_minutes)
    hours, minutes = divmod(abs_minutes, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def update_location_clock():
    local_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=selected_timezone_offset_hours
    )
    location_clock_value.configure(text=local_now.strftime("%I:%M:%S %p"))
    location_clock_subtitle.configure(
        text=f"{selected_timezone_name} · {format_utc_offset(selected_timezone_offset_hours)}"
    )
    root.after(1000, update_location_clock)


def get_current_weather(location, api_key):
    location_key = quote(str(location["Key"]), safe="")
    observations = accuweather_get(
        "/currentconditions/v1/" + location_key,
        {"apikey": api_key, "details": "true"},
    )
    if not observations:
        raise ValueError("No current conditions available")
    return observations[0]


def get_daily_forecast(location, api_key, days=7, metric=True):
    location_key = quote(str(location["Key"]), safe="")
    response = accuweather_get(
        "/forecasts/v1/daily/10day/" + location_key,
        {"apikey": api_key, "metric": "true" if metric else "false", "details": "false"},
    )
    entries = response.get("DailyForecasts", [])
    return entries[:days]


def render_forecast(forecast_items):
    if not forecast_items:
        forecast_value.configure(text="Forecast unavailable")
        return

    lines = []
    for item in forecast_items:
        day_text = item.get("Date", "")
        try:
            day_name = datetime.datetime.fromisoformat(day_text.replace("Z", "+00:00")).strftime("%a")
        except (ValueError, TypeError):
            day_name = "Day"
        day_icon = weather_icon(item.get("Day", {}).get("Icon"))
        max_value = item.get("Temperature", {}).get("Maximum", {}).get("Value")
        min_value = item.get("Temperature", {}).get("Minimum", {}).get("Value")
        if max_value is None or min_value is None:
            temp_text = "N/A"
        else:
            temp_text = f"{max_value:.0f}{temperature_symbol()}/{min_value:.0f}{temperature_symbol()}"
        lines.append(f"{day_name} {day_icon}  {temp_text}")

    forecast_value.configure(text="\n".join(lines))


def get_hourly_forecast(location, api_key, hours=12, metric=True):
    location_key = quote(str(location["Key"]), safe="")
    entries = accuweather_get(
        "/forecasts/v1/hourly/12hour/" + location_key,
        {"apikey": api_key, "metric": "true" if metric else "false", "details": "false"},
    )
    return entries[:hours]


def render_hourly_forecast(hourly_items):
    if not hourly_items:
        hourly_value.configure(text="Hourly forecast unavailable")
        return

    parsed_entries = []
    for item in hourly_items:
        try:
            timestamp = datetime.datetime.fromisoformat(item.get("DateTime", "").replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        parsed_entries.append((timestamp, item))

    if not parsed_entries:
        hourly_value.configure(text="Hourly forecast unavailable")
        return

    current_day = parsed_entries[0][0].date()
    lines = []
    for timestamp, item in parsed_entries:
        if timestamp.date() != current_day:
            continue
        hour_label = timestamp.strftime("%I %p").lstrip("0")
        hour_icon = weather_icon(item.get("WeatherIcon"))
        temp_value = item.get("Temperature", {}).get("Value")
        if temp_value is None:
            temp_text = "N/A"
        else:
            temp_text = f"{temp_value:.0f}{temperature_symbol()}"
        lines.append(f"{hour_label} {hour_icon}  {temp_text}")

    hourly_value.configure(text="\n".join(lines[:8]) if lines else "Hourly forecast unavailable")


def show_weather(location, current):
    global selected_timezone_offset_hours, selected_timezone_name

    unit_field = temperature_field_name()
    current_temperature = current["Temperature"].get(unit_field, {}).get("Value")
    conditions = current.get("WeatherText") or "Current conditions"
    humidity = current.get("RelativeHumidity")
    past_day = current.get("TemperatureSummary", {}).get("Past24Hour", {})
    tempmin = past_day.get("Minimum", {}).get(unit_field, {}).get("Value")
    tempmax = past_day.get("Maximum", {}).get(unit_field, {}).get("Value")
    coordinates = location["GeoPosition"]
    longitude = coordinates["Longitude"]
    latitude = coordinates["Latitude"]
    country = location["Country"]["LocalizedName"]
    city_result = location["LocalizedName"]

    timezone_info = location.get("TimeZone", {})
    try:
        selected_timezone_offset_hours = float(timezone_info.get("GmtOffset", 0.0) or 0.0)
    except (TypeError, ValueError):
        selected_timezone_offset_hours = 0.0
    selected_timezone_name = timezone_info.get("Name") or "Local time"

    lable_temp.configure(text=f"{current_temperature:.0f}{temperature_symbol()}" if current_temperature is not None else "N/A")
    icon_label.configure(text=weather_icon(current.get("WeatherIcon")))
    condition_label.configure(text=conditions)
    lable_humidity.configure(text=f"{humidity}%" if humidity is not None else "N/A")
    max_temp.configure(text=f"{tempmax:.0f}{temperature_symbol()}" if tempmax is not None else "N/A")
    min_temp.configure(text=f"{tempmin:.0f}{temperature_symbol()}" if tempmin is not None else "N/A")
    lable_lon.configure(text=longitude)
    lable_lat.configure(text=latitude)
    lable_country.configure(text=country)
    lable_citi.configure(text=city_result)


def refresh_for_selected_unit():
    city = city_entry.get().strip()
    if not city or location_button["state"] == DISABLED:
        return
    fetch_city_weather()


def fetch_city_weather():
    if location_button["state"] == DISABLED:
        return
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning("City required", "Enter a city name.", parent=root)
        return

    api_key = ensure_api_key()
    if not api_key:
        return

    try:
        locations = accuweather_get(
            "/locations/v1/cities/search", {"apikey": api_key, "q": city}
        )
        if not locations:
            messagebox.showinfo("City not found", "No matching city was found.", parent=root)
            return
        location = locations[0]
        current = get_current_weather(location, api_key)
        metric_units = use_metric_units()
        show_weather(location, current)
        try:
            render_forecast(get_daily_forecast(location, api_key, metric=metric_units))
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError):
            render_forecast([])
        try:
            render_hourly_forecast(get_hourly_forecast(location, api_key, metric=metric_units))
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError):
            render_hourly_forecast([])
    except HTTPError as error:
        if error.code in (401, 403):
            message = "AccuWeather rejected the key or access to this endpoint. Check your key and subscription."
        elif error.code == 429:
            message = "AccuWeather's request limit was reached. Try again later."
        else:
            message = f"AccuWeather returned HTTP {error.code}."
        messagebox.showerror("Weather lookup failed", message, parent=root)
        return
    except (URLError, OSError, ValueError, KeyError, TypeError, IndexError):
        messagebox.showerror(
            "Weather lookup failed",
            "Could not retrieve or interpret AccuWeather data. Check your connection and try again.",
            parent=root,
        )
        return


def use_my_location():
    api_key = ensure_api_key()
    if not api_key:
        return
    if not messagebox.askyesno(
        "Approximate location",
        "Use your public IP address to find an approximate city? "
        "This contacts api.ipify.org to obtain your IP address and sends it to AccuWeather. "
        "The result may be inaccurate, especially when using a VPN.",
        parent=root,
    ):
        return

    location_button.configure(state=DISABLED, text="Locating...")
    search_button.configure(state=DISABLED)
    results = Queue()

    def lookup():
        try:
            location = detect_location(api_key)
            current = get_current_weather(location, api_key)
            metric_units = use_metric_units()
            try:
                forecast = get_daily_forecast(location, api_key, metric=metric_units)
            except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError):
                forecast = []
            try:
                hourly = get_hourly_forecast(location, api_key, metric=metric_units)
            except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError):
                hourly = []
            results.put((location, current, forecast, hourly, None))
        except HTTPError as error:
            if error.code in (401, 403):
                message = "AccuWeather rejected the key or access to this endpoint."
            elif error.code == 429:
                message = "A request limit was reached. Try again later."
            else:
                message = "Location or weather service is unavailable. Try again later."
            results.put((None, None, None, None, message))
        except Exception:
            results.put((None, None, None, None, "Could not detect your location or retrieve weather. Try a city search."))

    def check_result():
        try:
            location, current, forecast, hourly, error = results.get_nowait()
        except Empty:
            root.after(100, check_result)
            return
        location_button.configure(state=NORMAL, text="Use my location")
        search_button.configure(state=NORMAL)
        if error:
            messagebox.showerror("Location lookup failed", error, parent=root)
            return
        try:
            show_weather(location, current)
            render_forecast(forecast)
            render_hourly_forecast(hourly)
            city_entry.delete(0, END)
            city_entry.insert(0, location["LocalizedName"])
        except (ValueError, KeyError, TypeError, IndexError):
            messagebox.showerror("Location lookup failed", "The weather service returned incomplete data.", parent=root)

    Thread(target=lookup, daemon=True).start()
    root.after(100, check_result)


viewport = Frame(root, bg="#eef3f9")
viewport.pack(fill=BOTH, expand=True)

canvas = Canvas(viewport, bg="#eef3f9", highlightthickness=0)
scrollbar = Scrollbar(viewport, orient=VERTICAL, command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side=RIGHT, fill=Y)
canvas.pack(side=LEFT, fill=BOTH, expand=True)

content = Frame(canvas, bg="#eef3f9", padx=24, pady=20)
content_window = canvas.create_window((0, 0), window=content, anchor=NW)
content.columnconfigure(0, weight=1)


def _on_content_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))


def _on_canvas_configure(event):
    canvas.itemconfigure(content_window, width=event.width)


content.bind("<Configure>", _on_content_configure)
canvas.bind("<Configure>", _on_canvas_configure)

Label(content, text="Weather", bg="#eef3f9", fg="#0f172a",
      font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky=W)
Label(content, text="Current conditions for your city", bg="#eef3f9", fg="#64748b",
      font=("Segoe UI", 10)).grid(row=1, column=0, sticky=W, pady=(0, 16))

search = Frame(content, bg="#eef3f9")
search.grid(row=2, column=0, sticky=EW, pady=(0, 18))
search.columnconfigure(0, weight=1)
city_entry = Entry(search, font=("Segoe UI", 12), relief=FLAT, bd=0, highlightthickness=1,
                  highlightbackground="#cbd5e1", highlightcolor="#60a5fa")
city_entry.grid(row=0, column=0, sticky=EW, ipady=8)
city_entry.bind("<Return>", lambda event: fetch_city_weather())
city_entry.focus_set()
search_button = Button(search, text="Search", command=fetch_city_weather, bg="#2563eb", fg="white",
                       activebackground="#1d4ed8", activeforeground="white", relief=FLAT,
                       padx=20, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
search_button.grid(row=0, column=1, padx=(10, 0))
location_button = Button(search, text="Use my location", command=use_my_location,
                         bg="#e2e8f0", fg="#0f172a", relief=FLAT,
                         padx=12, pady=5, font=("Segoe UI", 9), cursor="hand2")
location_button.grid(row=1, column=0, sticky=W, pady=(8, 0))

unit_selector = Frame(search, bg="#eef3f9")
unit_selector.grid(row=1, column=1, sticky=E, pady=(8, 0))
Radiobutton(unit_selector, text="°C", variable=temperature_unit, value="metric",
            command=refresh_for_selected_unit, bg="#eef3f9", fg="#334155",
            selectcolor="#eef3f9", activebackground="#eef3f9").pack(side=LEFT)
Radiobutton(unit_selector, text="°F", variable=temperature_unit, value="imperial",
            command=refresh_for_selected_unit, bg="#eef3f9", fg="#334155",
            selectcolor="#eef3f9", activebackground="#eef3f9").pack(side=LEFT, padx=(8, 0))

card = Frame(content, bg="white", padx=24, pady=20, highlightbackground="#dbe4ef", highlightthickness=1)
card.grid(row=3, column=0, sticky=EW)
card.columnconfigure(0, weight=1)
card.columnconfigure(1, weight=1)

lable_citi = Label(card, text="Search for a city", bg="white", fg="#0f172a", font=("Segoe UI", 18, "bold"))
lable_citi.grid(row=0, column=0, columnspan=2, sticky=W)
lable_country = Label(card, text="", bg="white", fg="#64748b", font=("Segoe UI", 10))
lable_country.grid(row=1, column=0, sticky=W)

clock_frame = Frame(card, bg="#f8fafc", padx=10, pady=7, highlightbackground="#e2e8f0", highlightthickness=1)
clock_frame.grid(row=1, column=1, sticky=E)
location_clock_value = Label(clock_frame, text="--:--:-- --", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 12, "bold"))
location_clock_value.pack(anchor=E)
location_clock_subtitle = Label(clock_frame, text="UTC+00:00", bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8))
location_clock_subtitle.pack(anchor=E)

lable_temp = Label(card, text="—°C", bg="white", fg="#0f172a", font=("Segoe UI", 44, "bold"))
lable_temp.grid(row=2, column=0, sticky=W, pady=(8, 0))
icon_label = Label(card, text="—", bg="white", fg="#64748b", font=("Segoe UI Emoji", 42))
icon_label.grid(row=2, column=1, sticky=E, pady=(8, 0))
condition_label = Label(card, text="Current conditions", bg="white", fg="#475569", font=("Segoe UI", 11))
condition_label.grid(row=3, column=0, columnspan=2, sticky=W, pady=(0, 14))


def detail_label(row, title):
    Label(card, text=title, bg="white", fg="#64748b", font=("Segoe UI", 10)).grid(
        row=row, column=0, sticky=W, pady=3
    )
    value = Label(card, text="—", bg="white", fg="#0f172a", font=("Segoe UI", 10, "bold"))
    value.grid(row=row, column=1, sticky=E, pady=3)
    return value


lable_humidity = detail_label(4, "Humidity")
max_temp = detail_label(5, "24-hour maximum")
min_temp = detail_label(6, "24-hour minimum")
lable_lat = detail_label(7, "Latitude")
lable_lon = detail_label(8, "Longitude")

forecast_title = Label(card, text="7-day forecast", bg="white", fg="#64748b", font=("Segoe UI", 10))
forecast_title.grid(row=9, column=0, columnspan=2, sticky=W, pady=(12, 3))
forecast_value = Label(card, text="—", justify=LEFT, anchor=W,
                       bg="white", fg="#0f172a", font=("Segoe UI", 10, "bold"), wraplength=520)
forecast_value.grid(row=10, column=0, columnspan=2, sticky=W)

hourly_title = Label(card, text="Today hourly forecast", bg="white", fg="#64748b", font=("Segoe UI", 10))
hourly_title.grid(row=11, column=0, columnspan=2, sticky=W, pady=(12, 3))
hourly_value = Label(card, text="—", justify=LEFT, anchor=W,
                     bg="white", fg="#0f172a", font=("Segoe UI", 10, "bold"), wraplength=520)
hourly_value.grid(row=12, column=0, columnspan=2, sticky=W)

Label(content, text="Weather data from AccuWeather · Unit toggle: °C / °F",
      bg="#eef3f9", fg="#64748b", font=("Segoe UI", 9), wraplength=520,
      justify=LEFT).grid(row=4, column=0, sticky=W, pady=(14, 0))

update_location_clock()

root.mainloop()
