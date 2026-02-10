from mcp.server.fastmcp import FastMCP
import shutil
import platform

mcp = FastMCP("Mein Server")

@mcp.tool()
async def say_hello() -> str:
    """Tell me a secret"""
    return f"Hier ist mein Geheimnis: Die Erde ist flach und die Mondlandung war fake!!11!"

@mcp.tool()
async def show_system_usage() -> str:
    total, used, free = shutil.disk_usage("/")
    gb = 1024**3
    return (f"Betriebssystem: {platform.system()} {platform.release()}\n"
            f"Speicherplatz: {free // gb} GB von {total // gb} GB verfügbar.")

if __name__ == "__main__":
    mcp.run()