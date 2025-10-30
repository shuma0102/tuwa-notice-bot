import discord
from discord.ui import View, Button, Modal, TextInput, Select
from typing import List
from config_util import get_guild_cfg, set_guild_cfg

class SettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # Webhook設定（Modal）
    @discord.ui.button(label="Webhook設定", style=discord.ButtonStyle.primary, custom_id="set_webhook")
    async def set_webhook_button(self, inter: discord.Interaction, button: Button):
        await inter.response.send_modal(WebhookModal())

    # メンション設定（ロールSelect）
    @discord.ui.button(label="メンション設定", style=discord.ButtonStyle.secondary, custom_id="set_role")
    async def set_role_button(self, inter: discord.Interaction, button: Button):
        options = [discord.SelectOption(label="@here（デフォルト）", value="none")]
        for r in inter.guild.roles:
            if not r.is_default() and r.name != "@everyone":
                options.append(discord.SelectOption(label=r.name, value=str(r.id)))
        await inter.response.send_message("🔔 メンションするロールを選んでください：", view=RoleSelectView(options), ephemeral=True)

    # クールダウン設定（Modal）
    @discord.ui.button(label="クールダウン設定", style=discord.ButtonStyle.secondary, custom_id="set_cd")
    async def set_cd_button(self, inter: discord.Interaction, button: Button):
        await inter.response.send_modal(CooldownModal())

    # 対象VC設定（Select）
    @discord.ui.button(label="対象VC設定", style=discord.ButtonStyle.secondary, custom_id="set_vc")
    async def set_vc_button(self, inter: discord.Interaction, button: Button):
        vcs = [c for c in inter.guild.voice_channels]
        if not vcs:
            return await inter.response.send_message("⚠️ このサーバーにVCがありません。", ephemeral=True)
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in vcs]
        await inter.response.send_message("🎙️ 通知対象にするVCを選んでください：", view=VCSelectView(options), ephemeral=True)

    # 設定確認
    @discord.ui.button(label="設定を確認", style=discord.ButtonStyle.success, custom_id="check_status")
    async def check_status_button(self, inter: discord.Interaction, button: Button):
        gcfg = get_guild_cfg(inter.guild_id)
        webhook = "✅ 登録済み" if gcfg.get("webhook_url") else "❌ 未登録"
        role = gcfg.get("ping_role_id")
        role_txt = f"<@&{role}>" if role else "@here"
        cd = gcfg.get("cooldown_sec", 300)
        vc_ids = gcfg.get("target_vc_ids", [])
        vc_names = [ (ch.name if (ch := inter.guild.get_channel(int(cid))) else f"(不明:{cid})") for cid in vc_ids ]
        vc_disp = "全VC対象" if not vc_names else ", ".join(vc_names)

        embed = discord.Embed(title="📋 通話通知くんの設定状況", color=0x00b0f4)
        embed.add_field(name="Webhook", value=webhook, inline=False)
        embed.add_field(name="メンション", value=role_txt, inline=False)
        embed.add_field(name="クールダウン", value=f"{cd} 秒", inline=False)
        embed.add_field(name="対象VC", value=vc_disp, inline=False)
        await inter.response.send_message(embed=embed, ephemeral=True)

# ---- Webhook Modal ----
class WebhookModal(Modal, title="Webhook URL設定"):
    def __init__(self):
        super().__init__(title="Webhook URL設定")
        self.webhook_url = TextInput(
            label="Webhook URL",
            placeholder="https://discord.com/api/webhooks/...",
            style=discord.TextStyle.short
        )
        self.add_item(self.webhook_url)

    async def on_submit(self, inter: discord.Interaction):
        url = self.webhook_url.value.strip()
        if not url.startswith("https://discord.com/api/webhooks/"):
            return await inter.response.send_message("❌ URLの形式が正しくありません。", ephemeral=True)
        set_guild_cfg(inter.guild_id, "webhook_url", url)
        await inter.response.send_message(f"✅ Webhookを登録しました：{url}", ephemeral=True)

# ---- Role Select ----
class RoleSelectView(View):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(RoleSelect(options))

class RoleSelect(Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(placeholder="メンションするロールを選択", options=options)

    async def callback(self, inter: discord.Interaction):
        val = self.values[0]
        if val == "none":
            set_guild_cfg(inter.guild_id, "ping_role_id", None)
            msg = "メンションを @here に設定しました。"
        else:
            set_guild_cfg(inter.guild_id, "ping_role_id", int(val))
            role = inter.guild.get_role(int(val))
            msg = f"メンションを {role.mention} に設定しました。"
        await inter.response.send_message(f"✅ {msg}", ephemeral=True)

# ---- Cooldown Modal ----
class CooldownModal(Modal, title="クールダウン秒数設定"):
    def __init__(self):
        super().__init__(title="クールダウン秒数設定")
        self.cooldown = TextInput(label="クールダウン秒数", placeholder="例: 300", style=discord.TextStyle.short)
        self.add_item(self.cooldown)

    async def on_submit(self, inter: discord.Interaction):
        try:
            sec = int(self.cooldown.value.strip())
            if not (0 <= sec <= 86400):
                raise ValueError
        except ValueError:
            return await inter.response.send_message("❌ 0〜86400 の数値を入力してください。", ephemeral=True)
        set_guild_cfg(inter.guild_id, "cooldown_sec", sec)
        await inter.response.send_message(f"✅ クールダウンを {sec} 秒に設定しました。", ephemeral=True)

# ---- VC Select ----
class VCSelectView(View):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(VCSelect(options))

class VCSelect(Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(placeholder="対象VCを選択（もう一度選ぶと解除）", options=options)

    async def callback(self, inter: discord.Interaction):
        gid = inter.guild_id
        val = int(self.values[0])
        gcfg = get_guild_cfg(gid)
        vc_set = set(map(int, gcfg.get("target_vc_ids", [])))
        if val in vc_set:
            vc_set.remove(val); msg = "❌ 除外しました"
        else:
            vc_set.add(val);    msg = "✅ 対象に追加しました"
        set_guild_cfg(gid, "target_vc_ids", list(vc_set))
        name = (inter.guild.get_channel(val).name if inter.guild.get_channel(val) else str(val))
        await inter.response.send_message(f"{msg}: **{name}**", ephemeral=True)
