import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio
import sqlite3
import aiosqlite
import re

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    print(" ошибка токен не найден")
    exit(1)

# =============== ID =================
ROLE_APPLICANT_ACCESS = 1444647329725677582
FAMILY_ROLE_ID = 1449119840286675025
VOICE_CHANNEL_ID = 1449117056019468419
LOG_CHANNEL_ID = 1450181312769167500
RECRUIT_APP_CHANNEL_ID = 1450511499704668170
REPORT_CHANNEL_ID = 1452532989090332724

HR_ROLES = {
    1449116921533431898,
    1449116925220225094,
    1449116939287793724,
    1449116944589520926,
    1449116948011946005,
}
CONFIRMATION_ROLES = {1449116921533431898, 1449116925220225094, 1449116939287793724, 1449116944589520926}

RANK_NAME_TO_ID = {
    "leader 8 rang": 1449116921533431898,
    "owner 7 rang": 1449116925220225094,
    "dep leader 6 rang": 1449116939287793724,
    "high rank 5 rang": 1449116944589520926,
    "recruit 4 rang": 1449116948011946005,
    "main 3 rang": 1449116951732289596,
    "test 2 rang": 1449116959550734488,
    "academ 1 rang": 1449116973010128957,
}
ID_TO_RANK_NAME = {v: k for k, v in RANK_NAME_TO_ID.items()}
RANK_ROLES = RANK_NAME_TO_ID

AWARD_ROLES = {
    "за_верность": 1452534631185514496,
    "за_храбрость": 1452534677436108922,
    "за_службу": 1452534726718914683,
}

COMPOSITION_MESSAGE_ID = None
FAQ_MESSAGE_CONTENT = None
ANNOUNCEMENT_TASKS = {}

# =============== БАЗА ДАННЫХ ===============
def init_db():
    conn = sqlite3.connect("dominate_famq.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER,
            reason TEXT,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            action_type TEXT,
            target_id INTEGER,
            actor_id INTEGER,
            details TEXT,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            message_id INTEGER,
            applicant_id INTEGER,
            channel_id INTEGER,
            app_type TEXT,
            content TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            event_time TEXT,
            content TEXT,
            creator_id INTEGER,
            created_at TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            static_id TEXT,
            name_irl TEXT,
            join_date TEXT,
            last_passport_update TEXT
        )
    """)
    conn.commit()
    conn.close()

# =============== ВСПОМОГАТЕЛЬНЫЕ ===============
def has_any_role(member, role_ids):
    return any(role.id in role_ids for role in member.roles)

def get_member_status(member):
    return {
        discord.Status.online: "🟢",
        discord.Status.idle: "🟡",
        discord.Status.dnd: "🔴",
        discord.Status.offline: "⚪"
    }.get(member.status, "⚪")

async def remove_all_rank_roles(member: discord.Member):
    roles_to_remove = []
    for role_id in RANK_NAME_TO_ID.values():
        role = discord.utils.get(member.guild.roles, id=role_id)
        if role and role in member.roles:
            roles_to_remove.append(role)
    family_role = discord.utils.get(member.guild.roles, id=FAMILY_ROLE_ID)
    if family_role and family_role in member.roles:
        roles_to_remove.append(family_role)
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove)
    return roles_to_remove

async def log_action(content):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(content)

async def log_action_to_db(action_type, target_id, actor_id, details):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            await db.execute(
                "INSERT INTO actions (action_type, target_id, actor_id, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (action_type, target_id, actor_id, details, datetime.utcnow().isoformat())
            )
            await db.commit()
    except Exception as e:
        print(f"DB log error: {e}")

async def get_warnings(user_id):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            cursor = await db.execute("SELECT reason FROM warnings WHERE user_id = ?", (user_id,))
            return await cursor.fetchall()
    except:
        return []

async def add_warning(user_id, reason):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            await db.execute(
                "INSERT INTO warnings (user_id, reason, timestamp) VALUES (?, ?, ?)",
                (user_id, reason, datetime.utcnow().isoformat())
            )
            await db.commit()
    except Exception as e:
        print(f"DB warning error: {e}")

async def clear_warnings(user_id):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            await db.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
            await db.commit()
    except:
        pass

async def save_member_info(user_id: int, static_id: str = None, name_irl: str = None):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            cursor = await db.execute("SELECT join_date FROM members WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    "UPDATE members SET static_id = ?, name_irl = ?, last_passport_update = ? WHERE user_id = ?",
                    (static_id, name_irl, datetime.utcnow().isoformat(), user_id)
                )
            else:
                await db.execute(
                    "INSERT INTO members (user_id, static_id, name_irl, join_date, last_passport_update) VALUES (?, ?, ?, ?, ?)",
                    (user_id, static_id, name_irl, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
                )
            await db.commit()
    except Exception as e:
        print(f"DB member save error: {e}")

async def get_member_info(user_id: int):
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            cursor = await db.execute("SELECT static_id, name_irl, join_date FROM members WHERE user_id = ?", (user_id,))
            return await cursor.fetchone()
    except:
        return None

# =============== БОТ ===============
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =============== КОМПОНЕНТЫ ===============
class ApplicationButtons(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Заявка в РП стак", style=discord.ButtonStyle.primary)
    async def rp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal(self.channel_id, "RP"))

    @discord.ui.button(label="Заявка в капт стак", style=discord.ButtonStyle.secondary)
    async def capt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal(self.channel_id, "CAPT"))

class ApplicationModal(discord.ui.Modal):
    def __init__(self, channel_id, app_type):
        super().__init__(title="Подача заявки")
        self.channel_id = channel_id
        self.app_type = app_type

        self.q1 = discord.ui.TextInput(label="Nick Name || Static ID || Имя IRL", required=True, max_length=100)
        self.q2 = discord.ui.TextInput(label="Возраст IRL", required=True, max_length=3)
        self.q3 = discord.ui.TextInput(label="В каких семьях состояли на Majestic", required=True, max_length=200)
        self.add_item(self.q1)
        self.add_item(self.q2)
        self.add_item(self.q3)

        if app_type == "CAPT":
            self.q4 = discord.ui.TextInput(label="Откат стрельбы на (тяге/сайге)", required=True, max_length=200)
            self.add_item(self.q4)

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("❌ Канал для заявок не найден.", ephemeral=True)
            return

        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        embed = discord.Embed(title="Новая заявка", color=discord.Color.blurple(), timestamp=datetime.utcnow())
        embed.add_field(name="Дата/время", value=now, inline=False)
        embed.add_field(name="Discord ID", value=interaction.user.id, inline=False)
        embed.add_field(name="Пинг", value=interaction.user.mention, inline=False)
        embed.add_field(name="Ответы", value=f"1. {self.q1.value}\n2. {self.q2.value}\n3. {self.q3.value}", inline=False)
        if self.app_type == "CAPT":
            embed.add_field(name="Откат стрельбы", value=self.q4.value, inline=False)

        view = ApplicationActionView(interaction.user.id)
        message = await channel.send(embed=embed, view=view)

        async with aiosqlite.connect("dominate_famq.db") as db:
            content = f"{self.q1.value}|{self.q2.value}|{self.q3.value}" + (f"|{self.q4.value}" if self.app_type == "CAPT" else "")
            await db.execute(
                "INSERT INTO applications (message_id, applicant_id, channel_id, app_type, content) VALUES (?, ?, ?, ?, ?)",
                (message.id, interaction.user.id, self.channel_id, self.app_type, content)
            )
            await db.commit()

        await interaction.response.send_message("✅ Ваша заявка отправлена!", ephemeral=True)

class ApplicationActionView(discord.ui.View):
    def __init__(self, applicant_id):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.reviewed = False

    @discord.ui.button(label="Вызвать на обзвон", style=discord.ButtonStyle.blurple)
    async def call_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, HR_ROLES):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            return
        try:
            applicant = await bot.fetch_user(self.applicant_id)
            voice = bot.get_channel(VOICE_CHANNEL_ID)
            msg = f"Ваша заявка взята на рассмотрение. Зайдите в войс: {voice.mention}" if voice else "Зайдите в войс семьи."
            await applicant.send(msg)
            await interaction.response.send_message("✅ Участник вызван.", ephemeral=True)
        except:
            await interaction.response.send_message("⚠️ Не удалось отправить ЛС.", ephemeral=True)

    @discord.ui.button(label="🟢 Принять", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, HR_ROLES) or self.reviewed:
            await interaction.response.send_message("❌ Недоступно.", ephemeral=True)
            return
        self.reviewed = True
        self.disable_all_items()
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text=f"Рассмотрено: {interaction.user} (Принято)")
        await interaction.message.edit(embed=embed, view=self)

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            family_role = interaction.guild.get_role(FAMILY_ROLE_ID)
            if family_role and family_role not in member.roles:
                await member.add_roles(family_role)
            await log_action(f"✅ **Принят**: {member.mention} — {interaction.user.mention}")
            await log_action_to_db("accept", member.id, interaction.user.id, "manual_accept")

        try:
            await (await bot.fetch_user(self.applicant_id)).send("🟢 Ваша заявка **принята**! Добро пожаловать в DOMINATE FAMQ!")
        except:
            pass
        await interaction.response.send_message("✅ Заявка принята.", ephemeral=True)

    @discord.ui.button(label="🔴 Отказать", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, HR_ROLES) or self.reviewed:
            await interaction.response.send_message("❌ Недоступно.", ephemeral=True)
            return
        await interaction.response.send_modal(RejectReasonModal(self.applicant_id, interaction.message, self))

class RejectReasonModal(discord.ui.Modal):
    def __init__(self, applicant_id, message, view):
        super().__init__(title="Причина отказа")
        self.applicant_id = applicant_id
        self.message = message
        self.view = view
        self.reason = discord.ui.TextInput(label="Причина", required=True, max_length=300)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.reviewed = True
        self.view.disable_all_items()
        embed = self.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"Рассмотрено: {interaction.user} (Отказано)")
        embed.add_field(name="Причина отказа", value=self.reason.value, inline=False)
        await self.message.edit(embed=embed, view=self)

        try:
            await (await bot.fetch_user(self.applicant_id)).send(f"🔴 Ваша заявка **отклонена**.\nПричина: {self.reason.value}")
        except:
            pass

        await log_action(f"❌ **Отказано**: <@{self.applicant_id}> — {interaction.user.mention}\nПричина: {self.reason.value}")
        await interaction.response.send_message("✅ Отказ отправлен.", ephemeral=True)

class FireConfirmationView(discord.ui.View):
    def __init__(self, member, static_id, reason, author):
        super().__init__(timeout=60)
        self.member = member
        self.static_id = static_id
        self.reason = reason
        self.author = author

    @discord.ui.button(label="Подтвердить увольнение", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, CONFIRMATION_ROLES):
            await interaction.response.send_message("❌ Только лидерство может подтверждать.", ephemeral=True)
            return

        removed = await remove_all_rank_roles(self.member)
        roles_display = ", ".join(ID_TO_RANK_NAME.get(r.id, str(r.id)) for r in removed) or "Нет"

        embed = discord.Embed(title="🔴 Увольнение", color=discord.Color.red())
        embed.add_field(name="Кто уволил", value=f"{self.author.mention} | {self.author.id}", inline=False)
        embed.add_field(name="Кого уволил", value=f"{self.member.mention} | {self.member.id}", inline=False)
        embed.add_field(name="Дата/время", value=datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
        embed.add_field(name="Подробности", value=f"Причина: {self.reason}\nСнятые роли: {roles_display}\nStatic ID: {self.static_id}", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)
        await log_action(f"❌ **Уволен**: {self.member.mention} — {self.author.mention} | {self.reason}")
        await log_action_to_db("fire", self.member.id, self.author.id, self.reason)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Отменено.", embed=None, view=None)

# =============== КОМАНДЫ ===============
def hr_command_check():
    return app_commands.check(lambda i: has_any_role(i.user, HR_ROLES))

def high_rank_check():
    return app_commands.check(lambda i: has_any_role(i.user, CONFIRMATION_ROLES))

@bot.tree.command(name="набор", description="Отправить форму набора")
@app_commands.describe(channel_id="ID канала, куда будут приходить заявки")
@bot.tree.command(name="набор", description="Отправить форму набора")
@app_commands.describe(channel="Канал, куда будут приходить заявки")
async def recruitment(interaction: discord.Interaction, channel: discord.TextChannel):
    # Теперь channel — это объект канала, channel.id — его ID
    ...
    view = ApplicationButtons(channel.id)
    if not discord.utils.get(interaction.user.roles, id=ROLE_APPLICANT_ACCESS):
        await interaction.response.send_message("❌ У вас нет роли для этой команды.", ephemeral=True)
        return
    try:
        cid = int(channel_id)
    except:
        await interaction.response.send_message("❌ Неверный ID канала.", ephemeral=True)
        return
    if not bot.get_channel(cid):
        await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔥 ДОБРО ПОЖАЛОВАТЬ В DOMINATE FAMQ!",
        description="💀 Ты вошёл в криминальную империю, где лояльность — выше всего.\n\n"
                    "📜 Наши принципы:\n"
                    "✅ Возраст от 13 лет\n"
                    "✅ Адекватность и уважение\n"
                    "✅ Пунктуальность и ответственность\n"
                    "✅ Командный дух — мы едины.\n\n"
                    "🔥 Готов влиться в легенду? Подавай заявку!",
        color=discord.Color.dark_red()
    )
    await interaction.response.send_message(embed=embed, view=ApplicationButtons(cid))

@bot.tree.command(name="заявка_на_рекрута", description="Подать заявку на рекрута (только для членов семьи)")
async def recruit_app(interaction: discord.Interaction):
    if not discord.utils.get(interaction.user.roles, id=FAMILY_ROLE_ID):
        await interaction.response.send_message("❌ Только члены семьи могут подавать заявку.", ephemeral=True)
        return
    await interaction.response.send_modal(RecruitAppModal())

class RecruitAppModal(discord.ui.Modal, title="Заявка на рекрута"):
    nick = discord.ui.TextInput(label="Ваш ник", required=True)
    age = discord.ui.TextInput(label="Сколько вам лет", max_length=3, required=True)
    rank = discord.ui.TextInput(label="Ваш текущий ранг", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(RECRUIT_APP_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Канал заявок не найден.", ephemeral=True)
            return

        embed = discord.Embed(title="📄 Заявка на рекрута", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(name="Дата/время", value=datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
        embed.add_field(name="Discord ID", value=interaction.user.id, inline=False)
        embed.add_field(name="Пинг", value=interaction.user.mention, inline=False)
        embed.add_field(name="Ответы", value=f"1. {self.nick.value}\n2. {self.age.value}\n3. {self.rank.value}", inline=False)

        view = ApplicationActionView(interaction.user.id)
        message = await channel.send(embed=embed, view=view)

        async with aiosqlite.connect("dominate_famq.db") as db:
            await db.execute(
                "INSERT INTO applications (message_id, applicant_id, channel_id, app_type, content) VALUES (?, ?, ?, ?, ?)",
                (message.id, interaction.user.id, RECRUIT_APP_CHANNEL_ID, "recruit_app", f"{self.nick.value}|{self.age.value}|{self.rank.value}")
            )
            await db.commit()

        await interaction.response.send_message("✅ Заявка отправлена!", ephemeral=True)

@bot.tree.command(name="принятие", description="Принять участника в семью")
@hr_command_check()
@app_commands.describe(member="Участник", static_id="Static ID", reason="Причина принятия")
async def accept_member(interaction: discord.Interaction, member: discord.Member, static_id: str, reason: str):
    family_role = interaction.guild.get_role(FAMILY_ROLE_ID)
    if family_role and family_role not in member.roles:
        await member.add_roles(family_role)
    await save_member_info(member.id, static_id=static_id)
    roles_display = ", ".join(ID_TO_RANK_NAME.get(r.id, str(r.id)) for r in member.roles if r.id in ID_TO_RANK_NAME) or "Нет"
    embed = discord.Embed(title="🟢 Принятие", color=discord.Color.green())
    embed.add_field(name="Кто принял", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Кого принял", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Дата/время", value=datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
    embed.add_field(name="Подробности", value=f"Причина: {reason}\nРоли: {roles_display}\nStatic ID: {static_id}", inline=False)
    await interaction.response.send_message(embed=embed)
    await log_action(f"✅ **Принят вручную**: {member.mention} — {interaction.user.mention} | {reason}")
    await log_action_to_db("accept", member.id, interaction.user.id, reason)

@bot.tree.command(name="увольнение", description="Уволить участника")
@hr_command_check()
@app_commands.describe(member="Участник", static_id="Static ID", reason="Причина увольнения")
async def fire_member(interaction: discord.Interaction, member: discord.Member, static_id: str, reason: str):
    embed = discord.Embed(title="Подтверждение увольнения", description=f"Вы уверены, что хотите уволить {member.mention}?", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=FireConfirmationView(member, static_id, reason, interaction.user), ephemeral=True)

@bot.tree.command(name="повышение", description="Повысить участника")
@hr_command_check()
@app_commands.describe(member="Участник", static_id="Static ID", current_rank="Текущий ранг", new_rank="Новый ранг", reason="Причина")
async def promote(interaction: discord.Interaction, member: discord.Member, static_id: str, current_rank: str, new_rank: str, reason: str):
    cr, nr = current_rank.lower().strip(), new_rank.lower().strip()
    if cr not in RANK_NAME_TO_ID or nr not in RANK_NAME_TO_ID:
        valid = ", ".join(RANK_NAME_TO_ID.keys())
        await interaction.response.send_message(f"❌ Неверный ранг. Допустимо: {valid}", ephemeral=True)
        return

    old_role = interaction.guild.get_role(RANK_NAME_TO_ID[cr])
    new_role = interaction.guild.get_role(RANK_NAME_TO_ID[nr])
    if not new_role:
        await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
        return

    if old_role and old_role in member.roles:
        await member.remove_roles(old_role)
    if new_role not in member.roles:
        await member.add_roles(new_role)

    family_role = interaction.guild.get_role(FAMILY_ROLE_ID)
    if family_role and family_role not in member.roles:
        await member.add_roles(family_role)

    embed = discord.Embed(title="📈 Отчет на повышение", color=discord.Color.green())
    embed.add_field(name="Повышен", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Кто повышал", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Старый → Новый", value=f"{current_rank} → {new_rank}", inline=False)
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.add_field(name="Дата/время", value=datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
    await interaction.response.send_message(embed=embed)
    await log_action(f"⬆️ **Повышение**: {member.mention} ({current_rank} → {new_rank}) — {interaction.user.mention} | {reason}")
    await log_action_to_db("promote", member.id, interaction.user.id, f"{cr}→{nr}")

@bot.tree.command(name="понижение", description="Понизить участника")
@hr_command_check()
@app_commands.describe(member="Участник", static_id="Static ID", current_rank="Текущий ранг", new_rank="Новый ранг", reason="Причина")
async def demote(interaction: discord.Interaction, member: discord.Member, static_id: str, current_rank: str, new_rank: str, reason: str):
    cr, nr = current_rank.lower().strip(), new_rank.lower().strip()
    if cr not in RANK_NAME_TO_ID or nr not in RANK_NAME_TO_ID:
        valid = ", ".join(RANK_NAME_TO_ID.keys())
        await interaction.response.send_message(f"❌ Неверный ранг. Допустимо: {valid}", ephemeral=True)
        return

    old_role = interaction.guild.get_role(RANK_NAME_TO_ID[cr])
    new_role = interaction.guild.get_role(RANK_NAME_TO_ID[nr])
    if not new_role:
        await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
        return

    if old_role and old_role in member.roles:
        await member.remove_roles(old_role)
    if new_role not in member.roles:
        await member.add_roles(new_role)

    embed = discord.Embed(title="📉 Отчет на понижение", color=discord.Color.orange())
    embed.add_field(name="Понижен", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Кто понижал", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Старый → Новый", value=f"{current_rank} → {new_rank}", inline=False)
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.add_field(name="Дата/время", value=datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
    await interaction.response.send_message(embed=embed)
    await log_action(f"⬇️ **Понижение**: {member.mention} ({current_rank} → {new_rank}) — {interaction.user.mention} | {reason}")
    await log_action_to_db("demote", member.id, interaction.user.id, f"{cr}→{nr}")

@bot.tree.command(name="предупреждение", description="Выдать предупреждение")
@hr_command_check()
@app_commands.describe(member="Участник", reason="Причина")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await add_warning(member.id, reason)
    count = len(await get_warnings(member.id))
    if count >= 3:
        await clear_warnings(member.id)
        await remove_all_rank_roles(member)
        await interaction.response.send_message(f"⚠️ {member.mention} получил 3 предупреждения и **уволен**.")
        await log_action(f"⚠️ **Автоувольнение**: {member.mention} за 3 предупреждения")
        await log_action_to_db("auto_fire", member.id, bot.user.id, "3 warnings")
    else:
        await interaction.response.send_message(f"⚠️ {member.mention} получил предупреждение ({count}/3): {reason}")
        await log_action(f"⚠️ **Предупреждение**: {member.mention} — {reason} ({count}/3)")
        await log_action_to_db("warning", member.id, interaction.user.id, reason)

@bot.tree.command(name="вызов", description="Вызвать участника на допрос")
@hr_command_check()
@app_commands.describe(member="Участник", reason="Причина")
async def summon(interaction: discord.Interaction, member: discord.Member, reason: str):
    try:
        voice = bot.get_channel(VOICE_CHANNEL_ID)
        msg = f"👮 **ВАС ВЫЗЫВАЮТ НА ДОПРОС!**\nПричина: **{reason}**\nЗайдите в войс: {voice.mention if voice else 'войс семьи'}"
        await member.send(msg)
        await interaction.response.send_message(f"✅ {member.mention} вызван.", ephemeral=True)
        await log_action(f"📞 **Вызов**: {member.mention} — {reason} — {interaction.user.mention}")
        await log_action_to_db("summon", member.id, interaction.user.id, reason)
    except:
        await interaction.response.send_message("⚠️ Не удалось отправить ЛС.", ephemeral=True)

@bot.tree.command(name="наградить", description="Выдать награду участнику")
@app_commands.describe(member="Участник", award="Награда")
@app_commands.choices(award=[
    app_commands.Choice(name="За верность", value="за_верность"),
    app_commands.Choice(name="За храбрость", value="за_храбрость"),
    app_commands.Choice(name="За службу", value="за_службу"),
])
async def award_member(interaction: discord.Interaction, member: discord.Member, award: str):
    if not has_any_role(interaction.user, CONFIRMATION_ROLES):
        await interaction.response.send_message("❌ Только лидерство может выдавать награды.", ephemeral=True)
        return
    role_id = AWARD_ROLES[award]
    role = interaction.guild.get_role(role_id)
    if not role:
        await interaction.response.send_message("❌ Роль награды не найдена.", ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message("🟡 Участник уже имеет эту награду.", ephemeral=True)
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ {member.mention} получил награду: **{award}**!")
    await log_action(f"🎖️ **Награда**: {member.mention} — {award} — {interaction.user.mention}")
    await log_action_to_db("award", member.id, interaction.user.id, award)

@bot.tree.command(name="обновить_состав", description="Обновить состав в канале")
@high_rank_check()
async def update_composition(interaction: discord.Interaction):
    global COMPOSITION_MESSAGE_ID
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("❌ Канал состава не найден.", ephemeral=True)
        return

    embed = discord.Embed(title="👥 Состав DOMINATE FAMQ", color=discord.Color.dark_red(), timestamp=datetime.utcnow())
    total, online = 0, 0
    for role_id, name in RANK_ROLES.items():
        role = interaction.guild.get_role(role_id)
        if not role:
            continue
        members = [m for m in role.members if not m.bot]
        total += len(members)
        online += sum(1 for m in members if m.status != discord.Status.offline)
        lst = "\n".join(f"{i+1}. {m.mention} {get_member_status(m)}" for i, m in enumerate(members)) if members else "—"
        embed.add_field(name=f"**{name}**", value=lst, inline=False)

    embed.set_footer(text=f"Всего: {total} | Онлайн: {online}")

    if COMPOSITION_MESSAGE_ID:
        try:
            msg = await channel.fetch_message(COMPOSITION_MESSAGE_ID)
            await msg.edit(embed=embed)
        except:
            msg = await channel.send(embed=embed)
            COMPOSITION_MESSAGE_ID = msg.id
    else:
        msg = await channel.send(embed=embed)
        COMPOSITION_MESSAGE_ID = msg.id

    await interaction.response.send_message("✅ Состав обновлён!", ephemeral=True)

@bot.tree.command(name="лсответ", description="Установить текст для новых участников")
@app_commands.describe(channel_id="ID канала с текстом (последнее сообщение)")
async def set_faq(interaction: discord.Interaction, channel_id: str):
    if not discord.utils.get(interaction.user.roles, id=ROLE_APPLICANT_ACCESS):
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    try:
        chan = bot.get_channel(int(channel_id))
        if not chan:
            raise ValueError
        async for msg in chan.history(limit=1):
            global FAQ_MESSAGE_CONTENT
            FAQ_MESSAGE_CONTENT = msg.content
            await interaction.response.send_message("✅ Текст для ЛС обновлён!", ephemeral=True)
            return
        await interaction.response.send_message("❌ В канале нет сообщений.", ephemeral=True)
    except:
        await interaction.response.send_message("❌ Ошибка. Проверьте ID канала.", ephemeral=True)

@bot.tree.command(name="отправить_лс", description="Отправить FAQ участнику")
@app_commands.describe(member="Участник")
async def send_faq(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=ROLE_APPLICANT_ACCESS):
        await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        return
    if not FAQ_MESSAGE_CONTENT:
        await interaction.response.send_message("❌ Текст не задан. Используйте /лсответ.", ephemeral=True)
        return
    try:
        await member.send(FAQ_MESSAGE_CONTENT)
        await interaction.response.send_message(f"✅ FAQ отправлен {member.mention}!", ephemeral=True)
    except:
        await interaction.response.send_message("⚠️ Не удалось отправить ЛС.", ephemeral=True)

# =============== ПАСПОРТ ===============
@bot.tree.command(name="паспорт", description="Получить паспорт участника")
@app_commands.describe(member="Участник")
async def passport(interaction: discord.Interaction, member: discord.Member):
    if member != interaction.user and not has_any_role(interaction.user, HR_ROLES):
        await interaction.response.send_message("❌ Вы можете посмотреть только свой паспорт.", ephemeral=True)
        return

    info = await get_member_info(member.id)
    static_id = "Не указано"
    name_irl = "Не указано"
    join_date_str = None
    if info:
        static_id, name_irl, join_date_str = info

    rank_name = "Нет ранга"
    for role_id, name in ID_TO_RANK_NAME.items():
        if discord.utils.get(member.roles, id=role_id):
            rank_name = name
            break

    awards = []
    for award_key, role_id in AWARD_ROLES.items():
        if discord.utils.get(member.roles, id=role_id):
            awards.append(award_key.replace("_", " ").capitalize())
    awards_str = ", ".join(awards) if awards else "Нет"

    join_datetime = datetime.fromisoformat(join_date_str) if join_date_str else datetime.utcnow()
    days_in_famq = (datetime.utcnow() - join_datetime).days
    join_date = join_datetime.strftime("%d.%m.%Y") if join_date_str else "Неизвестно"

    status_emoji = get_member_status(member)
    status_text = "Активен" if member.status != discord.Status.offline else "Не в сети"

    async with aiosqlite.connect("dominate_famq.db") as db:
        cursor = await db.execute(
            "SELECT actor_id FROM actions WHERE action_type = 'accept' AND target_id = ? ORDER BY timestamp DESC LIMIT 1",
            (member.id,)
        )
        signer_row = await cursor.fetchone()
        signer = "Система"
        if signer_row:
            try:
                signer_user = await bot.fetch_user(signer_row[0])
                signer = f"{signer_user.mention} ({signer_user.name})"
            except:
                signer = "HR"

    embed = discord.Embed(
        title="📌 ПАСПОРТ ЧЛЕНА DOMINATE FAMQ",
        color=discord.Color.dark_red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Имя (IRL)", value=name_irl, inline=False)
    embed.add_field(name="Nick", value=member.name, inline=False)
    embed.add_field(name="Static ID", value=static_id, inline=False)
    embed.add_field(name="Ранг", value=rank_name, inline=False)
    embed.add_field(name="Награды", value=awards_str, inline=False)
    embed.add_field(name="Стаж", value=f"{days_in_famq} дней", inline=False)
    embed.add_field(name="Статус", value=f"{status_emoji} {status_text}", inline=False)
    embed.add_field(name="Дата приёма", value=join_date, inline=False)
    embed.add_field(name="Подпись", value=signer, inline=False)
    embed.set_footer(text="Документ строго конфиденциален")

    try:
        if member == interaction.user:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("✅ Паспорт отправлен вам в ЛС.", ephemeral=True)
    except:
        await interaction.response.send_message("⚠️ Не удалось отправить ЛС.", ephemeral=True)

@bot.tree.command(name="обновить_паспорт", description="Обновить данные в паспорте (IRL, Static ID)")
@app_commands.describe(static_id="Ваш Static ID", name_irl="Ваше имя IRL")
async def update_passport(interaction: discord.Interaction, static_id: str, name_irl: str):
    await save_member_info(interaction.user.id, static_id, name_irl)
    await interaction.response.send_message("✅ Данные паспорта обновлены!", ephemeral=True)

# =============== АНОНСЫ ===============
async def send_announcement_notification(channel_id, content, title):
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    guild = channel.guild
    mentioned_roles = []
    for rank_name in ["main 3 rang", "recruit 4 rang", "high rank 5 rang", "dep leader 6 rang", "owner 7 rang", "leader 8 rang"]:
        role_id = RANK_NAME_TO_ID.get(rank_name)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                mentioned_roles.append(role.mention)

    mention_str = " ".join(mentioned_roles) if mentioned_roles else "@here"

    embed = discord.Embed(title=title, description=content, color=discord.Color.red())
    try:
        await channel.send(content=mention_str, embed=embed)
    except:
        pass

async def schedule_announcement(ann_id, channel_id, event_time, content):
    if ann_id in ANNOUNCEMENT_TASKS:
        for task in ANNOUNCEMENT_TASKS[ann_id]:
            task.cancel()

    async def notify_1h():
        now = datetime.now()
        if event_time > now:
            await asyncio.sleep((event_time - now).total_seconds() - 3600)
            await send_announcement_notification(channel_id, content, "🔴 **НАПОМИНАНИЕ (1 час до события)**")

    async def notify_5m():
        now = datetime.now()
        if event_time > now:
            await asyncio.sleep((event_time - now).total_seconds() - 300)
            await send_announcement_notification(channel_id, content, "🔥 **СОБЫТИЕ ЧЕРЕЗ 5 МИНУТ!**")
            voice_channel = bot.get_channel(VOICE_CHANNEL_ID)
            if voice_channel and isinstance(voice_channel, discord.VoiceChannel):
                try:
                    await voice_channel.send("📢 **Событие через 5 минут!** Все в сборе!")
                except:
                    pass

    task1 = bot.loop.create_task(notify_1h())
    task2 = bot.loop.create_task(notify_5m())
    ANNOUNCEMENT_TASKS[ann_id] = [task1, task2]

@bot.tree.command(name="анонс", description="Создать анонс события")
@app_commands.describe(
    channel="Канал для анонса",
    datetime_str="Дата и время (ЧЧ:ММ ДД.ММ)",
    content="Текст анонса"
)
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, datetime_str: str, content: str):
    if not has_any_role(interaction.user, CONFIRMATION_ROLES):
        await interaction.response.send_message("❌ Только лидерство может создавать анонсы.", ephemeral=True)
        return

    try:
        time_part, date_part = datetime_str.split(" ")
        hour, minute = map(int, time_part.split(":"))
        day, month = map(int, date_part.split("."))
        event_time = datetime(datetime.now().year, month, day, hour, minute)
        if event_time < datetime.now():
            event_time = event_time.replace(year=event_time.year + 1)
    except Exception as e:
        await interaction.response.send_message("❌ Неверный формат. Используйте: `ЧЧ:ММ ДД.ММ` (например: `20:00 25.12`)", ephemeral=True)
        return

    async with aiosqlite.connect("dominate_famq.db") as db:
        cursor = await db.execute(
            "INSERT INTO announcements (channel_id, event_time, content, creator_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (channel.id, event_time.isoformat(), content, interaction.user.id, datetime.utcnow().isoformat())
        )
        ann_id = cursor.lastrowid
        await db.commit()

    await schedule_announcement(ann_id, channel.id, event_time, content)
    await interaction.response.send_message(f"✅ Анонс создан! ID: `{ann_id}`", ephemeral=True)

@bot.tree.command(name="анонс_отмена", description="Отменить анонс по ID")
@app_commands.describe(announcement_id="ID анонса")
async def cancel_announcement(interaction: discord.Interaction, announcement_id: int):
    if not has_any_role(interaction.user, CONFIRMATION_ROLES):
        await interaction.response.send_message("❌ Только лидерство может отменять анонсы.", ephemeral=True)
        return

    if announcement_id in ANNOUNCEMENT_TASKS:
        for task in ANNOUNCEMENT_TASKS[announcement_id]:
            task.cancel()
        del ANNOUNCEMENT_TASKS[announcement_id]

    async with aiosqlite.connect("dominate_famq.db") as db:
        await db.execute("UPDATE announcements SET active = 0 WHERE id = ?", (announcement_id,))
        await db.commit()

    await interaction.response.send_message(f"✅ Анонс `{announcement_id}` отменён.", ephemeral=True)

# =============== АВТОМАТИЗАЦИЯ ===============
STATUSES = [
    "Играет на Majestic RolePlay",
    "Смотрит каптик",
    "Заполняет кадровый аудит",
    "дрочу на масончика"
]

async def change_status():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for status in STATUSES:
            await bot.change_presence(activity=discord.Game(name=status))
            await asyncio.sleep(30)

async def weekly_report_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        days_ahead = 6 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_sunday = (now + timedelta(days=days_ahead)).replace(hour=20, minute=0, second=0, microsecond=0)
        wait_seconds = (next_sunday - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            async with aiosqlite.connect("dominate_famq.db") as db:
                week_ago = (datetime.utcnow() - timedelta(weeks=1)).isoformat()
                cursor = await db.execute("SELECT COUNT(*) FROM actions WHERE action_type = 'accept' AND timestamp > ?", (week_ago,))
                accepted = (await cursor.fetchone())[0]
                cursor = await db.execute("SELECT COUNT(*) FROM actions WHERE action_type IN ('fire','auto_fire') AND timestamp > ?", (week_ago,))
                fired = (await cursor.fetchone())[0]
                cursor = await db.execute("SELECT COUNT(*) FROM warnings WHERE timestamp > ?", (week_ago,))
                warns = (await cursor.fetchone())[0]
                cursor = await db.execute("SELECT COUNT(*) FROM applications WHERE timestamp > ?", (week_ago,))
                apps = (await cursor.fetchone())[0]

            channel = bot.get_channel(REPORT_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="📊 Еженедельный отчёт DOMINATE FAMQ",
                    color=discord.Color.dark_red(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Принято", value=str(accepted), inline=True)
                embed.add_field(name="Уволено", value=str(fired), inline=True)
                embed.add_field(name="Предупреждений", value=str(warns), inline=True)
                embed.add_field(name="Заявок", value=str(apps), inline=True)
                embed.set_footer(text="Отчёт за последнюю неделю")
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Weekly report error: {e}")

TASKS_STARTED = False

@bot.event
async def on_ready():
    global TASKS_STARTED
    if TASKS_STARTED:
        return
    init_db()
    print(f'✅ {bot.user} запущен!')
    TASKS_STARTED = True
    # ... запуск задач

    # Загрузка активных анонсов
    try:
        async with aiosqlite.connect("dominate_famq.db") as db:
            cursor = await db.execute("SELECT id, channel_id, event_time, content FROM announcements WHERE active = 1")
            rows = await cursor.fetchall()
            for row in rows:
                ann_id, channel_id, event_time_str, content = row
                event_time = datetime.fromisoformat(event_time_str)
                if event_time > datetime.now():
                    await schedule_announcement(ann_id, channel_id, event_time, content)
    except Exception as e:
        print(f"Announcement load error: {e}")

    bot.loop.create_task(change_status())
    bot.loop.create_task(weekly_report_task())

# =============== ЗАПУСК ===============
if __name__ == "__main__":
    bot.run(TOKEN)
