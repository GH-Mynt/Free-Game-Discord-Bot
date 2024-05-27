import discord
from discord.ext import commands, tasks

import datetime

import json
import aiohttp

def read_token():
    with open("token.txt", "r") as token_file:
        lines = token_file.readlines()
        
        return lines[0].strip()


TOKEN = read_token()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix='>', intents=intents)
bot.remove_command('help')


def update_data(updated_data  : dict) -> None:
    
    with open("data.json", "w") as data_file:
        json.dump(updated_data, data_file)
        
        
def get_data() -> dict:
    
    with open("data.json", "r") as data_file:
        data = json.load(data_file)
        
    return data

async def get_free_games() -> list[dict] | None:
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            
            if r.status != 200:
                print(r.status)
                return 
            
            data = await r.json()
            games = data['data']['Catalog']['searchStore']['elements']
            
            free_games = []
            
            for game in games:
                
                try:
                    promotions = game['promotions']['promotionalOffers']
                except TypeError:
                    # Some games return 'NoneType' for promotions so we can just skip past those
                    continue
                
                if promotions != []:
                    free_games.append(game)
            
            return free_games

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    activity = discord.Activity(type=discord.ActivityType.watching, name= "for free games...")
    await bot.change_presence(activity=activity)
    check_thursday.start()
    

@tasks.loop(minutes = 1)
async def check_thursday():
    
    now = datetime.datetime.now()
    
    if (now.weekday() == 3 and now.hour == 11 and now.minute == 5):
        
        data = get_data()
        free_games = await get_free_games()
        
        if free_games is None:
            print("No free games were found.")
            return
        
        for guild_id, channel_id in data.items():
            channel = bot.get_channel(channel_id)
            
            if not channel:
                print(f"'None' was returned when getting channel_id = {channel_id}. Removing from list.")
                del data[str(guild_id)]
                continue
                
            for game in free_games:
                
                game_embed = discord.Embed(
                    title = game['title'],
                    description = game.get('description', 'No description available'),
                    color  = discord.Color.random()
                )
                game_embed.set_image(url = game['keyImages'][0]['url'])
                game_embed.add_field(name = "Get the game NOW!", value = f"https://www.epicgames.com/store/en-US/p/{game['productSlug']}", inline = False)
                end_date = f"{game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['endDate']}"
                game_embed.set_footer(text = f"Offer expires {end_date[:-14]}")
                
                await channel.send(embed = game_embed)
                
        update_data(data)

@bot.command(name = "set")
async def set_channel_command(ctx : commands.Context, *, channel_name : str):
    
    guild = ctx.guild 
    
    # Check if the `channel_name` given by user is the exact name of the channel
    channel = discord.utils.get(guild.channels, name = channel_name)
    
    # If the channel is `None` then try and replace all the spaces with `-` and lowercase to see if that works
    if channel is None:
        channel = discord.utils.get(guild.channels, name = channel_name.strip().lower().replace(" ", "-"))
        
    # If it is still `None` then see if the user entered a channel ID instead of a name 
    if channel is None:
        try:
            channel_id = int(channel_name)
            channel = bot.get_channel(channel_id)
        except ValueError:
            channel = None 
            
    # If it is still `None` then user did not enter a valid channel
    if (channel is None) or (channel.guild.id != guild.id):
        return await ctx.send(embed = discord.Embed(
            title = "Channel not found.",
            description = "Could not find channel by name or ID.",
            color = discord.Color.red()
        ))
        
    # There is also a chance that the user gives a voice channel as the channel, which wouldn't work.
    if not isinstance(channel, discord.TextChannel):
        return await ctx.send(embed = discord.Embed(
            title = "Invalid channel.",
            description = "The provided channel is a `voice channel` when a `text channel` is needed.",
            color = discord.Color.red()
        ))
        
    data = get_data()
    
    data.update({str(guild.id) : channel.id})
    
    update_data(data)
        
    return await ctx.send(embed=discord.Embed(
        title = 'Channel Set!',
        color = discord.Color.green(),
        description = f'The channel has been set to `{channel.name}`.'
    ))

    
@bot.command(name = "disable")
async def disable_channel_command(ctx : commands.Context):
    
    data = get_data()
    
    embed = discord.Embed(
        title = "Disabled!",
        description = "This server won't receive any more free game updates.",
        color = discord.Color.green()
    )
    
    try:
        del data[str(ctx.guild.id)]
    except KeyError:
        embed = discord.Embed(
            title = "No channel set.",
            description = "There is no channel set for this server, so nothing was done.",
            color = discord.Color.yellow()
        )
        
    update_data(data)
    
    return await ctx.send(embed = embed)

@bot.command(name = "info")
async def information_command(ctx : commands.Context):
    
    info_embed = discord.Embed(
        title = "What is this?",
        description = "Every week, Epic Games gives out games [for free.](https://store.epicgames.com/en-US/free-games) All this bot does is remind you as soon as a new game goes free.",
        color = discord.Color.teal()
    )
    
    return await ctx.send(
        embed = info_embed
    )

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    help_embed = discord.Embed(
        title="Help - Free Game Notifier",
        description="Commands available:",
        color=discord.Color.random()
    )
    help_embed.add_field(
        name = ">set <channel_name or channel_id>",
        value = "Set the channel where free game notifications will be sent.",
        inline = False
    )
    help_embed.add_field(
        name = ">disable",
        value = "Disable the free game notifications for this server.",
        inline = False
    )
    help_embed.add_field(
        name = ">info",
        value = "Simple information about the bot.",
        inline = False
    )
    help_embed.add_field(
        name = ">help",
        value = "Show this help message.",
        inline = False
    )
    
    help_embed.set_footer(text="Free Game Notifier | Developed by Mynt")
    await ctx.send(embed=help_embed)
    
@bot.event
async def on_command_error(ctx : commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    raise error

@check_thursday.before_loop
async def before_check_thursday():
    await bot.wait_until_ready()

bot.run(TOKEN)
