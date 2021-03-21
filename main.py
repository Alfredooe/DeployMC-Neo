import discord
from discord.ext import commands
from discord.ext import menus
from coolname import generate_slug
import docker
import socket
import mcstatus
import logging
import time
import threading

bot = commands.Bot(command_prefix='/')
client = docker.from_env()
logging.basicConfig(filename='example.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S')

def get_free_tcp_port():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    
    tcp.bind(('', 0))
    addr, port = tcp.getsockname()
    tcp.close()
    logging.info(f"PORT {port} PICKED")
    return port

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    game = discord.Game("/minecraft")
    await bot.change_presence(status=discord.Status.online, activity=game)

def watch_dog():
    running_instances = {}
    logging.info("WATCHDOG INITIALIZED")
    while True:
        time.sleep(60)
        containers = client.containers.list()
        for i in containers:
            container_name = i.name

            try:
                query_info = instancehandler.query_container(i)
                players = query_info["players"]["online"]
            except:
                break

            if container_name not in running_instances:
                running_instances[container_name] = 0

            if players > 0:
                running_instances[container_name] = 0

            elif players == 0:
                inactive_time = running_instances[container_name]
                inactive_time += 1
                running_instances[container_name] = inactive_time
                if inactive_time > 15:
                    instancehandler.stop_container(i)
                    logging.info(f"INSTANCE {container_name} AUTO-STOP")
                    running_instances[container_name] = 0
        logging.info(f"RUNNING INSTANCES: {running_instances}")
        
class InstanceHandler:

    def create_container(self, owneruuid, version, username):
        port = get_free_tcp_port()
        dockerlabels = {"port": str(port), "version": str(version)}
        portlist={"25565/tcp":port}
        logging.info(f"UUID: {owneruuid} USERNAME: {username} CREATED A {version} INSTANCE")
        mc_name = f"{username}'s Instance. Powered by DeployMC!"
        environment={"MEMORY": "2048M", "TYPE": "PAPER", "VERSION": version, "EULA": "TRUE", "OPS": username, "MOTD": mc_name, "ENABLE_AUTOPAUSE": "TRUE", "AUTOPAUSE_TIMEOUT_EST": "60", "AUTOPAUSE_TIMEOUT_INIT": "60"}
        container = client.containers.run('itzg/minecraft-server', command="--noconsole", ports=portlist, name=owneruuid, 
            detach=True, environment=environment, labels=dockerlabels)

    def get_container(self, owneruuid):
        logging.info(f"GETTING CONTAINER {owneruuid}")
        try:
            container = client.containers.get(str(owneruuid))
        except docker.errors.NotFound:
            logging.info(f"FAILED TO GET CONTAINER {owneruuid}")
            return False
        else:
            return(container)

    def stop_container(self, container):
        logging.info(f"STOPPING CONTAINER {container.name}")
        container.stop()
        logging.info(f"STOPPED CONTAINER {container.name}")
    
    def start_container(self, container):
        logging.info(f"STARTING CONTAINER {container.name}")
        container.start()
        logging.info(f"STARTED CONTAINER {container.name}")

    def delete_container(self, container):
        logging.warning(f"DELETING CONTAINER {container.name}")
        container.stop()
        container.remove()
        logging.warning(f"DELETED CONTAINER {container.name}")

    def query_container(self, container):
        logging.info(f"QUERYING CONTAINER {container.name}")
        labels = container.labels
        port = labels.get("port")
        status = container.status
        full_stats = container.stats(stream=False)
        if status != "running":
            return {
                "status": status,
                "port": port,
            }
        try:
            minecraft_status = mcstatus.MinecraftServer("localhost", int(port)).status()
        except:
            return {
                "status": "starting",
                "port": port,
            }
            logging.info(f"FAILED TO MCSTATUS {container.name}")
        return {
            "port": port,
            "status": status,
            "version": labels.get("version"),
            "players": {"online": minecraft_status.players.online,
                      "max": minecraft_status.players.max},
            "description": minecraft_status.description,
            "ram_usage": full_stats["memory_stats"]["usage"],
        }

class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=30.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        embed = discord.Embed(title = f":tools: {self.msg}", color=0x595959)
        return await channel.send(embed=embed)

    @menus.button('✅')
    async def do_confirm(self, payload):
        await waitmessage(self.ctx)
        self.result = True
        self.stop()

    @menus.button('❌')
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class NewInstance(menus.Menu):
    async def send_initial_message(self, ctx, channel):
        def check(reply):
            return reply.channel == channel and reply.author == ctx.author
        embed = discord.Embed(title = ":tools: New Instance.", description = f"Greetings, What is your **minecraft username?** I require this for giving you OP.", color=0x595959)
        await channel.send(embed=embed)
        returned = await bot.wait_for('message', check=check)
        self.mc_username = returned.content
        embed = discord.Embed(title = ":tools: New Instance.", description = f"Greetings, {self.mc_username}. It appears you do not have an existing instance. Would you like to create one?\n1️⃣ 1.16.5\n2️⃣ 1.12.2\n⏹️ Cancel", color=0x595959)
        return await channel.send(embed=embed)

    @menus.button('1️⃣')
    async def on_keycap_digit_one(self, payload):
        instancehandler.create_container(self.ctx.author.id, "1.16.5", self.mc_username)
        await waitmessage(self.ctx)
        await self.message.delete()
 
    @menus.button('2️⃣')
    async def on_keycap_digit_two(self, payload):
        instancehandler.create_container(self.ctx.author.id, "1.12.2")
        await waitmessage(self.ctx)
        await self.message.delete()

    @menus.button('⏹️')
    async def on_stop(self, payload):
        await self.message.delete()

class MainMenu(menus.Menu):
    async def send_initial_message(self, ctx, channel):
        container = instancehandler.get_container(self.ctx.author.id)
        jsonData = instancehandler.query_container(container)
        port = jsonData["port"]
        if jsonData["status"] == "running":
            status = jsonData["status"]
            ramusage = str(round(jsonData["ram_usage"]/1000000))+"MB / 2048MB"
            description = jsonData["description"]["text"]
            players = jsonData["players"]["online"]
            version = jsonData["version"]
        else:
            status = "STOPPED"
            ramusage = "N/A"
            description = "N/A"
            players = "N/A"
            version = "N/A"

        embed=discord.Embed(title="DeployMC Toolbox")
        embed.add_field(name="Server Status", value=f"```STATUS: {status}\nIP: 192.168.1.25:{port}\nPLAYERS: {players}\nVERSION: {version}\nDESC: {description}\nRAM: {ramusage}```", inline=True)
        embed.add_field(name="Commands", value="What would you like to do?\n:arrow_forward: Start server \n:stop_button: Stop server \n"+
	        ":heart_decoration:Check status of server \n:wastebasket:Delete server", inline=True)
        embed.set_footer(text="Your instance will also stop after 15 minutes of inactivity.\nCurrently in alpha! Concerns or feedback? Please contact Alfredo#0974.")

        return await channel.send(embed=embed)

    @menus.button('▶️')
    async def on_play_button(self, payload):
        confirm = await Confirm('Start instance?').prompt(self.ctx)
        if confirm:
            container = instancehandler.get_container(self.ctx.author.id)
            instancehandler.start_container(container)
            await self.message.delete()

    @menus.button('⏹️')
    async def on_stop_button(self, payload):
        confirm = await Confirm('Stop instance?').prompt(self.ctx)
        if confirm:
            container = instancehandler.get_container(self.ctx.author.id)
            instancehandler.stop_container(container)
            await self.message.delete()

    @menus.button('💟')
    async def on_query(self, payload):
        confirm = await Confirm('Query instance?').prompt(self.ctx)
        if confirm:
            print(instancehandler.query_container(self.ctx.author.id))
            await self.message.delete()

    @menus.button('🗑️')
    async def on_trash_can(self, payload):
        confirm = await Confirm('Delete instance?').prompt(self.ctx)
        if confirm:
            container = instancehandler.get_container(self.ctx.author.id)
            instancehandler.delete_container(container)
            await self.message.delete()

@bot.command()
async def minecraft(ctx):
    if instancehandler.get_container(ctx.author.id) == False:
        m = NewInstance()
        await m.start(ctx)
    else:
        m = MainMenu()
        await m.start(ctx)

@bot.command()
async def waitmessage(ctx):
    embed = discord.Embed(title = f":tools: Please allow 30 seconds for this operation, this is only running on an E3-1220 V3 :(")
    await ctx.send(embed=embed)

instancehandler = InstanceHandler()
watchdog_thread = threading.Thread(target=watch_dog).start()

logging.info("STARTED")
bot.run('', bot=True)
