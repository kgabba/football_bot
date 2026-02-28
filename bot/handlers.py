"""Telegram bot handlers: multi-select players, then distribute by teams, call core, send photos."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .players import load_players, build_lineup_csv, PlayerRecord
from .state import get_state, clear_state
from .core_client import generate_lineups, get_image_bytes, resize_for_telegram

logger = logging.getLogger(__name__)

# Загружаем один раз при старте (при необходимости можно перечитывать)
_players: list[PlayerRecord] = []


def get_players() -> list[PlayerRecord]:
    global _players
    if not _players:
        _players = load_players()
    return _players


def _keyboard_select_players(selected: set[int]) -> InlineKeyboardMarkup:
    players = get_players()
    buttons = []
    row = []
    for i, p in enumerate(players):
        label = f"{'✓ ' if i in selected else ''}{p.name} {p.surname}"
        row.append(InlineKeyboardButton(label, callback_data=f"p_{i}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Готово — перейти к распределению", callback_data="done")])
    return InlineKeyboardMarkup(buttons)


def _keyboard_teams() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Красная (1)", callback_data="t_1"),
            InlineKeyboardButton("🔵 Синяя (2)", callback_data="t_2"),
        ],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    clear_state(update.effective_user.id)
    players = get_players()
    if not players:
        await update.message.reply_text(
            "База игроков пуста. Добавь data/players.csv в папку бота."
        )
        return
    await update.message.reply_text(
        "Выбери, кто сегодня в игре. Нажимай на игроков — галочка отметит участников. "
        "Потом нажми «Готово».",
        reply_markup=_keyboard_select_players(set()),
    )


async def callback_toggle_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.message or not update.effective_user:
        return
    await query.answer()
    if not query.data.startswith("p_"):
        return
    try:
        idx = int(query.data[2:])
    except ValueError:
        return
    players = get_players()
    if idx < 0 or idx >= len(players):
        return
    state = get_state(update.effective_user.id)
    if state["selected"] is None:
        state["selected"] = set()
    if idx in state["selected"]:
        state["selected"].remove(idx)
    else:
        state["selected"].add(idx)
    await query.edit_message_text(
        "Отметь игроков, кто в игре. Потом нажми «Готово».",
        reply_markup=_keyboard_select_players(state["selected"]),
    )


async def callback_done_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or query.data != "done" or not query.message or not update.effective_user:
        return
    state = get_state(update.effective_user.id)
    selected = state.get("selected") or set()
    if len(selected) < 2:
        await query.answer("Выбери минимум 2 игроков.", show_alert=True)
        return
    await query.answer()
    state["step"] = "distribute"
    state["selected_list"] = sorted(selected)
    state["distribution"] = []
    state["current_index"] = 0
    players = get_players()
    idx = state["selected_list"][0]
    p = players[idx]
    n = len(state["selected_list"])
    await query.edit_message_text(
        f"Распределение по командам (1 из {n}):\n{p.name} {p.surname} — в какую команду?",
        reply_markup=_keyboard_teams(),
    )


async def callback_assign_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("t_") or not query.message or not update.effective_user:
        return
    await query.answer()
    try:
        team = int(query.data[2:])
    except ValueError:
        return
    if team not in (1, 2):
        return
    state = get_state(update.effective_user.id)
    if state.get("step") != "distribute":
        return
    sel_list = state["selected_list"]
    cur = state["current_index"]
    if cur >= len(sel_list):
        return
    player_idx = sel_list[cur]
    state["distribution"].append((player_idx, team))
    state["current_index"] = cur + 1
    players = get_players()
    n = len(sel_list)
    if state["current_index"] == n:
        # Все распределены — формируем CSV, дергаем core, шлём фото
        await query.edit_message_text("Формирую составы…")
        try:
            csv_body = build_lineup_csv(players, state["distribution"])
            resp = await generate_lineups(csv_body)
        except Exception as e:
            logger.exception("Core request failed")
            await query.edit_message_text(f"Ошибка при генерации составов: {e}")
            clear_state(update.effective_user.id)
            return
        if resp.get("status") != "ok":
            await query.edit_message_text(
                resp.get("message", "Ошибка") + "\n" + resp.get("details", "")
            )
            clear_state(update.effective_user.id)
            return
        teams = resp.get("teams") or []
        sent = 0
        errors = []
        for t in teams:
            url = t.get("image_url")
            if not url:
                continue
            try:
                data = await get_image_bytes(url)
                # Ужимаем изображение: меньше размер — быстрее загрузка в Telegram, нет таймаутов
                data = resize_for_telegram(data)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=data,
                    caption=f"Состав команды {t.get('team', '?')}",
                )
                sent += 1
            except Exception as e:
                logger.exception("Send photo failed")
                errors.append(str(e))
        chat_id = update.effective_chat.id
        if sent == len(teams):
            await context.bot.send_message(chat_id, "Готово! Составы выше.")
        elif sent > 0:
            await context.bot.send_message(
                chat_id,
                f"Отправлено {sent} из {len(teams)}. Ошибки: {errors[0][:150]}",
            )
        elif errors:
            await context.bot.send_message(
                chat_id,
                f"Не удалось отправить фото (таймаут загрузки): {errors[0][:150]}",
            )
        try:
            await query.edit_message_text("Готово.")
        except Exception:
            pass
        clear_state(update.effective_user.id)
        return
    # Следующий игрок
    next_idx = state["selected_list"][state["current_index"]]
    p = players[next_idx]
    await query.edit_message_text(
        f"Распределение по командам ({state['current_index'] + 1} из {n}):\n{p.name} {p.surname} — в какую команду?",
        reply_markup=_keyboard_teams(),
    )


def register_handlers(application) -> None:
    from telegram.ext import CommandHandler, CallbackQueryHandler
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(callback_toggle_player, pattern="^p_\\d+$"))
    application.add_handler(CallbackQueryHandler(callback_done_players, pattern="^done$"))
    application.add_handler(CallbackQueryHandler(callback_assign_team, pattern="^t_[12]$"))
