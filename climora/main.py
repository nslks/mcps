from mcp.server.fastmcp import FastMCP
import requests
import docker
import json

# Initialisierung des Climora Hubs
mcp = FastMCP("Climora-System-Control")
docker_client = docker.from_env()

# --- 1. SENSOR-SCHNITTSTELLE (API) ---
@mcp.tool()
def get_sensor_data():
    """Abfrage der aktuellen Arduino-Werte (Temp/Feuchtigkeit) aus der App."""
    try:
        # Ersetze localhost durch den Container-Namen, falls im selben Docker-Netz
        response = requests.get("http://localhost:8004/measurement/latest", timeout=2)
        return response.json()
    except Exception as e:
        return f"Sensor-Fehler: {str(e)}"

# --- 2. KI-ZU-KI INTERAKTION (Ollama) ---
@mcp.tool()
def ask_local_ollama(prompt: str):
    """Nutzt das lokale Ollama-Modell für eine private Datenanalyse."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False}
        )
        return response.json().get("response", "Keine Antwort von Ollama.")
    except Exception as e:
        return f"Ollama-Verbindungsfehler: {str(e)}"

# --- 3. DOCKER-ÜBERWACHUNG (DevOps) ---
@mcp.tool()
def get_climora_container_status():
    """Prüft den Zustand aller Climora-zugehörigen Container."""
    try:
        containers = docker_client.containers.list(all=True)
        status_list = [
            {"name": c.name, "status": c.status, "image": c.image.tags}
            for c in containers if "climora" in c.name.lower()
        ]
        return json.dumps(status_list, indent=2)
    except Exception as e:
        return f"Docker-Fehler: {str(e)}"

if __name__ == "__main__":
    mcp.run()