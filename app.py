import os
import sys
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify

# --- CONFIGURE LOGGING ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def get_coordinates(village_name):
    """Get coordinates using OpenStreetMap Nominatim API"""
    try:
        search_query = f"{village_name}, Telangana, India"
       #logger.debug(f"🔍 Contacting OpenStreetMap for location query: '{search_query}'")
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": search_query, "format": "json", "limit": 1}
        headers = {"User-Agent": "warangal-weatherman-bot"}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if not data:
            logger.warning(f"❌ Location '{village_name}' not found in Telangana.")
            return None, None, None
        
        place = data[0]
        latitude = float(place["lat"])
        longitude = float(place["lon"])
        display_name = place["display_name"]
        
        #logger.info(f"📍 Location resolved: {display_name} -> ({latitude}, {longitude})")
        return latitude, longitude, display_name
    except Exception as e:
        logger.error(f"⚠️ Error getting coordinates from OSM: {e}")
        return None, None, None


def get_weather_back(latitude, longitude, location):
    """Fetch weather using Open-Meteo ECMWF model"""
    try:

        weather_url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": latitude,
            "longitude": longitude,

            # Force ECMWF model
            "models": "ecmwf_ifs025",

            "current": "temperature_2m,wind_speed_10m",

            "hourly": (
                "temperature_2m,"
                "precipitation_probability,"
                "precipitation,"
                "cloud_cover"
            ),

            "forecast_days": 2,
            "timezone": "Asia/Kolkata"
        }

        response = requests.get(
            weather_url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        # -------------------------
        # Current Weather
        # -------------------------

        current = data["current"]

        current_temp = current["temperature_2m"]
        wind_speed = current["wind_speed_10m"]

        weather_time = current["time"]

        current_dt = datetime.fromisoformat(weather_time)

        formatted_time = current_dt.strftime(
            "%Y-%m-%d %I:%M %p IST"
        )

        # -------------------------
        # Hourly Forecast
        # -------------------------

        hourly_times = data["hourly"]["time"]
        hourly_temps = data["hourly"]["temperature_2m"]

        hourly_rain_prob = data["hourly"]["precipitation_probability"]

        hourly_rain_mm = data["hourly"]["precipitation"]

        hourly_cloud = data["hourly"]["cloud_cover"]

        forecast_lines = []

        for i in range(len(hourly_times)):

            forecast_dt = datetime.fromisoformat(
                hourly_times[i]
            )

            if forecast_dt <= current_dt:
                continue

            forecast_time = forecast_dt.strftime(
                "%I:%M %p"
            )

            temp = hourly_temps[i]

            rain_prob = hourly_rain_prob[i]

            rain_mm = hourly_rain_mm[i]

            cloud = hourly_cloud[i]

            # Better rain logic
            if rain_mm >= 10:
                rain_status = "Heavy Rain 🌧"
            elif rain_mm >= 5:
                rain_status = "Moderate Rain ⛈️"
            elif rain_mm >= 1:
                rain_status = "Light Rain 🌦"
            elif rain_prob >= 60:
                rain_status = "Rain Possible ☁️"
            elif cloud >= 70:
                rain_status = "Cloudy 🌥"
            else:
                rain_status = "Dry ☀️"

            forecast_lines.append(
                f"{forecast_time}: "
                f"{temp}°C | "
                f"{rain_mm} mm | "
                f"{rain_status}"
            )

            if len(forecast_lines) >= 12:
                break

        forecast_text = "\n".join(forecast_lines)

        weather_report = f"""
===========================
⛈️ WARANGAL WEATHERMAN ⛈️
===========================
📍Village/City: {location}
━━━━━━━━━━━━━━━━━━━━━━
🕒 Time: {formatted_time}
🌡 Current Temp: {current_temp}°C
💨 Wind Speed: {wind_speed} km/h
🌍 Model: ECMWF IFS
===========================
⏳ Next 12 Hours Forecast
===========================
{forecast_text}
"""

        return weather_report.strip()

    except Exception as e:
        logger.error(
            f"💥 ECMWF fetch failed: {e}",
            exc_info=True
        )

        return f"⚠️ Error fetching weather data: {str(e)}"


# Flask Web Infrastructure
app = Flask(__name__)


@app.route("/")
def home():
    logger.debug("❤️ Health check ping received...")
    return "Warangal Weather API Running", 200


@app.route("/weather/<village>")
def weather(village):
    """Fetch weather data for a village and return as JSON"""
    logger.info(f"📍 Weather request for: {village}")
    
    try:
        latitude, longitude, location = get_coordinates(village)
        
        if not latitude or not longitude:
            logger.warning(f"❌ Location not found: {village}")
            return jsonify({"error": "Location not found"}), 404
        
        report = get_weather_back(latitude, longitude, location)
        
        logger.info(f"✅ Weather report generated for {location}")
        
        return jsonify({
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "report": report
        }), 200
        
    except Exception as e:
        logger.error(f"💥 Error processing weather request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Launching server instance on port {port}...")
    app.run(host="0.0.0.0", port=port)
