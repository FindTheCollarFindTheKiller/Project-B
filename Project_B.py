# piython3 -- Weather Application using API

# importing the libraries
from tkinter import *
from tkinter import messagebox
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
root.geometry("520x620")
root.minsize(420, 560)
root['background'] = "#f1f5f9"

BASE_DIR = Path(__file__).resolve().parent


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


def get_current_weather(location, api_key):
    location_key = quote(str(location["Key"]), safe="")
    observations = accuweather_get(
        "/currentconditions/v1/" + location_key,
        {"apikey": api_key, "details": "true"},
    )
    if not observations:
        raise ValueError("No current conditions available")
    return observations[0]


def show_weather(location, current):
    current_temperature = current["Temperature"]["Metric"]["Value"]
    conditions = current.get("WeatherText") or "Current conditions"
    humidity = current.get("RelativeHumidity")
    past_day = current.get("TemperatureSummary", {}).get("Past24Hour", {})
    tempmin = past_day.get("Minimum", {}).get("Metric", {}).get("Value")
    tempmax = past_day.get("Maximum", {}).get("Metric", {}).get("Value")
    coordinates = location["GeoPosition"]
    longitude = coordinates["Longitude"]
    latitude = coordinates["Latitude"]
    country = location["Country"]["LocalizedName"]
    city_result = location["LocalizedName"]

    lable_temp.configure(text=f"{current_temperature}°C")
    icon_label.configure(text=weather_icon(current.get("WeatherIcon")))
    condition_label.configure(text=conditions)
    lable_humidity.configure(text=f"{humidity}%" if humidity is not None else "N/A")
    max_temp.configure(text=f"{tempmax}°C" if tempmax is not None else "N/A")
    min_temp.configure(text=f"{tempmin}°C" if tempmin is not None else "N/A")
    lable_lon.configure(text=longitude)
    lable_lat.configure(text=latitude)
    lable_country.configure(text=country)
    lable_citi.configure(text=city_result)


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
        show_weather(location, current)
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
            results.put((location, current, None))
        except HTTPError as error:
            if error.code in (401, 403):
                message = "AccuWeather rejected the key or access to this endpoint."
            elif error.code == 429:
                message = "A request limit was reached. Try again later."
            else:
                message = "Location or weather service is unavailable. Try again later."
            results.put((None, None, message))
        except Exception:
            results.put((None, None, "Could not detect your location or retrieve weather. Try a city search."))

    def check_result():
        try:
            location, current, error = results.get_nowait()
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
            city_entry.delete(0, END)
            city_entry.insert(0, location["LocalizedName"])
        except (ValueError, KeyError, TypeError, IndexError):
            messagebox.showerror("Location lookup failed", "The weather service returned incomplete data.", parent=root)

    Thread(target=lookup, daemon=True).start()
    root.after(100, check_result)


content = Frame(root, bg="#f1f5f9", padx=24, pady=20)
content.pack(fill=BOTH, expand=True)
content.columnconfigure(0, weight=1)

Label(content, text="Weather", bg="#f1f5f9", fg="#0f172a",
      font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky=W)
Label(content, text="Current conditions for your city", bg="#f1f5f9", fg="#64748b",
      font=("Segoe UI", 10)).grid(row=1, column=0, sticky=W, pady=(0, 16))

search = Frame(content, bg="#f1f5f9")
search.grid(row=2, column=0, sticky=EW, pady=(0, 18))
search.columnconfigure(0, weight=1)
city_entry = Entry(search, font=("Segoe UI", 12), relief=SOLID, bd=1)
city_entry.grid(row=0, column=0, sticky=EW, ipady=7)
city_entry.bind("<Return>", lambda event: fetch_city_weather())
city_entry.focus_set()
search_button = Button(search, text="Search", command=fetch_city_weather, bg="#2563eb", fg="white",
                       activebackground="#1d4ed8", activeforeground="white", relief=FLAT,
                       padx=18, pady=6, font=("Segoe UI", 10, "bold"))
search_button.grid(row=0, column=1, padx=(10, 0))
location_button = Button(search, text="Use my location", command=use_my_location,
                         bg="#e2e8f0", fg="#0f172a", relief=FLAT,
                         padx=12, pady=4, font=("Segoe UI", 9))
location_button.grid(row=1, column=0, sticky=W, pady=(8, 0))

card = Frame(content, bg="white", padx=22, pady=18, highlightbackground="#e2e8f0", highlightthickness=1)
card.grid(row=3, column=0, sticky=EW)
card.columnconfigure(0, weight=1)
card.columnconfigure(1, weight=1)

lable_citi = Label(card, text="Search for a city", bg="white", fg="#0f172a", font=("Segoe UI", 18, "bold"))
lable_citi.grid(row=0, column=0, columnspan=2, sticky=W)
lable_country = Label(card, text="", bg="white", fg="#64748b", font=("Segoe UI", 10))
lable_country.grid(row=1, column=0, columnspan=2, sticky=W)
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

Label(content, text="Weather data from AccuWeather · Temperatures in Celsius",
      bg="#f1f5f9", fg="#64748b", font=("Segoe UI", 9)).grid(row=4, column=0, sticky=W, pady=(14, 0))


root.mainloop()
