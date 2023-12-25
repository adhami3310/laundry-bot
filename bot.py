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
from datetime import datetime

helpMessage = """Hello Randomites! I'm Quinn the Laundry Bot. I'm here to make your laundry managing easier! My prefixes are 'quinn', 'laundry', and '?'. Here's a list of my commands:
-Say 'laundry, [list/status]' to get the status of the laundry machines currently.
-Say 'laundry, show' to get a graphical representation of the status of the laundry machines currently.
-Say 'laundry, [notify/remind] group1 group2 ...' to get pinged for each group when the first machine in that group turns free.
Each group can be of the format: machine1,machine2,... where machine is [washers/dryerys/washerX/dryerX] using 1-indexing.
Note that you can use this command with machines that are currently free to use. It will just remind you whenever they become free again. This could be useful in case you know the machine is going to turn on soon.
-Say 'laundry, cancel' to cancel all your notifications.
-Say 'laundry, help' to get this message.
Let Adhami know if you discover any bugs or have any suggestions!"""


def timeToString(time):
    units = [
        (1, "m"),
        (60, "h"),
        (24, "d"),
        (7, "w"),
        (4, "m"),
        (12, "y"),
        (10, "d"),
        (100, "c"),
    ]
    last_unit = units[0][1]
    for size, unit in units:
        if time < size:
            break
        last_unit = unit
        time /= size
    time = int(time)
    if time == 0:
        return "Just Now"
    return f"{int(time)}{last_unit}"


subscribers = {
    ("washer", 0): set(),
    ("washer", 1): set(),
    ("washer", 2): set(),
    ("dryer", 0): set(),
    ("dryer", 1): set(),
    ("dryer", 2): set(),
    ("dryer", 3): set(),
}


def subscribe(channel, group):
    global subscribers
    for type, index in group:
        subscribers[(type, index)].add(channel)


def unsubscribe(channel, group):
    global subscribers
    for type, index in group:
        if channel in subscribers[(type, index)]:
            subscribers[(type, index)].remove(channel)


def getStatus():
    with urllib.request.urlopen("https://laundry.mit.edu/watch") as url:
        data = json.loads(url.read().decode())
        laundry_status_mapping = {
            "On": "Busy",
            "Uknown": "Unknown",
            "Off": "Free",
            "Broken": "Broken",
        }
        washerStatus = [
            laundry_status_mapping[x["power_status"]] for x in data["washers"]["status"]
        ]
        washerFor = [
            int(x["since_updated"] / 1000 / 60) for x in data["washers"]["status"]
        ]
        dryerStatus = [
            laundry_status_mapping[x["power_status"]] for x in data["dryers"]["status"]
        ]
        dryerFor = [
            int(x["since_updated"] / 1000 / 60) for x in data["dryers"]["status"]
        ]
        washers = [
            f"{x[0]} for {timeToString(x[1])}" if x[0] in {"Busy", "Free"} else x[0]
            for x in zip(washerStatus, washerFor)
        ]
        dryers = [
            f"{x[0]} for {timeToString(x[1])}" if x[0] in {"Busy", "Free"} else x[0]
            for x in zip(dryerStatus, dryerFor)
        ]
        return (washers, dryers)


washerLastStatus = ["UNKNOWN", "UNKNOWN", "UNKNOWN"]
dryerLastStatus = ["UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"]
lastUpdate = datetime.now()
channelWaiting = []


async def statusChanged(type, index):
    global channelWaiting
    print(f"{type}#{index} is now available!")
    newChannelWaiting = []
    for channel, author, machines in channelWaiting:
        if (type, index) in machines:
            await channel.send(f"{author.mention} {type}#{index+1} is free")
        else:
            newChannelWaiting.append((channel, author, machines))
    channelWaiting = newChannelWaiting


async def statusChangedAnything(type, index, newStatus):
    global subscribers
    print(f"{type}#{index} is now {newStatus}!")
    for channel in subscribers[(type, index)]:
        await channel.send(f"{type}#{index+1} is {newStatus}")


async def updateStatus():
    global washerLastStatus, dryerLastStatus, lastUpdate
    try:
        with urllib.request.urlopen("https://laundry.mit.edu/watch") as url:
            data = json.loads(url.read().decode())

            washerStatus = [x for x in data["washers"]["status"]]
            dryerStatus = [x for x in data["dryers"]["status"]]
            for i, (washerNow, washerBefore) in enumerate(
                zip(washerStatus, washerLastStatus)
            ):
                if washerNow != washerBefore:
                    await statusChangedAnything("washer", i, washerNow)
                if washerNow == "OFF" and washerBefore != "OFF":
                    await statusChanged("washer", i)
            for i, (dryerNow, dryerBefore) in enumerate(
                zip(dryerStatus, dryerLastStatus)
            ):
                if dryerNow != dryerBefore:
                    await statusChangedAnything("dryer", i, dryerNow)
                if dryerNow == "OFF" and dryerBefore != "OFF":
                    await statusChanged("dryer", i)
            washerLastStatus = washerStatus
            dryerLastStatus = dryerStatus
            lastUpdate = datetime.now()
    except:
        print("failed")
        pass


def split(s, delim):
    return list(filter(None, s.split(delim)))


def interpretMachines(machinesString):
    machines = set()
    for machine in machinesString:
        if machine == "washers":
            for i in range(3):
                machines.add(("washer", i))
        elif machine == "dryers":
            for i in range(4):
                machines.add(("dryer", i))
        elif machine.startswith("washer"):
            machines.add(("washer", int(machine[len("washer") :]) - 1))
        elif machine.startswith("dryer"):
            machines.add(("dryer", int(machine[len("dryer") :]) - 1))
    return list(machines)


def interpretRequest(machinesGroupsString):
    machinesGroups = list(
        filter(
            None,
            [
                interpretMachines(split(x, ","))
                for x in split(machinesGroupsString, " ")
            ],
        )
    )
    return machinesGroups


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.none()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")
    while True:
        await updateStatus()
        await asyncio.sleep(15)


@client.event
async def on_message(message):
    global channelWaiting
    if message.author == client.user:
        return

    content = message.content.lower()

    keywords = [
        "laundry ",
        "?",
        "? ",
        "laundry,",
        "laundry, ",
        "quinn ",
        "quinn,",
        "quinn, ",
    ]

    for key in keywords:
        if content.startswith(f"{key}list") or content.startswith(f"{key}status"):
            washers, dryers = getStatus()
            washers = [x.replace("Free", "**Free**") for x in washers]
            dryers = [x.replace("Free", "**Free**") for x in dryers]
            await message.channel.send(
                "Washers: " + ", ".join(washers) + "\n" + "Dryers: " + ", ".join(dryers)
            )
            break
        elif content.startswith(f"{key}notify") or content.startswith(f"{key}remind"):
            machinesGroups = interpretRequest(content[len(f"{key}notify") :])
            for machines in machinesGroups:
                channelWaiting.append((message.channel, message.author, machines))
            if len(machinesGroups) > 0:
                await message.channel.send(
                    f"will notify you for {' '.join(['{'+', '.join([y[0]+str(y[1]+1) for y in x])+'}' for x in machinesGroups])}!"
                )
            break
        elif content.startswith(f"{key}last"):
            current = datetime.now()
            await message.channel.send(
                f"last successful update was {(current-lastUpdate).total_seconds()} seconds ago"
            )
            break
        elif content.startswith(f"{key}cancel"):
            channelWaiting = [x for x in channelWaiting if x[1] != message.author]
            await message.channel.send("all notifications cancelled!")
            break
        elif content.startswith(f"{key}subscribe"):
            machinesGroups = interpretRequest(content[len(f"{key}subscribe") :])
            for machines in machinesGroups:
                subscribe(message.channel, machines)
            subscribed = []
            for machine, channels in subscribers.items():
                if message.channel in channels:
                    subscribed.append(f"{machine[0]}#{machine[1]+1}")
            if subscribed:
                await message.channel.send(
                    f"currently subscribed to {', '.join(subscribed)}"
                )
            else:
                await message.channel.send(f"currently subscribed to nothing!")
        elif content.startswith(f"{key}unsubscribe"):
            machinesGroups = interpretRequest(content[len(f"{key}unsubscribe") :])
            for machines in machinesGroups:
                unsubscribe(message.channel, machines)
            subscribed = []
            for machine, channels in subscribers.items():
                if message.channel in channels:
                    subscribed.append(f"{machine[0]}#{machine[1]+1}")
            if subscribed:
                await message.channel.send(
                    f"currently subscribed to {', '.join(subscribed)}"
                )
            else:
                await message.channel.send(f"currently subscribed to nothing!")

        elif content.startswith(f"{key}show"):
            emojis = {
                "Unknown": "<:laundry_unknown:1044357960740114592>",
                "Busy": "<:laundry_cross:1044357959876083722>",
                "Free": "<:laundry_check:1044358144291254352>",
                "Broken": "<:laundry_skull:1044357961553813705>",
                "Ozok": "<:laundry_ozok:1044360518430896198>",
            }
            endl = "\n"
            washers, dryers = getStatus()
            washers = [emojis[w.split(" ")[0]] for w in washers]
            dryers = [emojis[d.split(" ")[0]] for d in dryers]
            await message.channel.send(
                f"{emojis['Ozok']}{''.join(washers)}{endl}{endl.join(dryers)}"
            )
            break
        elif content.startswith(f"{key}help"):
            await message.channel.send(helpMessage)
            break


client.run(TOKEN)
