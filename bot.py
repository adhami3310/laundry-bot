import os
import socket
import random
import time
import asyncio
import subprocess
import urllib.request, json
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.none()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
	print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
	if message.author == client.user:
		return

	if message.content.startswith("laundry, list"):
		with urllib.request.urlopen("http://laundry.mit.edu/watch") as url:
			data = json.loads(url.read().decode())
			laundry_status_mapping = {
				"ON": "Busy",
				"UNKNOWN": "Unknown",
				"OFF": "Free",
				"BROKEN": "Broken"
			}
			washers = [laundry_status_mapping[x] for x in data["washers"]["status"]]
			dryers = [laundry_status_mapping[x] for x in data["dryers"]["status"]]
			await message.channel.send('Washers: ' + ', '.join(washers) + '\n' + 'Dryers: ' + ', '.join(dryers))

client.run(TOKEN)
