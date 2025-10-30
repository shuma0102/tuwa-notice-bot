import os, time, asyncio, logging, random
from typing import Dict, Any, Tuple, List

import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

# 環境変数
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DEV_GUILD_IDS: List[int] = [int(x) for x in os.getenv("DEV_GUILD_IDS", "").split(",") if x.strip().isdigit()]
print("✅ DEV_GUILD_IDS =", DEV_GUILD_IDS)

# 設定/UI 読み込み
from config_util import conf, get_guild_cfg, set_guild_cfg, DEFAULT_COOLDOWN_SEC
from ui_views.settings_view import SettingsView

# ロガー
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vc-webhook-notifier")

# Discord Client
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 管理者チェック
def admin_only(inter: discord.Interaction) -> bool:
    p = inter.user.guild_permissions
    return p.administrator or p.manage_guild

# 通知ユーティリティ
last_notice_at: Dict[Tuple[int, int], float] = {}

def vc_is_target(gid: int, vcid: int) -> bool:
    target = (get_guild_cfg(gid).get("target_vc_ids") or [])
    return (not target) or (int(vcid) in map(int, target))

def can_notify(gid: int, vcid: int, cooldown_sec: int) -> bool:
    now = time.time(); key = (gid, vcid)
    last = last_notice_at.get(key, 0.0)
    if now - last >= cooldown_sec:
        last_notice_at[key] = now
        return True
    return False

async def post_webhook(url: str, payload: Dict[str, Any]) -> tuple[bool, str]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=10) as r:
                if 200 <= r.status < 300:
                    return True, ""
                if r.status == 429:
                    ra = 0.0
                    try:
                        if "application/json" in r.headers.get("Content-Type", ""):
                            data = await r.json()
                            ra = float(data.get("retry_after", 0))
                    except Exception:
                        pass
                    if ra > 0:
                        await asyncio.sleep(min(ra, 5))
                        async with s.post(url, json=payload, timeout=10) as r2:
                            if 200 <= r2.status < 300:
                                return True, ""
                            return False, f"HTTP {r2.status} after retry"
                return False, f"HTTP {r.status}"
    except asyncio.TimeoutError:
        return False, "timeout"
    except Exception as e:
        return False, f"{e}"

# VC検知
@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    try:
        if before.channel is None and after.channel is not None:
            guild = member.guild
            vc = after.channel  # VoiceChannel / StageChannel

            if not vc_is_target(guild.id, vc.id):
                return

            humans = [m for m in vc.members if not m.bot]
            if len(humans) != 1:
                return  # 一人目だけ通知

            gcfg = get_guild_cfg(guild.id)
            url = gcfg.get("webhook_url")
            if not url:
                return

            cooldown = int(gcfg.get("cooldown_sec", DEFAULT_COOLDOWN_SEC))
            if not can_notify(guild.id, vc.id, cooldown):
                return

            mention = "@here"
            if gcfg.get("ping_role_id"):
                mention = f"<@&{int(gcfg['ping_role_id'])}>"

            ts = int(time.time())
            color = random.randint(0, 0xFFFFFF)  # 🎲 Embed色ランダム

            # カード風の3列インライン & 右側にサムネ
            embed = {
                "title": "通話開始",
                "color": color,
                "fields": [
                    {"name": "チャンネル", "value": vc.mention, "inline": True},
                    {"name": "始めた人", "value": member.display_name, "inline": True},
                    {"name": "開始時間", "value": f"<t:{ts}:D>\n<t:{ts}:T>", "inline": True},
                ],
                "thumbnail": {"url": member.display_avatar.url},
                "footer": {"text": "通話通知くん"},
            }

            payload = {
                "content": f"誰かがお話し中です♪ {mention}",
                "embeds": [embed],
                "allowed_mentions": {"parse": ["roles", "everyone", "users"]},
            }
            ok, err = await post_webhook(url, payload)
            if not ok:
                log.warning(f"[{guild.id}] webhook send failed: {err}")
    except Exception as e:
        log.exception(f"on_voice_state_update error: {e}")

# /setup（設定パネルを貼る）
@app_commands.command(name="setup", description="設定パネルをこのチャンネルに設置（管理者のみ）")
async def setup(inter: discord.Interaction):
    if not admin_only(inter):
        return await inter.response.send_message("権限がありません（管理者のみ）", ephemeral=True)

    embed = discord.Embed(
        title="🎛 通話通知くん 設定パネル",
        description="下のボタンから設定を変更できます！",
        color=0x00b0f4
    )
    embed.add_field(name="Webhook設定", value="通知を送るDiscord Webhookを登録します。", inline=False)
    embed.add_field(name="メンション設定", value="通知時に@hereかロールを指定できます。", inline=False)
    embed.add_field(name="クールダウン", value="通知の再送間隔を設定します。", inline=False)
    embed.add_field(name="対象VC設定", value="どのVCで通知するかを選べます。", inline=False)
    embed.add_field(name="現在の設定確認", value="設定済み内容をEmbedで表示します。", inline=False)

    await inter.channel.send(embed=embed, view=SettingsView())
    await inter.response.send_message("✅ 設定パネルを設置しました！", ephemeral=True)

# 起動時：/setup を鯖へ明示登録→同期
@client.event
async def on_ready():
    log.info(f"Logged in as {client.user} ({client.user.id})")
    for gid in DEV_GUILD_IDS:
        guild_obj = discord.Object(id=gid)
        try:
            tree.add_command(setup, guild=guild_obj)      # 明示追加
            synced = await tree.sync(guild=guild_obj)     # 即時同期
            log.info(f"[guild {gid}] synced {len(synced)} commands: {[c.name for c in synced]}")
        except Exception as e:
            log.exception(e)

# 実行
client.run(TOKEN)
