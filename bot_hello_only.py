# bot_hello_only.py — GUILD限定で確実に /hello を作る版（決定打）
import os, logging, discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(x) for x in os.getenv("DEV_GUILD_IDS","").split(",") if x.strip().isdigit()]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hello-guild-only")

if not TOKEN or not GUILD_IDS:
    raise SystemExit("環境変数が不足：DISCORD_TOKEN と DEV_GUILD_IDS を設定してください。")

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ★ ここで “ギルド限定” のコマンドとして定義（UI反映が速く、確実）
GUILDS = [discord.Object(id=gid) for gid in GUILD_IDS]

@tree.command(name="hello", description="動作確認用の挨拶", guilds=GUILDS)
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("👋 こんにちは！（/hello 成功）", ephemeral=True)

@client.event
async def on_ready():
    log.info(f"Logged in as {client.user} ({client.user.id}), app_id={client.application_id}")
    # 既存のギルドコマンドを一覧しながら同期
    for gid in GUILD_IDS:
        try:
            guild = discord.Object(id=gid)
            synced = await tree.sync(guild=guild)  # ← GUILDに限定同期
            log.info(f"[guild {gid}] synced {len(synced)} cmd(s): {[c.name for c in synced]}")
        except Exception as e:
            log.exception(f"[guild {gid}] sync error: {e}")

client.run(TOKEN)
