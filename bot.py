from dotenv import load_dotenv
import os
import socket
import random
import time
import asyncio
import subprocess
import urllib.request
import json
import discord


def timeToString(time):
    if time < 60:
        return f'{time}m'
    if time < 60*24:
        return f'{int(time/60)}h'
    return f'{int(time/60/24)}'


def getStatus():
    with urllib.request.urlopen("https://laundry.mit.edu/watch") as url:
        data = json.loads(url.read().decode())
        laundry_status_mapping = {
            "ON": "Busy",
            "UNKNOWN": "Unknown",
            "OFF": "Free",
            "BROKEN": "Broken"
        }
        washerStatus = [laundry_status_mapping[x]
                        for x in data["washers"]["status"]]
        washerFor = [int(x/1000/60)
                     for x in data["washers"]["sinceTransition"]]
        dryerStatus = [laundry_status_mapping[x]
                       for x in data["dryers"]["status"]]
        dryerFor = [int(x/1000/60) for x in data["dryers"]["sinceTransition"]]
        washers = [f'{x[0]} for {timeToString(x[1])}' if x[0] in {
            "Busy", "Free"} else x[0] for x in zip(washerStatus, washerFor)]
        dryers = [f'{x[0]} for {timeToString(x[1])}' if x[0] in {
            "Busy", "Free"} else x[0] for x in zip(dryerStatus, dryerFor)]
        return (washers, dryers)


washerLastStatus = ["UNKNOWN", "UNKNOWN", "UNKNOWN"]
dryerLastStatus = ["UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"]

channelWaiting = []


async def statusChanged(type, index):
    global channelWaiting
    newChannelWaiting = []
    for (channel, author, machines) in channelWaiting:
        if (type, index) in machines:
            await channel.send(f'{author.mention} {type}#{index+1} is free')
        else:
            newChannelWaiting.append((channel, author, machines))
    channelWaiting = newChannelWaiting


async def updateStatus():
    global washerLastStatus, dryerLastStatus
    try: 
        with urllib.request.urlopen("https://laundry.mit.edu/watch") as url:
            data = json.loads(url.read().decode())

            washerStatus = [x
                            for x in data["washers"]["status"]]
            dryerStatus = [x
                        for x in data["dryers"]["status"]]
            for i, (washerNow, washerBefore) in enumerate(zip(washerStatus, washerLastStatus)):
                if washerNow == "OFF" and washerBefore != "OFF":
                    await statusChanged("washer", i)
            for i, (dryerNow, dryerBefore) in enumerate(zip(dryerStatus, dryerLastStatus)):
                if dryerNow == "OFF" and dryerBefore != "OFF":
                    await statusChanged("dryer", i)
            washerLastStatus = washerStatus
            dryerLastStatus = dryerStatus
    except:
        pass
    await asyncio.sleep(5)
    await updateStatus()


def split(s, delim):
    return list(filter(None, s.split(delim)))


def interpretMachines(machinesString):
    machines = set()
    for machine in machinesString:
        if machine == "washers":
            for i in range(3):
                machines.add(('washer', i))
        elif machine == "dryers":
            for i in range(4):
                machines.add(('dryer', i))
        elif machine.startswith("washer"):
            machines.add(('washer', int(machine[len('washer'):])-1))
        elif machine.startswith("dryer"):
            machines.add(('dryer', int(machine[len('dryer'):])-1))
    return list(machines)


def interpretRequest(machinesGroupsString):
    machinesGroups = list(filter(None, [interpretMachines(
        split(x, ",")) for x in split(machinesGroupsString, " ")]))
    return machinesGroups


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.none()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    await updateStatus()
    print(f'{client.user} has connected to Discord!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("laundry, list"):
        washers, dryers = getStatus()
        washers = [x.replace("Free", "**Free**") for x in washers]
        dryers = [x.replace("Free", "**Free**") for x in dryers]
        await message.channel.send('Washers: ' + ', '.join(washers) + '\n' + 'Dryers: ' + ', '.join(dryers))
    elif message.content.startswith("laundry, notify"):
        machinesGroups = interpretRequest(
            message.content[len("laundry, notify"):])
        for machines in machinesGroups:
            channelWaiting.append((message.channel, message.author, machines))
        if len(machinesGroups) > 0:
            await message.channel.send(f"will notify you for {' '.join(['{'+', '.join([y[0]+str(y[1]+1) for y in x])+'}' for x in machinesGroups])}!")

client.run(TOKEN)
