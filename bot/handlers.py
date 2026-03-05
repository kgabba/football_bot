"""Бот: стартовое меню (админ-панель / капитанская дуэль), голосование, драфт, отправка составов в группу."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .config import GROUP_CHAT_ID_INT, is_admin
from .players import load_players, build_lineup_csv, get_match_player_indices as players_match_indices, PlayerRecord
from .state import get_state, clear_state
from .match_state import (
    is_voting_active,
    get_voted_user_ids,
    get_match_player_indices,
    get_match_user_ids,
    has_match_players,
    start_voting,
    add_vote,
    finish_voting,
    set_active_poll_id,
    get_active_poll_id,
    get_captain_queue,
    add_captain_candidate,
    set_draft,
    draft_get_state,
    draft_pick,
    draft_set_group_message_id,
    clear_draft,
)
from .core_client import generate_lineups, get_image_bytes, resize_for_telegram

logger = logging.getLogger(__name__)

_players: list[PlayerRecord] = []


def get_players() -> list[PlayerRecord]:
    global _players
    if not _players:
        _players = load_players()
    return _players


# --- Старт и меню ---

def _start_keyboard(update: Update) -> InlineKeyboardMarkup:
    user = update.effective_user
    show_admin = is_admin(user.username if user else None, user.id if user else None)
    buttons = []
    if show_admin:
        buttons.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="menu_admin")])
    buttons.append([InlineKeyboardButton("⚔️ Капитанская дуэль", callback_data="menu_captain")])
    return InlineKeyboardMarkup(buttons)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    clear_state(update.effective_user.id)
    group_ok = GROUP_CHAT_ID_INT is not None
    text = "Выбери действие:"
    if not group_ok:
        text += "\n\n⚠️ GROUP_CHAT_ID не задан — голосование и драфт в группе работать не будут."
    await update.message.reply_text(text, reply_markup=_start_keyboard(update))


async def callback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    await query.answer()
    data = query.data
    if data == "menu_admin":
        if not is_admin(update.effective_user.username, update.effective_user.id):
            await query.edit_message_text("Нет доступа.")
            return
        # Админ-панель
        voting = is_voting_active()
        lines = ["Админ-панель.", "Начни голосование в группе и заверши его кнопкой ниже."]
        buttons = []
        if not voting:
            buttons.append([InlineKeyboardButton("📢 Начать голосование", callback_data="admin_start_vote")])
        else:
            buttons.append([InlineKeyboardButton("✅ Завершить голосование", callback_data="admin_end_vote")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_back")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
        return
    if data == "menu_captain":
        if not has_match_players():
            await query.edit_message_text(
                "Сначала составьте список игроков: админ запускает голосование в беседе и нажимает «Завершить голосование».",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]),
            )
            return
        draft = draft_get_state()
        if draft:
            await query.edit_message_text("Драфт уже идёт. Участвуйте в беседе.", reply_markup=_start_keyboard(update))
            return
        queue = get_captain_queue()
        match_uids = get_match_user_ids()
        if update.effective_user.id not in match_uids:
            await query.answer("Только проголосовавшие игроки из списка могут нажать.", show_alert=True)
            return
        q = add_captain_candidate(update.effective_user.id)
        if len(q) == 1:
            await query.edit_message_text(
                "Вы первый капитан. Ждём второго — пусть тоже нажмёт «Капитанская дуэль».",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]),
            )
            return
        if len(q) == 2:
            # Двое капитанов — показываем выбор цвета (первый нажавший выбирает)
            try:
                c1 = await context.bot.get_chat(q[0])
                c2 = await context.bot.get_chat(q[1])
                name1 = c1.username or c1.first_name or "Капитан 1"
                name2 = c2.username or c2.first_name or "Капитан 2"
            except Exception:
                name1, name2 = "Капитан 1", "Капитан 2"
            await query.edit_message_text(
                f"Капитаны: {name1} и {name2}. Выберите цвет — кто первый нажмёт, тот и получает выбранную команду.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔴 Красные", callback_data="color_red"), InlineKeyboardButton("🔵 Синие", callback_data="color_blue")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
                ]),
            )
            return
    if data == "menu_back":
        await query.edit_message_text("Выбери действие:", reply_markup=_start_keyboard(update))


# --- Админ: голосование ---

async def callback_admin_start_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not is_admin(update.effective_user.username, update.effective_user.id):
        return
    await query.answer()
    if GROUP_CHAT_ID_INT is None:
        await query.edit_message_text("Укажи GROUP_CHAT_ID в .env")
        return
    start_voting()
    try:
        msg = await context.bot.send_poll(
            GROUP_CHAT_ID_INT,
            "Кто играет? Отметьтесь.",
            options=["Играю"],
            is_anonymous=False,
        )
        if msg.poll:
            set_active_poll_id(str(msg.poll.id))
    except Exception as e:
        logger.exception("Send poll failed")
        await query.edit_message_text(f"Не удалось отправить опрос в группу: {e}")
        return
    buttons = [
        [InlineKeyboardButton("✅ Завершить голосование", callback_data="admin_end_vote")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_admin")],
    ]
    await query.edit_message_text("Голосование запущено в беседе. По завершении нажми «Завершить голосование».", reply_markup=InlineKeyboardMarkup(buttons))


async def callback_admin_end_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not is_admin(update.effective_user.username, update.effective_user.id):
        return
    await query.answer()
    voted = get_voted_user_ids()
    if not voted:
        await query.edit_message_text("Никто не проголосовал. Запусти голосование снова при необходимости.")
        return
    usernames = set()
    uid_to_username = {}
    players = get_players()
    for uid in voted:
        try:
            chat = await context.bot.get_chat(uid)
            uname = (chat.username or "").strip().lower().lstrip("@")
            if uname:
                usernames.add(uname)
                uid_to_username[uid] = uname
        except Exception:
            pass
    indices = players_match_indices(players, usernames)
    match_usernames = {players[i].tg.lower() for i in indices if players[i].tg}
    match_user_ids = [uid for uid in voted if uid_to_username.get(uid, "").lower() in match_usernames]
    if len(indices) < 2:
        await query.edit_message_text("В таблице (колонка tg) нашлось меньше двух игроков из проголосовавших. Добавь tg-ники в таблицу.")
        return
    finish_voting(indices, list(set(match_user_ids)))
    buttons = [[InlineKeyboardButton("◀️ В админку", callback_data="menu_admin")]]
    await query.edit_message_text(f"Голосование завершено. В списке на матч: {len(indices)} человек. Можно запускать «Капитанская дуэль».", reply_markup=InlineKeyboardMarkup(buttons))


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.poll_answer:
        return
    poll_id = str(update.poll_answer.poll_id)
    if get_active_poll_id() != poll_id:
        return
    add_vote(update.poll_answer.user.id)


# --- Выбор цвета и старт драфта ---

def _sheet_index_for_user(players: list[PlayerRecord], match_indices: list[int], username: str) -> int | None:
    un = (username or "").lower().lstrip("@")
    for i in match_indices:
        if players[i].tg and players[i].tg.lower() == un:
            return i
    return None


async def callback_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("color_") or not update.effective_user:
        return
    if draft_get_state():
        await query.answer()
        return
    q = get_captain_queue()
    if len(q) != 2 or update.effective_user.id not in q:
        await query.answer()
        return
    team = "red" if query.data == "color_red" else "blue"
    await query.answer()
    red_uid = update.effective_user.id if team == "red" else (q[1] if q[0] == update.effective_user.id else q[0])
    blue_uid = q[0] if red_uid == q[1] else q[1]
    players = get_players()
    match_indices = get_match_player_indices()
    try:
        c1 = await context.bot.get_chat(q[0])
        c2 = await context.bot.get_chat(q[1])
        cap1_sheet = _sheet_index_for_user(players, match_indices, c1.username)
        cap2_sheet = _sheet_index_for_user(players, match_indices, c2.username)
    except Exception:
        cap1_sheet = match_indices[0]
        cap2_sheet = match_indices[1]
    if cap1_sheet is None:
        cap1_sheet = match_indices[0]
    if cap2_sheet is None:
        cap2_sheet = next((i for i in match_indices if i != cap1_sheet), match_indices[1])
    set_draft(q[0], q[1], red_uid, blue_uid, match_indices, cap1_sheet, cap2_sheet)
    draft = draft_get_state()
    pool = draft["pool"]
    if not pool:
        # Только два капитана — сразу генерируем составы и шлём в группу
        red_team = draft["red_team"]
        blue_team = draft["blue_team"]
        distribution = [(i, 1) for i in red_team] + [(i, 2) for i in blue_team]
        try:
            csv_body = build_lineup_csv(players, distribution)
            resp = await generate_lineups(csv_body)
        except Exception as e:
            logger.exception("Core request failed")
            await query.edit_message_text(f"Ошибка генерации составов: {e}")
            clear_draft()
            return
        if resp.get("status") == "ok" and GROUP_CHAT_ID_INT:
            for t in resp.get("teams", []):
                url = t.get("image_url")
                if url:
                    try:
                        data = resize_for_telegram(await get_image_bytes(url))
                        caption = "Красные" if t.get("team") == 1 else "Синие"
                        await context.bot.send_photo(chat_id=GROUP_CHAT_ID_INT, photo=data, caption=caption)
                    except Exception:
                        pass
        clear_draft()
        await query.edit_message_text("В матче только два капитана — составы отправлены в беседу.")
        return
    # Отправляем сообщение с кнопками в группу
    if GROUP_CHAT_ID_INT is None:
        await query.edit_message_text("GROUP_CHAT_ID не задан — драфт в группу отправить нельзя.")
        return
    keyboard = _draft_keyboard(pool, draft, players)
    msg = await context.bot.send_message(
        GROUP_CHAT_ID_INT,
        "🔴 Ход красных. Выберите игрока:",
        reply_markup=keyboard,
    )
    draft_set_group_message_id(msg.message_id)
    await query.edit_message_text("Драфт запущен в беседе. Участвуйте там.")


def _draft_keyboard(pool: list[int], draft: dict, players: list[PlayerRecord]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for idx in pool:
        p = players[idx]
        row.append(InlineKeyboardButton(f"{p.name} {p.surname}", callback_data=f"pick_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _draft_status_text(draft: dict, players: list[PlayerRecord]) -> str:
    turn = draft["current_turn"]
    red_team = draft["red_team"]
    blue_team = draft["blue_team"]
    red_names = ", ".join(players[i].name for i in red_team)
    blue_names = ", ".join(players[i].name for i in blue_team)
    if turn == "red":
        return f"🔴 Ход красных.\nКрасные: {red_names}\nСиние: {blue_names}\n\nВыберите игрока:"
    return f"🔵 Ход синих.\nКрасные: {red_names}\nСиние: {blue_names}\n\nВыберите игрока:"


async def callback_draft_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("pick_") or not update.effective_user:
        return
    draft = draft_get_state()
    if not draft:
        await query.answer()
        return
    try:
        sheet_index = int(query.data[5:])
    except ValueError:
        await query.answer()
        return
    turn = draft["current_turn"]
    allowed_uid = draft["red_captain_uid"] if turn == "red" else draft["blue_captain_uid"]
    if update.effective_user.id != allowed_uid:
        await query.answer("Не ваш ход.", show_alert=True)
        return
    if sheet_index not in draft.get("pool", []):
        await query.answer("Уже выбран.")
        return
    await query.answer()
    team = "red" if turn == "red" else "blue"
    done = draft_pick(sheet_index, team)
    draft = draft_get_state()
    players = get_players()
    if done:
        # Драфт завершён — собираем CSV и шлём картинки в группу
        red_team = draft["red_team"]
        blue_team = draft["blue_team"]
        distribution = [(i, 1) for i in red_team] + [(i, 2) for i in blue_team]
        csv_body = build_lineup_csv(players, distribution)
        try:
            resp = await generate_lineups(csv_body)
        except Exception as e:
            logger.exception("Core request failed")
            await context.bot.send_message(GROUP_CHAT_ID_INT or update.effective_chat.id, f"Ошибка генерации составов: {e}")
            clear_draft()
            return
        if resp.get("status") != "ok":
            await context.bot.send_message(GROUP_CHAT_ID_INT or update.effective_chat.id, resp.get("message", "Ошибка"))
            clear_draft()
            return
        chat_id = GROUP_CHAT_ID_INT or update.effective_chat.id
        for t in resp.get("teams", []):
            url = t.get("image_url")
            if not url:
                continue
            try:
                data = await get_image_bytes(url)
                data = resize_for_telegram(data)
                caption = "Красные" if t.get("team") == 1 else "Синие"
                await context.bot.send_photo(chat_id=chat_id, photo=data, caption=caption)
            except Exception as e:
                logger.exception("Send photo failed")
        try:
            await query.edit_message_text("✅ Составы сформированы и отправлены выше.")
        except Exception:
            pass
        clear_draft()
        return
    # Обновляем сообщение с драфтом (оно в группе, query пришёл от нажатия там)
    try:
        keyboard = _draft_keyboard(draft["pool"], draft, players)
        text = _draft_status_text(draft, players)
        await query.edit_message_text(text=text, reply_markup=keyboard)
    except Exception as e:
        logger.warning("Edit draft message: %s", e)


def register_handlers(application) -> None:
    from telegram.ext import CommandHandler, CallbackQueryHandler, PollAnswerHandler
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(callback_menu, pattern="^menu_|^admin_|^color_"))
    application.add_handler(CallbackQueryHandler(callback_draft_pick, pattern="^pick_\\d+$"))
    application.add_handler(PollAnswerHandler(poll_answer_handler))