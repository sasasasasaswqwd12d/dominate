import discord
from discord import app_commands, ui, Embed, ButtonStyle
from discord.ext import commands, tasks
import datetime
import json
import os
from dotenv import load_dotenv

# === КОНФИГУРАЦИЯ ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    print(" ошибка токен не найден")
    exit(1)

# Роли
ROLE_RECRUITER = 1444647329725677582
ROLE_FAMILY_MEMBER = 1449119840286675025

ROLES_RANKS = {
    8: 1449116921533431898,   # leader
    7: 1449116925220225094,   # owner
    6: 1449116939287793724,   # dep leader
    5: 1449116944589520926,   # high rank
    4: 1449116948011946005,   # recruit
    3: 1449116951732289596,   # main
    2: 1449116959550734488,   # test
    1: 1449116973010128957,   # academ
}

RANK_NAMES = {
    8: "Leader",
    7: "Owner",
    6: "Dep Leader",
    5: "High Rank",
    4: "Recruit",
    3: "Main",
    2: "Test",
    1: "Academ",
}

AUTHORIZED_RANKS = [8, 7, 6, 5, 4]
AUTHORIZED_FOR_FAMILY_ROSTER = [8, 7, 6, 5]
AUTHORIZED_FOR_CONFIRM_FIRE = [8, 7, 6, 5]

LOG_CHANNEL_ID = 1450181312769167500
VOICE_CHANNEL_ID = 1449117056019468419  # ID войса для обзвона

WARNINGS = {}
HISTORY = {}

WARNINGS_FILE = "warnings.json"
HISTORY_FILE = "history.json"

def load_data():
    global WARNINGS, HISTORY
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
            WARNINGS = {int(k): v for k, v in json.load(f).items()}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            HISTORY = {int(k): v for k, v in json.load(f).items()}

def save_data():
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(WARNINGS, f)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(HISTORY, f)

def get_user_rank(member):
    for rank, role_id in ROLES_RANKS.items():
        if discord.utils.get(member.roles, id=role_id):
            return rank
    return 0

def add_to_history(user_id, event: str):
    if user_id not in HISTORY:
        HISTORY[user_id] = []
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    HISTORY[user_id].append(f"[{timestamp}] {event}")
    save_data()

def get_user_roles_display(member):
    roles = []
    for rank, role_id in ROLES_RANKS.items():
        if discord.utils.get(member.roles, id=role_id):
            roles.append(RANK_NAMES[rank])
    if discord.utils.get(member.roles, id=ROLE_FAMILY_MEMBER):
        roles.append("Family Member")
    return ", ".join(roles) if roles else "—"

# === БОТ ===
intents = discord.Intents.default()
intents.members = True
intents.presences = True  # ← обязательно для отображения статуса

bot = commands.Bot(command_prefix="!", intents=intents)

statuses = [
    "Играет на Majestic RolePlay",
    "Смотрит каптик",
    "Занимается кадровым аудитом",
    "Дрочит на масончика"
]

@tasks.loop(seconds=30)
async def change_status():
    await bot.change_presence(activity=discord.Game(name=statuses[change_status.current_loop % len(statuses)]))

@bot.event
async def on_ready():
    load_data()
    change_status.start()
    await bot.tree.sync()
    print(f"✅ {bot.user} готов к работе!")

def has_required_role(member, allowed_roles: list):
    return any(discord.utils.get(member.roles, id=role_id) for role_id in allowed_roles)

async def send_log(embed: Embed):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=embed)

# === /набор ===
@bot.tree.command(name="набор", description="Отправить embed для набора в фамилию")
@app_commands.describe(channel="ID канала, куда будут приходить заявки")
async def команда_набор(interaction: discord.Interaction, channel: str):
    try:
        channel_id = int(channel.strip())
    except ValueError:
        await interaction.response.send_message("❌ Неверный ID канала.", ephemeral=True)
        return

    target_channel = bot.get_channel(channel_id)
    if not target_channel:
        await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)
        return

    if not has_required_role(interaction.user, [ROLE_RECRUITER]):
        await interaction.response.send_message("❌ У вас нет прав для использования этой команды.", ephemeral=True)
        return

    embed = Embed(
        title="🔥 ДОБРО ПОЖАЛОВАТЬ В DOMINATE FAMQ!",
        description=(
            "💀 Ты вошёл в криминальную империю, где лояльность — выше всего.\n\n"
            "📜 Наши принципы:\n"
            "✅ Возраст от 13 лет\n"
            "✅ Адекватность и уважение\n"
            "✅ Пунктуальность и ответственность\n"
            "✅ Командный дух — мы едины.\n\n"
            "🔥 Готов влиться в легенду? Подавай заявку!"
        ),
        color=0x00ff00
    )

    class ApplyButton(ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @ui.button(label="Подать заявку", style=ButtonStyle.green, emoji="📝")
        async def apply(self, inter: discord.Interaction, button: ui.Button):
            await inter.response.send_modal(ApplyModal(target_channel))

    await interaction.response.send_message(embed=embed, view=ApplyButton())

# === ИСПРАВЛЕННЫЙ MODAL ===
class ApplyModal(ui.Modal, title="Заявка в Dominate FamQ"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    nick = ui.TextInput(
        label="Ник | Static ID | Имя IRL",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    age = ui.TextInput(
        label="Возраст IRL",
        style=discord.TextStyle.short,
        required=True,
        max_length=3
    )
    families = ui.TextInput(
        label="Семьи на Majestic (фама | сервер)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )
    shooting = ui.TextInput(
        label="Откат стрельбы (Сайга/Тяга)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = Embed(
            title="📄 Новая заявка",
            color=0x2b2d31,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=False)
        embed.add_field(name="Пинг", value=interaction.user.mention, inline=False)
        embed.add_field(name="Ник | Static ID | Имя IRL", value=self.nick.value, inline=False)
        embed.add_field(name="Возраст IRL", value=self.age.value, inline=False)
        embed.add_field(name="Семьи на Majestic", value=self.families.value, inline=False)
        embed.add_field(name="Откат стрельбы", value=self.shooting.value, inline=False)

        view = ReviewView(interaction.user, self.target_channel)
        await self.target_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Заявка отправлена!", ephemeral=True)

# === ОСНОВНОЙ VIEW ЗАЯВКИ ===
class ReviewView(ui.View):
    def __init__(self, applicant: discord.Member, target_channel):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.target_channel = target_channel

    @ui.button(label="Вызвать на обзвон", style=ButtonStyle.blurple, emoji="📞")
    async def call_for_interview(self, inter: discord.Interaction, button: ui.Button):
        if not has_required_role(inter.user, [ROLES_RANKS[r] for r in AUTHORIZED_RANKS]):
            await inter.response.send_message("❌ У вас нет прав для этого действия.", ephemeral=True)
            return

        voice = inter.guild.get_channel(VOICE_CHANNEL_ID)
        mention = voice.mention if voice else f"<#{VOICE_CHANNEL_ID}>"

        try:
            await self.applicant.send(
                f"🔔 Вы вызваны на обзвон в **Dominate FamQ**!\n"
                f"Присоединяйтесь к голосовому каналу: {mention}"
            )
            msg = "✅ Кандидату отправлено уведомление об обзвоне."
        except discord.Forbidden:
            msg = "⚠️ Не удалось отправить ЛС (закрыты приватные сообщения)."

        await inter.response.send_message(msg, ephemeral=True)

        # Замена view на финальный выбор
        new_view = InterviewResultView(self.applicant, self.target_channel)
        await inter.message.edit(view=new_view)

    @ui.button(label="Принять", style=ButtonStyle.green, emoji="🟢")
    async def accept(self, inter: discord.Interaction, button: ui.Button):
        if not has_required_role(inter.user, [ROLES_RANKS[r] for r in AUTHORIZED_RANKS]):
            await inter.response.send_message("❌ У вас нет прав для этого действия.", ephemeral=True)
            return

        role = discord.utils.get(inter.guild.roles, id=ROLE_FAMILY_MEMBER)
        if role:
            try:
                await self.applicant.add_roles(role)
            except:
                pass

        embed = inter.message.embeds[0]
        embed.color = 0x00ff00
        embed.set_footer(text=f"Принято: {inter.user} ({inter.user.id})")
        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(embed=embed, view=self)

        log_embed = Embed(
            title="🟢 Приём",
            color=0x00ff00,
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="Кто принял", value=f"{inter.user.mention} | {inter.user.id}", inline=False)
        log_embed.add_field(name="Кого принял", value=f"{self.applicant.mention} | {self.applicant.id}", inline=False)
        static_id = embed.fields[2].value.split("|")[1].strip() if "|" in embed.fields[2].value else "—"
        log_embed.add_field(name="Static ID", value=static_id, inline=False)
        log_embed.add_field(name="Роли на момент приёма", value=get_user_roles_display(self.applicant), inline=False)
        await send_log(log_embed)
        add_to_history(self.applicant.id, f"Принят в фамилию (Static ID: {static_id})")

    @ui.button(label="Отказать", style=ButtonStyle.red, emoji="🔴")
    async def deny(self, inter: discord.Interaction, button: ui.Button):
        if not has_required_role(inter.user, [ROLES_RANKS[r] for r in AUTHORIZED_RANKS]):
            await inter.response.send_message("❌ У вас нет прав для этого действия.", ephemeral=True)
            return

        await inter.response.send_modal(DenyReasonModal(self.applicant, self))

# === VIEW ПОСЛЕ ОБЗВОНА ===
class InterviewResultView(ui.View):
    def __init__(self, applicant: discord.Member, target_channel):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.target_channel = target_channel

    @ui.button(label="Принять", style=ButtonStyle.green, emoji="🟢")
    async def accept(self, inter: discord.Interaction, button: ui.Button):
        if not has_required_role(inter.user, [ROLES_RANKS[r] for r in AUTHORIZED_RANKS]):
            await inter.response.send_message("❌ У вас нет прав для этого действия.", ephemeral=True)
            return

        role = discord.utils.get(inter.guild.roles, id=ROLE_FAMILY_MEMBER)
        if role:
            try:
                await self.applicant.add_roles(role)
            except:
                pass

        embed = inter.message.embeds[0]
        embed.color = 0x00ff00
        embed.set_footer(text=f"Принято после обзвона: {inter.user} ({inter.user.id})")
        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(embed=embed, view=self)

        log_embed = Embed(
            title="🟢 Приём (после обзвона)",
            color=0x00ff00,
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="Кто принял", value=f"{inter.user.mention} | {inter.user.id}", inline=False)
        log_embed.add_field(name="Кого принял", value=f"{self.applicant.mention} | {self.applicant.id}", inline=False)
        static_id = embed.fields[2].value.split("|")[1].strip() if "|" in embed.fields[2].value else "—"
        log_embed.add_field(name="Static ID", value=static_id, inline=False)
        log_embed.add_field(name="Роли на момент приёма", value=get_user_roles_display(self.applicant), inline=False)
        await send_log(log_embed)
        add_to_history(self.applicant.id, f"Принят после обзвона (Static ID: {static_id})")

    @ui.button(label="Отказать", style=ButtonStyle.red, emoji="🔴")
    async def deny(self, inter: discord.Interaction, button: ui.Button):
        if not has_required_role(inter.user, [ROLES_RANKS[r] for r in AUTHORIZED_RANKS]):
            await inter.response.send_message("❌ У вас нет прав для этого действия.", ephemeral=True)
            return

        await inter.response.send_modal(DenyReasonModal(self.applicant, self))

# === МОДАЛ ОТКАЗА ===
class DenyReasonModal(ui.Modal, title="Причина отказа"):
    def __init__(self, applicant, view):
        super().__init__()
        self.applicant = applicant
        self.view = view

    reason = ui.TextInput(
        label="Причина отказа",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, inter: discord.Interaction):
        try:
            await self.applicant.send(f"❌ Ваша заявка в Dominate FamQ отклонена.\n**Причина:** {self.reason.value}")
        except:
            pass

        embed = inter.message.embeds[0]
        embed.color = 0xff0000
        embed.set_footer(text=f"Отказано: {inter.user} ({inter.user.id}) — {self.reason.value}")
        for item in self.view.children:
            item.disabled = True
        await inter.response.edit_message(embed=embed, view=self.view)

        log_embed = Embed(
            title="🔴 Отказ в приёме",
            color=0xff0000,
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="Кто отказал", value=f"{inter.user.mention} | {inter.user.id}", inline=False)
        log_embed.add_field(name="Кому отказано", value=f"{self.applicant.mention} | {self.applicant.id}", inline=False)
        log_embed.add_field(name="Причина", value=self.reason.value, inline=False)
        await send_log(log_embed)
        add_to_history(self.applicant.id, f"Отказ в приёме: {self.reason.value}")

# === ДЕКОРАТОР ПРОВЕРКИ РАНГА ===
def require_rank(min_ranks: list):
    def predicate(interaction: discord.Interaction) -> bool:
        user_rank = get_user_rank(interaction.user)
        return user_rank in min_ranks
    return app_commands.check(predicate)

# === /принятие ===
@bot.tree.command(name="принятие", description="Принять участника в фамилию (ручной приём)")
@app_commands.describe(member="Кого принимаете", static_id="Static ID", reason="Причина приёма")
@require_rank(AUTHORIZED_RANKS)
async def команда_принятие(interaction: discord.Interaction, member: discord.Member, static_id: str, reason: str):
    role = discord.utils.get(interaction.guild.roles, id=ROLE_FAMILY_MEMBER)
    if role:
        await member.add_roles(role)

    embed = Embed(
        title="🟢 Приём",
        color=0x00ff00,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Кто принял", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Кого принял", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Дата и время", value=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
    embed.add_field(name="Подробности", value=(
        f"**Причина:** {reason}\n"
        f"**Роли на момент приёма:** {get_user_roles_display(member)}\n"
        f"**Static ID:** {static_id}"
    ), inline=False)

    await interaction.response.send_message(embed=embed)
    log_embed = embed.copy()
    log_embed.title = "🟢 Ручной приём"
    await send_log(log_embed)
    add_to_history(member.id, f"Ручной приём (Static ID: {static_id}) — {reason}")

# === /увольнение ===
@bot.tree.command(name="увольнение", description="Уволить участника из фамилии")
@app_commands.describe(member="Кого увольняете", static_id="Static ID", reason="Причина увольнения")
@require_rank(AUTHORIZED_RANKS)
async def команда_увольнение(interaction: discord.Interaction, member: discord.Member, static_id: str, reason: str):
    embed = Embed(
        title="❓ Подтверждение увольнения",
        description=f"Вы действительно хотите уволить {member.mention}?",
        color=0xffa500
    )
    await interaction.response.send_message(embed=embed, view=ConfirmFireView(member, static_id, reason, interaction.user), ephemeral=True)

class ConfirmFireView(ui.View):
    def __init__(self, member, static_id, reason, author):
        super().__init__(timeout=60)
        self.member = member
        self.static_id = static_id
        self.reason = reason
        self.author = author

    @ui.button(label="Подтвердить", style=ButtonStyle.danger, emoji="🔥")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if not has_required_role(interaction.user, [ROLES_RANKS[r] for r in AUTHORIZED_FOR_CONFIRM_FIRE]):
            await interaction.response.send_message("❌ Только Leader+ могут подтверждать увольнения.", ephemeral=True)
            return

        roles_to_remove = [discord.utils.get(interaction.guild.roles, id=rid) for rid in ROLES_RANKS.values()]
        family_role = discord.utils.get(interaction.guild.roles, id=ROLE_FAMILY_MEMBER)
        if family_role:
            roles_to_remove.append(family_role)
        roles_to_remove = [r for r in roles_to_remove if r and r in self.member.roles]

        if roles_to_remove:
            await self.member.remove_roles(*roles_to_remove)

        embed = Embed(
            title="🔴 Увольнение",
            color=0xff0000,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Кто уволил", value=f"{self.author.mention} | {self.author.id}", inline=False)
        embed.add_field(name="Кого уволил", value=f"{self.member.mention} | {self.member.id}", inline=False)
        embed.add_field(name="Дата и время", value=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)
        embed.add_field(name="Подробности", value=(
            f"**Причина:** {self.reason}\n"
            f"**Роли на момент увольнения:** {get_user_roles_display(self.member)}\n"
            f"**Static ID:** {self.static_id}"
        ), inline=False)

        await interaction.response.edit_message(embed=embed, view=None)
        await send_log(embed.copy())
        try:
            await self.member.send(f"🔴 Вы были уволены из Dominate FamQ.\n**Причина:** {self.reason}")
        except:
            pass
        add_to_history(self.member.id, f"Уволен (Static ID: {self.static_id}) — {self.reason}")

        if self.member.id in WARNINGS:
            del WARNINGS[self.member.id]
            save_data()

    @ui.button(label="Отмена", style=ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="❌ Увольнение отменено.", embed=None, view=None)

# === /повышение ===
@bot.tree.command(name="повышение", description="Повысить участника")
@app_commands.describe(
    member="Кого повышаете",
    static_id="Static ID",
    current_rank="Текущий ранг (1-8)",
    new_rank="Ранг на который повышаете (1-8)",
    reason="Причина повышения"
)
@require_rank(AUTHORIZED_RANKS)
async def команда_повышение(
    interaction: discord.Interaction,
    member: discord.Member,
    static_id: str,
    current_rank: app_commands.Range[int, 1, 8],
    new_rank: app_commands.Range[int, 1, 8],
    reason: str
):
    if new_rank <= current_rank:
        await interaction.response.send_message("❌ Новый ранг должен быть выше текущего.", ephemeral=True)
        return

    old_role = discord.utils.get(interaction.guild.roles, id=ROLES_RANKS.get(current_rank))
    new_role = discord.utils.get(interaction.guild.roles, id=ROLES_RANKS.get(new_rank))
    if not old_role or not new_role:
        await interaction.response.send_message("❌ Ошибка рангов.", ephemeral=True)
        return

    if old_role in member.roles:
        await member.remove_roles(old_role)
    await member.add_roles(new_role)

    embed = Embed(
        title="🔼 Отчёт на повышение",
        color=0x00ff00,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Причина повышения", value=reason, inline=False)
    embed.add_field(name="Повышен", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Кто повысил", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Дата и время", value=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)

    await interaction.response.send_message(embed=embed)
    log_embed = embed.copy()
    log_embed.title = "🔼 Повышение"
    await send_log(log_embed)
    add_to_history(member.id, f"Повышен с {RANK_NAMES[current_rank]} до {RANK_NAMES[new_rank]} — {reason}")

# === /понижение ===
@bot.tree.command(name="понижение", description="Понизить участника")
@app_commands.describe(
    member="Кого понижаете",
    static_id="Static ID",
    current_rank="Текущий ранг (1-8)",
    new_rank="Ранг на который понижаете (1-8)",
    reason="Причина понижения"
)
@require_rank(AUTHORIZED_RANKS)
async def команда_понижение(
    interaction: discord.Interaction,
    member: discord.Member,
    static_id: str,
    current_rank: app_commands.Range[int, 1, 8],
    new_rank: app_commands.Range[int, 1, 8],
    reason: str
):
    if new_rank >= current_rank:
        await interaction.response.send_message("❌ Новый ранг должен быть ниже текущего.", ephemeral=True)
        return

    old_role = discord.utils.get(interaction.guild.roles, id=ROLES_RANKS.get(current_rank))
    new_role = discord.utils.get(interaction.guild.roles, id=ROLES_RANKS.get(new_rank))
    if not old_role or not new_role:
        await interaction.response.send_message("❌ Ошибка рангов.", ephemeral=True)
        return

    if old_role in member.roles:
        await member.remove_roles(old_role)
    await member.add_roles(new_role)

    embed = Embed(
        title="🔽 Отчёт на понижение",
        color=0xffff00,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Причина понижения", value=reason, inline=False)
    embed.add_field(name="Понижен", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Кто понизил", value=f"{interaction.user.mention} | {interaction.user.id}", inline=False)
    embed.add_field(name="Дата и время", value=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), inline=False)

    await interaction.response.send_message(embed=embed)
    log_embed = embed.copy()
    log_embed.title = "🔽 Понижение"
    await send_log(log_embed)
    add_to_history(member.id, f"Понижен с {RANK_NAMES[current_rank]} до {RANK_NAMES[new_rank]} — {reason}")

# === /история ===
@bot.tree.command(name="история", description="Показать историю участника")
@app_commands.describe(member="Чью историю показать")
@require_rank(AUTHORIZED_RANKS)
async def команда_история(interaction: discord.Interaction, member: discord.Member):
    events = HISTORY.get(member.id, [])
    desc = "\n".join(events[-20:]) if events else "История пуста."
    embed = Embed(
        title=f"📜 История {member.display_name}",
        description=desc,
        color=0x2b2d31
    )
    await interaction.response.send_message(embed=embed)

# === /состав_фамы — С ОНЛАЙН СТАТУСОМ ===
@bot.tree.command(name="состав_фамы", description="Показать состав фамилии")
@require_rank(AUTHORIZED_FOR_FAMILY_ROSTER)
async def команда_состав_фамы(interaction: discord.Interaction):
    embed = Embed(title="👥 Состав Dominate FamQ", color=0x2b2d31)
    total = 0

    def status_emoji(m):
        if m.status == discord.Status.online:
            return "🟢"
        elif m.status == discord.Status.idle:
            return "🟡"
        elif m.status == discord.Status.dnd:
            return "🔴"
        else:
            return "⚪"

    for rank in sorted(ROLES_RANKS.keys(), reverse=True):
        role = discord.utils.get(interaction.guild.roles, id=ROLES_RANKS[rank])
        if not role:
            continue
        members = [m for m in role.members if not m.bot]
        if not members:
            continue
        total += len(members)

        # Сортируем: онлайн первыми
        sorted_members = sorted(members, key=lambda x: x.status == discord.Status.offline)

        member_list = "\n".join(
            f"{i+1}. {m.mention} {status_emoji(m)}"
            for i, m in enumerate(sorted_members[:20])
        )
        embed.add_field(
            name=f"{RANK_NAMES[rank]} ({len(members)})",
            value=member_list,
            inline=False
        )

    family_role = discord.utils.get(interaction.guild.roles, id=ROLE_FAMILY_MEMBER)
    if family_role:
        extra = [m for m in family_role.members if not m.bot and get_user_rank(m) == 0]
        if extra:
            total += len(extra)
            sorted_extra = sorted(extra, key=lambda x: x.status == discord.Status.offline)
            member_list = "\n".join(f"{i+1}. {m.mention} {status_emoji(m)}" for i, m in enumerate(sorted_extra[:10]))
            embed.add_field(name="Family Members (без ранга)", value=member_list, inline=False)

    embed.set_footer(text=f"Общее количество: {total}")
    await interaction.response.send_message(embed=embed)

# === /инструкция ===
@bot.tree.command(name="инструкция", description="Получить инструкцию по боту")
@require_rank(AUTHORIZED_RANKS)
async def команда_инструкция(interaction: discord.Interaction):
    embed = Embed(
        title="📘 Инструкция по Masonchik Bot",
        description=(
            "Бот для управления кадрами в Dominate FamQ.\n"
            "Автор: **Mason**\n\n"
            "**Команды:**\n"
            "/набор — запустить набор\n"
            "/принятие @user static причина — принять\n"
            "/увольнение @user static причина — уволить\n"
            "/повышение /понижение — управление рангами\n"
            "/история @user — посмотреть историю\n"
            "/состав_фамы — список участников с онлайн-статусом\n"
            "/предупреждение @user причина — выдать предупреждение (3 = увольнение)\n\n"
            "Все действия логируются."
        ),
        color=0x2b2d31
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /предупреждение ===
@bot.tree.command(name="предупреждение", description="Выдать предупреждение участнику")
@app_commands.describe(member="Кому выдать", reason="Причина")
@require_rank(AUTHORIZED_RANKS)
async def команда_предупреждение(interaction: discord.Interaction, member: discord.Member, reason: str):
    user_id = member.id
    WARNINGS[user_id] = WARNINGS.get(user_id, 0) + 1
    count = WARNINGS[user_id]
    save_data()

    embed = Embed(
        title="⚠️ Предупреждение",
        color=0xffa500,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Кому", value=f"{member.mention} | {member.id}", inline=False)
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.add_field(name="Всего предупреждений", value=str(count), inline=False)
    await interaction.response.send_message(embed=embed)
    await send_log(embed.copy())
    add_to_history(member.id, f"Предупреждение #{count}: {reason}")

    if count >= 3:
        roles_to_remove = [discord.utils.get(interaction.guild.roles, id=rid) for rid in ROLES_RANKS.values()]
        family_role = discord.utils.get(interaction.guild.roles, id=ROLE_FAMILY_MEMBER)
        if family_role:
            roles_to_remove.append(family_role)
        roles_to_remove = [r for r in roles_to_remove if r and r in member.roles]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        fire_embed = Embed(
            title="🔴 Автоматическое увольнение",
            description=f"{member.mention} уволен после 3 предупреждений.",
            color=0xff0000
        )
        await interaction.followup.send(embed=fire_embed)

        log_embed2 = Embed(title="🔴 Авто-увольнение", color=0xff0000)
        log_embed2.add_field(name="Кого уволили", value=f"{member.mention} | {member.id}", inline=False)
        log_embed2.add_field(name="Причина", value="3 предупреждения", inline=False)
        await send_log(log_embed2)
        add_to_history(member.id, "Автоматическое увольнение (3 предупреждения)")
        del WARNINGS[user_id]
        save_data()

# === ЗАПУСК ===
if __name__ == "__main__":
    bot.run(TOKEN)

print(input(""))