import discord
from discord.ext import commands
from coolname import generate_slug
import docker
import socket
import uuid

bot = commands.Bot(command_prefix='/')
client = docker.from_env()
instances = []
reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣']
confirmreactions =['✅', '❌']

def get_free_tcp_port():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(('', 0))
    addr, port = tcp.getsockname()
    tcp.close()
    return port

def get_instance(owner):
    for i in instances:
        if i.owneruuid == owner:
            return i
    return False

class Instance:
    def __init__(self, owner, jartype, version):

        self.owneruuid = owner
        self.jartype = jartype
        self.version = version
        self.coolname = None
        self.container = None
        self.running = None
        self.port = None
        self.ip = "IP HERE"

    def initialize(self):
        print(f"{self.owneruuid} CREATED.")
        self.port = get_free_tcp_port()
        portlist={"25565/tcp":self.port}
        environment={"MEMORY": "2048M", "TYPE": self.jartype, "VERSION": self.version, "EULA": "TRUE"}
        self.coolname = generate_slug(3)
        self.container = client.containers.run('itzg/minecraft-server', command="--noconsole", ports=portlist, name=self.owneruuid, 
            detach=True, environment=environment)

    def decommission(self):
        print(f"{self.owneruuid} DELETED.")
        self.container.remove(force=True)

    def start(self):
        print(f"{self.owneruuid} STARTED.")
        self.container.start()

    def stop(self):
        print(f"{self.owneruuid} STOPPED.")
        self.container.stop()

    def get_info(self):
        print(f"{self.owneruuid} QUERIED.")

    def get_container(self):
        print(f"{self.owneruuid} GOT CONTAINER.")
        self.container = client.get(self.owneruuid)

def create_instance(owner, jartype, version):
    instance = Instance(owner, "PAPER", version)
    instances.append(instance)
    instance.initialize()
    return instance

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    game = discord.Game("/minecraft")
    await bot.change_presence(status=discord.Status.online, activity=game)

@bot.command()
async def instancecreator(ctx):
    if get_instance(ctx.author.id) != False:
        return

    embed = discord.Embed(title = ":tools: New Instance.", description = f"Greetings, {ctx.author.name}. It appears you do not have an existing instance. Would you like to create one?\n1️⃣ 1.16.5\n2️⃣ 1.12.2\n:x: Cancel", color=0x595959)
    message = await ctx.send(embed=embed)
    for i in range(2):
        await message.add_reaction(reactions[i])
    await message.add_reaction('❌')
    @bot.event
    async def on_reaction_add(reaction, user):
        if user.id == ctx.message.author.id:
            if reaction.emoji == "1️⃣":
                #await message.delete()
                instance = create_instance(ctx.author.id, "PAPER", "1.16.5")
                await initmessage(ctx, instance)
            if reaction.emoji == "2️⃣":
                #await message.delete()
                instance = create_instance(ctx.author.id, "PAPER", "1.12.2")
                await initmessage(ctx, instance)

            if reaction.emoji == "❌":
                await message.delete()

@bot.command()
async def initmessage(ctx, instance):
    embed = discord.Embed(title = f":tools: Instance {instance.coolname} created. Join at {instance.ip}:{instance.port}", description = "Please allow 30 seconds for startup, this is only running on an E3-1220 V3 :(")
    message = await ctx.send(embed=embed)

@bot.command()
async def waitmessage(ctx, instance):
    embed = discord.Embed(title = f":tools: Please allow 30 seconds for this operation, this is only running on an E3-1220 V3 :(")
    message = await ctx.send(embed=embed)

@bot.command()
async def confirm(ctx, module, instance, text):
    embed = discord.Embed(title = f":tools: {text}", color=0x595959)
    message = await ctx.send(embed=embed)

    for emoji in confirmreactions:
        await message.add_reaction(emoji)

    @bot.event
    async def on_reaction_add(reaction, user):
        if user.id == ctx.message.author.id:
            if reaction.emoji == "✅":
                #await message.delete()
                await module(ctx, instance)
            if reaction.emoji == "❌":
                await message.delete()
                
@bot.event
async def startinstance(ctx, instance):
    await waitmessage(ctx, instance)
    print("Starting instance")
    instance.start()

@bot.event
async def stopinstance(ctx, instance):
    await waitmessage(ctx, instance)
    print("Stopping")
    instance.stop()

@bot.event
async def queryinstance(ctx, instance):
    print("Querying instance")
    pass

@bot.event
async def deleteinstance(ctx, instance):
    await waitmessage(ctx, instance)
    instance.decommission()
    instances.remove(instance)
    del instance

@bot.command()
async def minecraft(ctx):

    instance = get_instance(ctx.author.id)
    if instance == False:
        await ctx.invoke(instancecreator)
        return

    embed = discord.Embed(title = ":tools: Toolbox", description = f"Greetings, {ctx.author.name}.\n Your instances IP is {instance.ip}:{instance.port}\nWhat would you like to do?\n:arrow_forward: Start server \n:stop_button: Stop server \n"+
	":heart_decoration:Check status of server \n:wastebasket:Delete server", color=0x595959)
    message = await ctx.send(embed=embed)
    reactions = ['▶️', '⏹️', '💟', '🗑️']

    for emoji in reactions:
        await message.add_reaction(emoji)

    @bot.event
    async def on_reaction_add(reaction, user):
        if user.id == ctx.message.author.id:
            if reaction.emoji == "▶️":
                await confirm(ctx, startinstance, instance, "Are you sure you want to start your instance?")
                #await message.delete()
            if reaction.emoji == "⏹️":
                await confirm(ctx, stopinstance, instance, "Are you sure you want to stop your instance?")
                #await message.delete()
            if reaction.emoji == "💟":
                await confirm(ctx, queryinstance, instance, "Are you sure you want to query your instance?")
                #await message.delete()
            if reaction.emoji == "🗑️":
                await confirm(ctx, deleteinstance, instance, "Are you sure you want to delete your instance? \n\n:warning:THIS IS IRRESVERSABLE.:warning:")
                #await message.delete()
            
@bot.command()
async def instancelist(ctx):
    for i in instances:
        await ctx.send(i.coolname)

bot.run('', bot=True)
