import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import json
import os
import sys
import datetime
import paho.mqtt.client as mqtt

# --- GLOBAL CONFIGURATION & STATE ---
CONFIG_FILE = "config.json"

# Default Configuration
config = {
    "mqtt_broker": "192.168.1.100",
    "mqtt_port": 1883,
    "mqtt_user": "",
    "mqtt_pass": "",
    "mqtt_topic": "home/weatherstation/state",
    "device_name": "weatherstation2mqtt",
    "discovery_enabled": True
}

# Runtime storage for the last received data
latest_data = {
    "timestamp": "Waiting for data...",
    "values": {}
}

# --- HELPER FUNCTIONS ---
def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
            print(f"[*] Configuration loaded from {CONFIG_FILE}")
        except Exception as e:
            print(f"[!] Error loading config: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print(f"[*] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[!] Error saving config: {e}")

def degrees_to_cardinal(d):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((d / 22.5) + 0.5)
    return dirs[ix % 16]

# --- MQTT FUNCTIONS ---
def publish_mqtt(payload):
    if not config["mqtt_broker"]: return
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "WeatherBridge_Data")
        if config["mqtt_user"] and config["mqtt_pass"]:
            client.username_pw_set(config["mqtt_user"], config["mqtt_pass"])
        client.connect(config["mqtt_broker"], config["mqtt_port"], 60)
        client.publish(config["mqtt_topic"], json.dumps(payload), retain=True)
        client.disconnect()
        print(f" -> MQTT Data Sent: {payload}")
    except Exception as e:
        print(f" [!] MQTT Error: {e}")

def send_discovery():
    if not config["discovery_enabled"] or not config["mqtt_broker"]: return
    print("[*] Sending Home Assistant Auto-Discovery Configuration...")
    safe_id = config["device_name"].lower().replace(" ", "_")
    
    sensors = [
        ("temp", "temperature", "Temperature", "°C", "temperature"),
        ("hum", "humidity", "Humidity", "%", "humidity"),
        ("press", "pressure", "Pressure", "hPa", "pressure"),
        ("dew", "dew_point", "Dew Point", "°C", "temperature"),
        ("wind_s", "wind_speed", "Wind Speed", "km/h", "wind_speed"),
        ("wind_g", "wind_gust", "Wind Gust", "km/h", "wind_speed"),
        ("wind_d", "wind_bearing", "Wind Direction", "°", None),
        ("wind_txt", "wind_dir_cardinal", "Wind Direction (Text)", None, None),
        ("rain_r", "rain_rate", "Rain Rate", "mm/h", "precipitation_intensity"),
        ("rain_d", "rain_daily", "Rain Daily", "mm", "precipitation"),
        ("uv", "uv_index", "UV Index", None, None),
        ("solar", "solar_rad", "Solar Radiation", "W/m²", "irradiance"),
    ]

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "WeatherBridge_Config")
        if config["mqtt_user"] and config["mqtt_pass"]:
            client.username_pw_set(config["mqtt_user"], config["mqtt_pass"])
        client.connect(config["mqtt_broker"], config["mqtt_port"], 60)

        for suffix, json_key, name, unit, dev_class in sensors:
            topic = f"homeassistant/sensor/{safe_id}/{suffix}/config"
            payload = {
                "name": name,
                "unique_id": f"{safe_id}_{suffix}",
                "state_topic": config["mqtt_topic"],
                "value_template": f"{{{{ value_json.{json_key} }}}}",
                "device": {"identifiers": [safe_id], "name": config["device_name"], "model": "weatherstation2mqtt", "manufacturer": "liftylol"},
                "platform": "mqtt"
            }
            if unit: payload["unit_of_measurement"] = unit
            if dev_class: payload["device_class"] = dev_class
            client.publish(topic, json.dumps(payload), retain=True)
        client.disconnect()
        print("[*] Auto-Discovery Sent.")
    except Exception as e:
        print(f" [!] Discovery Error: {e}")

# --- HTML DASHBOARD (UPDATED) ---
def get_html_dashboard():
    sel_yes = "selected" if config["discovery_enabled"] else ""
    sel_no = "selected" if not config["discovery_enabled"] else ""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Weather Station Bridge</title>
        <style>
            :root {{ --primary: #2980b9; --bg: #f0f2f5; --card-bg: #ffffff; --text: #333; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; }}
            
            /* Typography & Layout */
            h2 {{ margin: 0; color: #2c3e50; font-size: 1.5em; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; padding-bottom: 10px; border-bottom: 2px solid var(--primary); }}
            
            /* New Sub-Header Row */
            .sub-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85em; color: #7f8c8d; margin-bottom: 20px; }}
            .api-status {{ display: flex; align-items: center; gap: 8px; }}
            
            /* Live Indicator Badge */
            #live-badge {{ width: 8px; height: 8px; background: #ccc; border-radius: 50%; display: inline-block; transition: background 0.3s, box-shadow 0.3s; }}
            .online #live-badge {{ background: #2ecc71; box-shadow: 0 0 6px #2ecc71; }}
            .offline #live-badge {{ background: #e74c3c; }}

            /* Cards */
            .card {{ background: var(--card-bg); padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 25px; transition: opacity 0.3s; }}
            .card.offline {{ opacity: 0.7; }}
            
            /* Data Grid */
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }}
            .stat-box {{ background: #ecf0f1; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-value {{ font-size: 1.4em; font-weight: 700; color: var(--primary); }}
            .stat-label {{ font-size: 0.9em; color: #7f8c8d; margin-top: 5px; }}
            
            /* Form & Buttons */
            form {{ display: flex; flex-direction: column; gap: 15px; }}
            input, select {{ padding: 10px; border: 1px solid #ddd; border-radius: 6px; width: 100%; box-sizing: border-box; }}
            label {{ font-weight: 600; font-size: 0.9em; }}
            
            .btn {{ padding: 12px; border: none; border-radius: 6px; cursor: pointer; color: white; font-size: 1em; font-weight: 600; width: 100%; }}
            .btn-save {{ background-color: #27ae60; }}
            .btn-restart {{ background-color: #c0392b; }}
            .btn-refresh {{ text-decoration: none; font-size: 1.2em; color: var(--primary); }}
        </style>
    </head>
    <body>
        <div class="container">
            
            <div class="card" id="data-card">
                <div class="card-header">
                    <h2>Live Weather Data</h2>
                    <a href="/" class="btn-refresh" title="Force Refresh">🔄</a>
                </div>
                
                <div class="sub-header">
                    <div class="api-status">
                        Live API Connected: <span id="live-badge"></span>
                    </div>
                    <div id="timestamp">Waiting for data...</div>
                </div>

                <div class="grid" id="data-grid">
                    <div style="grid-column:1/-1; text-align:center; padding:20px; color:#999;">Loading...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>⚙️ Configuration</h2>
                </div>
                <form action="/save" method="POST">
                    <label>MQTT Broker IP</label>
                    <input type="text" name="mqtt_broker" value="{config['mqtt_broker']}" required>

                    <div style="display: flex; gap: 15px;">
                        <div style="flex: 1;"><label>Port</label><input type="number" name="mqtt_port" value="{config['mqtt_port']}"></div>
                        <div style="flex: 2;"><label>Topic</label><input type="text" name="mqtt_topic" value="{config['mqtt_topic']}"></div>
                    </div>

                    <label>MQTT User / Pass (Optional)</label>
                    <div style="display: flex; gap: 15px;">
                        <input type="text" name="mqtt_user" value="{config['mqtt_user']}" placeholder="Username">
                        <input type="password" name="mqtt_pass" value="{config['mqtt_pass']}" placeholder="Password">
                    </div>

                    <label>Device Name (Home Assistant)</label>
                    <input type="text" name="device_name" value="{config['device_name']}">

                    <label>Auto-Discovery</label>
                    <select name="discovery_enabled">
                        <option value="true" {sel_yes}>Enabled</option>
                        <option value="false" {sel_no}>Disabled</option>
                    </select>

                    <button type="submit" class="btn btn-save">Save Settings</button>
                </form>
            </div>

            <div class="card" style="border-left: 5px solid #e74c3c;">
                <h3>System Control</h3>
                <p style="font-size: 0.9em; color: #555;">
                    Clicking "Restart" will terminate the script. 
                    If running in Docker (with <code>restart: unless-stopped</code>) or Systemd, it will reboot automatically. 
                    If running manually, the script will just stop.
                <form action="/restart" method="POST">
                    <button type="submit" class="btn btn-restart">Restart Service</button>
                </form>
            </div>
        </div>

        <script>
            function updateData() {{
                fetch('/api/live')
                    .then(response => {{
                        if (!response.ok) throw new Error("Network response was not ok");
                        return response.json();
                    }})
                    .then(data => {{
                        // Connection Successful
                        document.getElementById('data-card').classList.add('online');
                        document.getElementById('data-card').classList.remove('offline');
                        
                        // Update Timestamp
                        document.getElementById('timestamp').innerText = "Last Update: " + data.timestamp;
                        
                        // Update Grid
                        const grid = document.getElementById('data-grid');
                        grid.innerHTML = ""; 
                        
                        if (Object.keys(data.values).length === 0) {{
                            grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; color:#999;">Waiting for weather station...</div>';
                        }} else {{
                            Object.keys(data.values).sort().forEach(key => {{
                                const val = data.values[key];
                                grid.innerHTML += `
                                    <div class="stat-box">
                                        <div class="stat-value">${{val}}</div>
                                        <div class="stat-label">${{key}}</div>
                                    </div>`;
                            }});
                        }}
                    }})
                    .catch(error => {{
                        console.error('Error fetching data:', error);
                        // Connection Failed
                        document.getElementById('data-card').classList.remove('online');
                        document.getElementById('data-card').classList.add('offline');
                        document.getElementById('timestamp').innerText = "Connection Lost (Retrying...)";
                    }});
            }}

            updateData();
            setInterval(updateData, 2000);
        </script>
    </body>
    </html>
    """

# --- HTTP REQUEST HANDLER ---
class weatherstation2mqttHandler(http.server.BaseHTTPRequestHandler):
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        # 1. IoT Data Endpoint
        if parsed.path == "/weatherstation/updateweatherstation.php":
            self.handle_iot_data(parsed)
            
        # 2. Web Dashboard (Root)
        elif parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_html_dashboard().encode("utf-8"))

        # 3. NEW: JSON API for Auto-Update
        elif parsed.path == "/api/live":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(latest_data).encode("utf-8"))
            
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(length).decode('utf-8')
        
        if self.path == "/save":
            params = parse_qs(post_data)
            config["mqtt_broker"] = params.get("mqtt_broker", [""])[0]
            config["mqtt_port"] = int(params.get("mqtt_port", [1883])[0])
            config["mqtt_topic"] = params.get("mqtt_topic", [""])[0]
            config["mqtt_user"] = params.get("mqtt_user", [""])[0]
            config["mqtt_pass"] = params.get("mqtt_pass", [""])[0]
            config["device_name"] = params.get("device_name", [""])[0]
            disc_val = params.get("discovery_enabled", ["false"])[0]
            config["discovery_enabled"] = (disc_val == "true")
            
            save_config()
            if config["discovery_enabled"]: send_discovery()
            self.redirect("/")

        elif self.path == "/restart":
            self.redirect("/")
            self.wfile.flush()
            sys.exit(1)
        else:
            self.send_error(404)

    def redirect(self, loc):
        self.send_response(303)
        self.send_header("Location", loc)
        self.end_headers()

    def handle_iot_data(self, parsed):
        q = parse_qs(parsed.query)
        payload = {}
        disp = {}

        # Conversion Map
        param_map = {
            'tempf':        ('temperature',   lambda x: (x - 32) * 5/9, '°C'),
            'dewptf':       ('dew_point',     lambda x: (x - 32) * 5/9, '°C'),
            'baromin':      ('pressure',      lambda x: x * 33.8639, 'hPa'),
            'windspeedmph': ('wind_speed',    lambda x: x * 1.60934, 'km/h'),
            'windgustmph':  ('wind_gust',     lambda x: x * 1.60934, 'km/h'),
            'rainin':       ('rain_rate',     lambda x: x * 25.4, 'mm/h'),
            'dailyrainin':  ('rain_daily',    lambda x: x * 25.4, 'mm'),
            'humidity':     ('humidity',      None, '%'),
            'UV':           ('uv_index',      None, ''),
            'solarRadiation': ('solar_rad',   None, 'W/m²')
        }

        for k, v_list in q.items():
            if k in param_map:
                key, fn, unit = param_map[k]
                try:
                    val = float(v_list[0])
                    if fn: val = round(fn(val), 2)
                    payload[key] = val
                    disp[key.replace("_", " ").title()] = f"{val} {unit}"
                except: pass

        if 'winddir' in q:
            try:
                deg = float(q['winddir'][0])
                cardinal = degrees_to_cardinal(deg)
                payload['wind_bearing'] = deg
                payload['wind_dir_cardinal'] = cardinal
                disp['Wind Direction'] = f"{cardinal} ({int(deg)}°)"
            except: pass

        # Update State
        latest_data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latest_data["values"] = disp
        
        # Publish & Reply
        print(f"[+] Received Weather Data. Processing...")
        publish_mqtt(payload)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"SUCCESS")

# --- MAIN ---
if __name__ == "__main__":
    load_config()
    if config["discovery_enabled"]: send_discovery()
    print(f"[*] Starting weatherstation2mqtt on Port 80...")
    server = http.server.HTTPServer(("0.0.0.0", 80), weatherstation2mqttHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()