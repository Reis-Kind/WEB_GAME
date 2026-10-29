"""Gemini is selected by server config, not by the player."""
import asyncio
from provider_browser_check import run_provider
if __name__ == '__main__': asyncio.run(run_provider('gemini'))
