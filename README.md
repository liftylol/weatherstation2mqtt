# 🌦️ weatherstation2mqtt (MQTT + Home Assistant)

A standalone "Man-in-the-Middle" bridge for Vevor / branded Weather Stations.

This script acts as a fake cloud server for your weather station. It intercepts the HTTP upload data, converts it to **Metric units**, displays it on a **Live Web Dashboard**, and forwards it to **MQTT** for instant **Home Assistant** integration.

![Dashboard Concept](https://img.shields.io/badge/Dashboard-Live_Web_UI-blue?style=for-the-badge) ![Home Assistant](https://img.shields.io/badge/Home_Assistant-Auto_Discovery-41bdf5?style=for-the-badge) ![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge)

## ✨ Features
* **🚀 Zero Config:** Just point your weather station DNS to this server.
* **🔌 Home Assistant Native:** Supports MQTT Auto-Discovery (sensors appear automatically).
* **📊 Live Dashboard:** Built-in web UI with real-time auto-updates.
* **🌍 Metric Conversion:** Automatically converts Imperial (F, mph, inHg) to Metric (°C, km/h, hPa).
* **⚙️ Web GUI:** Configure MQTT settings, passwords, and device names directly from your browser.
* **🐳 Docker Ready:** Runs easily on Raspberry Pi, Synology NAS, or any Linux server.

---

## 🛠️ Quick Start (Docker Compose)

The easiest way to run this is with Docker.

1.  **Save the script** as `weatherstation2mqtt.py`.
2.  Create a `docker-compose.yml` file in the same folder:

    ```yaml
    services:
      weather-bridge:
        image: python:3.11-slim
        container_name: weather-bridge
        restart: unless-stopped
        ports:
          - "80:80"
        volumes:
          - ./weatherstation2mqtt.py:/app/app.py
          - ./config.json:/app/config.json
        # Install dependencies on startup
        command: >
          sh -c "pip install paho-mqtt && python3 -u app.py"
    ```

3.  **Run it:**
    ```bash
    docker compose up -d
    ```

4.  **Open Dashboard:** Go to `http://<YOUR_SERVER_IP>` in your browser.

---

## 🐍 Manual Installation (Python)

If you prefer running it directly on Linux/macOS:

1.  **Install Dependencies:**
    ```bash
    pip3 install paho-mqtt
    ```

2.  **Run the Script:**
    *(Note: Sudo is required to listen on Port 80)*
    ```bash
    sudo python3 weatherstation2mqtt.py
    ```

---

## 📡 How to Connect Your Weather Station

To make your weather station talk to this script instead of the manufacturer's cloud, you need to use **DNS Spoofing** (DNS Rewrite).

1.  **Identify the Target Domain:** Check your DNS logs (Pi-hole/AdGuard) to see what domain your station contacts (e.g., `rtupdate.wunderground.com`).
2.  **Create a DNS Record:**
    * **Pi-hole:** Go to *Local DNS > DNS Records*. Map the domain to your server's IP.
    * **AdGuard Home:** Go to *Filters > DNS Rewrites*.
    * **Router:** Look for "Host Overrides" or "DNSmasq" settings.
3.  **Restart the Station:** It should now send data to your local server.

## ⚙️ Configuration
All settings (MQTT Broker, Topic, Credentials) are managed via the **Web UI**.

* **Settings File:** Configuration is saved to `config.json`.
* **Reset:** To reset settings, delete `config.json` and restart the container/script.

## ❤️ Contributing
Feel free to fork this project and submit PRs for other weather stations!
