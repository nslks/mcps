from mcp.server.fastmcp import FastMCP
import platform
import shutil

# Erstelle den Server
mcp = FastMCP("MyCustomTools")

@mcp.tool()
def get_system_usage() -> str:
    """Gibt den verfügbaren Festplattenplatz und Mac-Infos zurück."""
    total, used, free = shutil.disk_usage("/")
    gb = 1024**3
    return (f"Betriebssystem: {platform.system()} {platform.release()}\n"
            f"Speicherplatz: {free // gb} GB von {total // gb} GB verfügbar.")

if __name__ == "__main__":
    mcp.run()