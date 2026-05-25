import asyncio
import json
import os
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATA_FILE = "data.json"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id: int) -> dict:
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"stats": {}, "combos": {}}
        save_data(data)
    return data[uid]

def save_user(user_id: int, user_data: dict):
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

# ─── FSM States ───────────────────────────────────────────────────────────────

class AddStat(StatesGroup):
    waiting_name = State()
    waiting_dice = State()
    waiting_modifier = State()

class AddCombo(StatesGroup):
    waiting_name = State()
    waiting_stats = State()

class DeleteStat(StatesGroup):
    waiting_choice = State()

class DeleteCombo(StatesGroup):
    waiting_choice = State()

# ─── Keyboards ────────────────────────────────────────────────────────────────

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Бросить кубик", callback_data="menu_roll")],
        [InlineKeyboardButton(text="⚔️ Комбо-бросок", callback_data="menu_combo")],
        [InlineKeyboardButton(text="📋 Мои характеристики", callback_data="menu_stats")],
        [InlineKeyboardButton(text="➕ Добавить характеристику", callback_data="menu_add_stat")],
        [InlineKeyboardButton(text="🔗 Добавить комбо", callback_data="menu_add_combo")],
        [InlineKeyboardButton(text="🗑 Удалить характеристику", callback_data="menu_del_stat")],
        [InlineKeyboardButton(text="🗑 Удалить комбо", callback_data="menu_del_combo")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def dice_type_kb():
    dice_types = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]
    buttons = [[InlineKeyboardButton(text=d, callback_data=f"dice_{d}")] for d in dice_types]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def stats_roll_kb(user_id: int):
    user = get_user(user_id)
    stats = user.get("stats", {})
    if not stats:
        return None
    buttons = []
    for name, info in stats.items():
        label = f"🎲 {name} ({info['dice']}{'%+d' % info['modifier'] if info['modifier'] != 0 else ''})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"roll_stat_{name}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def combo_roll_kb(user_id: int):
    user = get_user(user_id)
    combos = user.get("combos", {})
    if not combos:
        return None
    buttons = []
    for name in combos:
        buttons.append([InlineKeyboardButton(text=f"⚔️ {name}", callback_data=f"roll_combo_{name}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def stats_select_kb(user_id: int, selected: list):
    user = get_user(user_id)
    stats = user.get("stats", {})
    buttons = []
    for name in stats:
        check = "✅ " if name in selected else ""
        buttons.append([InlineKeyboardButton(text=f"{check}{name}", callback_data=f"combo_pick_{name}")])
    buttons.append([InlineKeyboardButton(text="✔️ Готово", callback_data="combo_done")])
    buttons.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def del_stat_kb(user_id: int):
    user = get_user(user_id)
    stats = user.get("stats", {})
    if not stats:
        return None
    buttons = []
    for name in stats:
        buttons.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_stat_{name}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def del_combo_kb(user_id: int):
    user = get_user(user_id)
    combos = user.get("combos", {})
    if not combos:
        return None
    buttons = []
    for name in combos:
        buttons.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_combo_{name}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── Dice rolling ─────────────────────────────────────────────────────────────

def roll_dice(dice_str: str) -> tuple[int, int]:
    """Returns (sides, result)"""
    sides = int(dice_str[1:])
    return sides, random.randint(1, sides)

def roll_stat(stat_info: dict) -> str:
    sides, result = roll_dice(stat_info["dice"])
    mod = stat_info["modifier"]
    total = result + mod
    mod_str = f" {'+' if mod >= 0 else ''}{mod}" if mod != 0 else ""
    return f"🎲 {stat_info['dice']}: **{result}**{mod_str} = **{total}**"

# ─── Handlers ─────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    get_user(msg.from_user.id)
    name = msg.from_user.first_name
    await msg.answer(
        f"⚔️ Добро пожаловать, {name}!\n\n"
        f"Я бот для бросания кубиков D&D.\n"
        f"Настрой свои характеристики и бросай прямо из меню!\n\n"
        f"Каждый игрок настраивает своё — данные сохраняются по твоему Telegram-аккаунту.",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("menu"))
async def cmd_menu(msg: Message):
    await msg.answer("📜 Главное меню:", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("📜 Главное меню:", reply_markup=main_menu_kb())

# ── View stats ────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_stats")
async def show_stats(cb: CallbackQuery):
    user = get_user(cb.from_user.id)
    stats = user.get("stats", {})
    combos = user.get("combos", {})

    if not stats:
        text = "📋 У тебя пока нет характеристик.\nДобавь через меню!"
    else:
        lines = ["📋 *Твои характеристики:*\n"]
        for name, info in stats.items():
            mod = info["modifier"]
            mod_str = f" ({'+' if mod >= 0 else ''}{mod})" if mod != 0 else ""
            lines.append(f"• **{name}** — {info['dice']}{mod_str}")
        if combos:
            lines.append("\n⚔️ *Комбо:*")
            for cname, cstats in combos.items():
                lines.append(f"• **{cname}**: {' + '.join(cstats)}")
        text = "\n".join(lines)

    await cb.message.edit_text(text, reply_markup=back_kb(), parse_mode="Markdown")

# ── Roll stat ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_roll")
async def menu_roll(cb: CallbackQuery):
    kb = stats_roll_kb(cb.from_user.id)
    if not kb:
        await cb.answer("У тебя нет характеристик! Добавь через меню.", show_alert=True)
        return
    await cb.message.edit_text("🎲 Выбери характеристику для броска:", reply_markup=kb)

@dp.callback_query(F.data.startswith("roll_stat_"))
async def do_roll_stat(cb: CallbackQuery):
    stat_name = cb.data[len("roll_stat_"):]
    user = get_user(cb.from_user.id)
    stats = user.get("stats", {})

    if stat_name not in stats:
        await cb.answer("Характеристика не найдена.", show_alert=True)
        return

    result_text = roll_stat(stats[stat_name])
    player = cb.from_user.first_name

    await cb.message.answer(
        f"🎯 *{player}* бросает **{stat_name}**:\n{result_text}",
        parse_mode="Markdown"
    )
    await cb.answer()

# ── Roll combo ────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_combo")
async def menu_combo(cb: CallbackQuery):
    kb = combo_roll_kb(cb.from_user.id)
    if not kb:
        await cb.answer("У тебя нет комбо! Добавь через меню.", show_alert=True)
        return
    await cb.message.edit_text("⚔️ Выбери комбо-бросок:", reply_markup=kb)

@dp.callback_query(F.data.startswith("roll_combo_"))
async def do_roll_combo(cb: CallbackQuery):
    combo_name = cb.data[len("roll_combo_"):]
    user = get_user(cb.from_user.id)
    combos = user.get("combos", {})
    stats = user.get("stats", {})

    if combo_name not in combos:
        await cb.answer("Комбо не найдено.", show_alert=True)
        return

    combo_stats = combos[combo_name]
    player = cb.from_user.first_name
    lines = [f"⚔️ *{player}* бросает комбо **{combo_name}**:\n"]
    grand_total = 0

    for stat_name in combo_stats:
        if stat_name in stats:
            info = stats[stat_name]
            sides, result = roll_dice(info["dice"])
            mod = info["modifier"]
            total = result + mod
            grand_total += total
            mod_str = f" {'+' if mod >= 0 else ''}{mod}" if mod != 0 else ""
            lines.append(f"• *{stat_name}* ({info['dice']}): {result}{mod_str} = **{total}**")

    lines.append(f"\n🏆 Итого: **{grand_total}**")

    await cb.message.answer("\n".join(lines), parse_mode="Markdown")
    await cb.answer()

# ── Add stat ──────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_add_stat")
async def menu_add_stat(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddStat.waiting_name)
    await cb.message.edit_text(
        "➕ *Добавление характеристики*\n\nВведи название (например: Атака молота, Спасбросок воли):",
        reply_markup=back_kb(),
        parse_mode="Markdown"
    )

@dp.message(AddStat.waiting_name)
async def add_stat_name(msg: Message, state: FSMContext):
    await state.update_data(stat_name=msg.text.strip())
    await state.set_state(AddStat.waiting_dice)
    await msg.answer(
        f"✅ Название: *{msg.text.strip()}*\n\nТеперь выбери тип кубика:",
        reply_markup=dice_type_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(AddStat.waiting_dice, F.data.startswith("dice_"))
async def add_stat_dice(cb: CallbackQuery, state: FSMContext):
    dice = cb.data[5:]
    await state.update_data(dice=dice)
    await state.set_state(AddStat.waiting_modifier)
    await cb.message.edit_text(
        f"✅ Кубик: *{dice}*\n\nВведи модификатор (целое число, например: 3 или -1 или 0):",
        reply_markup=back_kb(),
        parse_mode="Markdown"
    )

@dp.message(AddStat.waiting_modifier)
async def add_stat_modifier(msg: Message, state: FSMContext):
    try:
        modifier = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введи целое число (например: 0, 3, -2)")
        return

    data = await state.get_data()
    user = get_user(msg.from_user.id)
    user["stats"][data["stat_name"]] = {
        "dice": data["dice"],
        "modifier": modifier
    }
    save_user(msg.from_user.id, user)
    await state.clear()

    mod_str = f" ({'+' if modifier >= 0 else ''}{modifier})" if modifier != 0 else ""
    await msg.answer(
        f"✅ Характеристика добавлена!\n\n*{data['stat_name']}* — {data['dice']}{mod_str}",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

# ── Add combo ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_add_combo")
async def menu_add_combo(cb: CallbackQuery, state: FSMContext):
    user = get_user(cb.from_user.id)
    if not user.get("stats"):
        await cb.answer("Сначала добавь характеристики!", show_alert=True)
        return
    await state.set_state(AddCombo.waiting_name)
    await cb.message.edit_text(
        "🔗 *Добавление комбо*\n\nВведи название комбо (например: Удар молота, Дальний выстрел):",
        reply_markup=back_kb(),
        parse_mode="Markdown"
    )

@dp.message(AddCombo.waiting_name)
async def add_combo_name(msg: Message, state: FSMContext):
    await state.update_data(combo_name=msg.text.strip(), selected=[])
    await state.set_state(AddCombo.waiting_stats)
    user = get_user(msg.from_user.id)
    await msg.answer(
        f"✅ Название: *{msg.text.strip()}*\n\nВыбери характеристики для комбо (нажимай, затем «Готово»):",
        reply_markup=stats_select_kb(msg.from_user.id, []),
        parse_mode="Markdown"
    )

@dp.callback_query(AddCombo.waiting_stats, F.data.startswith("combo_pick_"))
async def combo_pick_stat(cb: CallbackQuery, state: FSMContext):
    stat = cb.data[len("combo_pick_"):]
    data = await state.get_data()
    selected = data.get("selected", [])
    if stat in selected:
        selected.remove(stat)
    else:
        selected.append(stat)
    await state.update_data(selected=selected)
    await cb.message.edit_reply_markup(reply_markup=stats_select_kb(cb.from_user.id, selected))
    await cb.answer()

@dp.callback_query(AddCombo.waiting_stats, F.data == "combo_done")
async def combo_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected", [])
    if not selected:
        await cb.answer("Выбери хотя бы одну характеристику!", show_alert=True)
        return

    user = get_user(cb.from_user.id)
    user["combos"][data["combo_name"]] = selected
    save_user(cb.from_user.id, user)
    await state.clear()

    await cb.message.edit_text(
        f"✅ Комбо *{data['combo_name']}* создано!\nСостав: {' + '.join(selected)}",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

# ── Delete stat ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_del_stat")
async def menu_del_stat(cb: CallbackQuery):
    kb = del_stat_kb(cb.from_user.id)
    if not kb:
        await cb.answer("Нет характеристик для удаления.", show_alert=True)
        return
    await cb.message.edit_text("🗑 Какую характеристику удалить?", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_stat_"))
async def do_del_stat(cb: CallbackQuery):
    stat_name = cb.data[len("del_stat_"):]
    user = get_user(cb.from_user.id)
    if stat_name in user["stats"]:
        del user["stats"][stat_name]
        # also remove from combos
        for cname in list(user["combos"].keys()):
            if stat_name in user["combos"][cname]:
                user["combos"][cname].remove(stat_name)
            if not user["combos"][cname]:
                del user["combos"][cname]
        save_user(cb.from_user.id, user)
        await cb.message.edit_text(
            f"✅ Характеристика *{stat_name}* удалена.",
            reply_markup=main_menu_kb(),
            parse_mode="Markdown"
        )
    else:
        await cb.answer("Не найдено.", show_alert=True)

# ── Delete combo ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_del_combo")
async def menu_del_combo(cb: CallbackQuery):
    kb = del_combo_kb(cb.from_user.id)
    if not kb:
        await cb.answer("Нет комбо для удаления.", show_alert=True)
        return
    await cb.message.edit_text("🗑 Какое комбо удалить?", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_combo_"))
async def do_del_combo(cb: CallbackQuery):
    combo_name = cb.data[len("del_combo_"):]
    user = get_user(cb.from_user.id)
    if combo_name in user["combos"]:
        del user["combos"][combo_name]
        save_user(cb.from_user.id, user)
        await cb.message.edit_text(
            f"✅ Комбо *{combo_name}* удалено.",
            reply_markup=main_menu_kb(),
            parse_mode="Markdown"
        )
    else:
        await cb.answer("Не найдено.", show_alert=True)

# ─── Run ──────────────────────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
