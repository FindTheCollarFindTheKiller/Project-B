# python3 -- Weather Application using API

# importing the libraries
from tkinter import *
import json
import datetime
import os
from pathlib import Path
from urllib.request import urlopen
from PIL import ImageTk, Image

try:
    import requests
except ModuleNotFoundError:
    class RequestsCompat:
        @staticmethod
        def get(url, timeout=10):
            class Response:
                def __init__(self, content):
                    self.content = content

            with urlopen(url, timeout=timeout) as response:
                return Response(response.read())

    requests = RequestsCompat()


# necessary details
root = Tk()
root.title("Weather App")
root.geometry("450x700")
root['background'] = "white"

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR_CANDIDATES = [BASE_DIR, BASE_DIR / "assets", BASE_DIR / "images"]
API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()


def resolve_image_path(filename):
    for directory in IMAGE_DIR_CANDIDATES:
        image_path = directory / filename
        if image_path.exists():
            return image_path

    matches = list(BASE_DIR.rglob(filename))
    if matches:
        return matches[0]

    return None


def add_image_or_fallback(parent, filename, fallback_text, x, y, font=("Segoe UI Emoji", 18), anchor=NW):
    image_path = resolve_image_path(filename)
    if image_path is not None:
        photo = ImageTk.PhotoImage(Image.open(image_path))
        label = Label(parent, image=photo, bg='white')
        label.image = photo
    else:
        print(f"Warning: image file not found: {filename}")
        label = Label(parent, text=fallback_text, bg='white', fg='black', font=font)

    label.place(x=x, y=y, anchor=anchor)
    return label


# Image
logo_panel = add_image_or_fallback(
    root,
    'logo.png',
    '🌦️ Weather App',
    x=10,
    y=545,
    font=("Segoe UI Emoji", 16, "bold")
)


# Dates
dt = datetime.datetime.now()
date = Label(root, text=dt.strftime('%A--'), bg='white', font=("bold", 15))
date.place(x=5, y=130)
month = Label(root, text=dt.strftime('%m %B'), bg='white', font=("bold", 15))
month.place(x=100, y=130)

# Time
hour = Label(root, text=dt.strftime('%I : %M %p'),
             bg='white', font=("bold", 15))
hour.place(x=10, y=160)

# Theme for the respective time the application is used
if int((dt.strftime('%I'))) >= 8 & int((dt.strftime('%I'))) <= 5:
    theme_panel = add_image_or_fallback(
        root,
        'moon.png',
        '🌙',
        x=210,
        y=200,
        font=("Segoe UI Emoji", 36)
    )
else:
    theme_panel = add_image_or_fallback(
        root,
        'sun.png',
        '☀️',
        x=210,
        y=200,
        font=("Segoe UI Emoji", 36)
    )


# City Search
city_name_var = StringVar()
city_entry = Entry(root, textvariable=city_name_var, width=45)
city_entry.grid(row=1, column=0, ipady=10, stick=W+E+N+S)


def fetch_city_weather():

    if not API_KEY:
        lable_citi.configure(text="API key missing")
        lable_country.configure(text="Set OPENWEATHER_API_KEY")
        return

    # API Call
    api_request = requests.get(
        "https://api.openweathermap.org/data/2.5/weather?q="
        + city_entry.get()
        + "&units=metric&appid="
        + API_KEY
    )

    api = json.loads(api_request.content)

    if str(api.get("cod")) != "200":
        lable_citi.configure(text="Lookup failed")
        lable_country.configure(text=api.get("message", "Invalid city or API key"))
        return

    # Temperatures
    y = api['main']
    current_temprature = y['temp']
    humidity = y['humidity']
    tempmin = y['temp_min']
    tempmax = y['temp_max']

    # Coordinates
    x = api['coord']
    longtitude = x['lon']
    latitude = x['lat']

    # Country
    z = api['sys']
    country = z['country']
    citi = api['name']

    # Adding the received info into the screen
    lable_temp.configure(text=current_temprature)
    lable_humidity.configure(text=humidity)
    max_temp.configure(text=tempmax)
    min_temp.configure(text=tempmin)
    lable_lon.configure(text=longtitude)
    lable_lat.configure(text=latitude)
    lable_country.configure(text=country)
    lable_citi.configure(text=citi)


# Search Bar and Button
city_nameButton = Button(root, text="Search", command=fetch_city_weather)
city_nameButton.grid(row=1, column=1, padx=5, stick=W+E+N+S)


# Country  Names and Coordinates
lable_citi = Label(root, text="...", width=0, 
                   bg='white', font=("bold", 15))
lable_citi.place(x=10, y=63)

lable_country = Label(root, text="...", width=0, 
                      bg='white', font=("bold", 15))
lable_country.place(x=135, y=63)

lable_lon = Label(root, text="...", width=0,
                  bg='white', font=("Helvetica", 15))
lable_lon.place(x=25, y=95)
lable_lat = Label(root, text="...", width=0,
                  bg='white', font=("Helvetica", 15))
lable_lat.place(x=95, y=95)

# Current Temperature

lable_temp = Label(root, text="...", width=0, bg='white',
                   font=("Helvetica", 110), fg='black')
lable_temp.place(x=18, y=220)

# Other temperature details

humi = Label(root, text="Humidity: ", width=0, 
             bg='white', font=("bold", 15))
humi.place(x=3, y=400)

lable_humidity = Label(root, text="...", width=0,
                       bg='white', font=("bold", 15))
lable_humidity.place(x=107, y=400)


maxi = Label(root, text="Max. Temp.: ", width=0, 
             bg='white', font=("bold", 15))
maxi.place(x=3, y=430)

max_temp = Label(root, text="...", width=0, 
                 bg='white', font=("bold", 15))
max_temp.place(x=128, y=430)


mini = Label(root, text="Min. Temp.: ", width=0, 
             bg='white', font=("bold", 15))
mini.place(x=3, y=460)

min_temp = Label(root, text="...", width=0, 
                 bg='white', font=("bold", 15))
min_temp.place(x=128, y=460)


# Note
note = Label(root, text="All temperatures in degree celsius",
             bg='white', font=("italic", 10))
note.place(x=95, y=495)


root.mainloop()