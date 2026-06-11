from pyrogram import filters
from pyromod import Client, Message
from pyromod import listen
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import db_manager
from logging import getLogger
import jdatetime

_logger = getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت طلب (من طلبکارم)", callback_data="add_demand")],
        [InlineKeyboardButton("➖ ثبت بدهی (من بدهکارم)", callback_data="add_owe")],
        [InlineKeyboardButton("📊 مشاهده تراز کلی", callback_data="show_status")],
    ])

    await message.reply_text(
        "سلام! به دفترچه حساب شخصی خودت خوش اومدی 🌹\n\n"
        "از منوی زیر انتخاب کن می‌خوای چیکار کنی:",
        reply_markup=keyboard
    )


@Client.on_callback_query()
async def handle_callbacks(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    await callback_query.answer()

    if data in ["add_demand", "add_owe"]:
        is_demand = (data == "add_demand")
        trans_type = "demand" if is_demand else "owe"

        # ۱. گرفتن لیست دوستان اخیر از دیتابیس
        contacts = db_manager.get_recent_contacts(user.id)

        keyboard = []
        for contact_id, contact_name in contacts.items():
            # ساخت دکمه برای هر شخص (مثلا: sel_123456_demand)
            keyboard.append([InlineKeyboardButton(f"👤 {contact_name}", callback_data=f"sel_{contact_id}_{trans_type}")])

        # ۲. اضافه کردن دکمه کاربر جدید و بازگشت
        keyboard.append([InlineKeyboardButton("➕ یک کاربر جدید (وارد کردن آیدی)", callback_data=f"new_{trans_type}")])
        keyboard.append([InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")])

        await callback_query.edit_message_text(
            "انتخاب کن این تراکنش با کدوم یکی از دوستانت ثبت بشه؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("sel_") or data.startswith("new_"):
        parts = data.split("_")
        action = parts[0]

        is_demand = (parts[-1] == "demand")
        transaction_type = "طلب" if is_demand else "بدهی"

        if action == "sel":
            target_user_id = int(parts[1])
            target_user_db = db_manager.get_user_info(target_user_id)

            target_first_name = target_user_db.first_name if target_user_db else "دوستت"
            target_username = target_user_db.username if target_user_db else None

        else:
            try:
                target_msg = await client.ask(chat_id, "آیدی عددی یا یوزرنیم (@username) شخص جدید رو بفرست:")
                target_user_info = await client.get_users(target_msg.text)

                target_user_id = target_user_info.id
                target_username = target_user_info.username
                target_first_name = target_user_info.first_name or "بدون نام"
            except Exception:
                await client.send_message(chat_id, "❌ کاربری پیدا نشد. عملیات لغو شد.")
                return

        try:
            amount_msg = await client.ask(chat_id,
                                          f"مبلغ {transaction_type} با **{target_first_name}** چقدره؟ (فقط عدد)")
            if not amount_msg.text.isdigit():
                await client.send_message(chat_id, "❌ مبلغ باید عدد باشد. عملیات لغو شد.")
                return
            amount = int(amount_msg.text)

            desc_msg = await client.ask(chat_id, "بابت چیه؟")
            description = desc_msg.text

            db_manager.upsert_user(user.id, user.username, user.first_name)
            db_manager.upsert_user(target_user_id, target_username, target_first_name)

            if is_demand:
                db_manager.add_transaction(user.id, target_user_id, amount, description)
                notif_text = f"🔔 **رسید تراکنش جدید**\n\n👤 **{user.first_name}** ثبت کرده که شما **{amount:,} تومان** بابت «{description}» به ایشون بدهکار هستید."
            else:
                db_manager.add_transaction(target_user_id, user.id, amount, description)
                notif_text = f"🔔 **رسید تراکنش جدید**\n\n👤 **{user.first_name}** ثبت کرده که **{amount:,} تومان** بابت «{description}» به شما بدهکار شده (شما طلبکار شدید)."

            main_menu_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ثبت طلب (کسی بدهکاره)", callback_data="add_demand")],
                [InlineKeyboardButton("➖ ثبت بدهی (من بدهکارم)", callback_data="add_owe")],
                [InlineKeyboardButton("📊 مشاهده تراز کلی", callback_data="show_status")]
            ])

            await client.send_message(
                chat_id,
                f"✅ **با موفقیت ثبت شد!**\n\n"
                f"👤 شخص: {target_first_name}\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"📝 بابت: {description}\n"
                f"نوع: {transaction_type}",
                reply_markup=main_menu_keyboard
            )

            if target_user_id != user.id:
                try:
                    await client.send_message(target_user_id, notif_text)
                except Exception:
                    await client.send_message(
                        chat_id,
                        f"⚠️ **نکته:** پیامک اطلاع‌رسانی برای {target_first_name} ارسال نشد، چون هنوز ربات رو Start نکرده."
                    )

        except Exception as e:
            _logger.error(e)
            await client.send_message(chat_id, "❌ خطایی در ثبت رخ داد یا فرآیند لغو شد.")
    elif data == "show_status":
        balances = db_manager.get_user_balances(user.id)

        if not balances:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]])
            await callback_query.edit_message_text(
                "🎉 حساب شما کاملاً پاکه! هیچ طلب یا بدهی ثبت نشده‌ای ندارید.",
                reply_markup=keyboard
            )
            return

        keyboard = []
        total_balance = 0

        for target_id, info in balances.items():
            net_amount = info['net_amount']
            total_balance += net_amount
            name = info['name']

            if net_amount > 0:
                btn_text = f"🟢 {name} (طلب: {net_amount:,})"
            else:
                btn_text = f"🔴 {name} (بدهی: {abs(net_amount):,})"

            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"history_{target_id}")])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")])

        text = "📊 **لیست ترازهای مالی شما:**\nبرای دیدن جزئیات، روی هر شخص کلیک کنید.\n\n"
        if total_balance > 0:
            text += f"✨ **وضعیت کل:** {total_balance:,} تومان طلبکارید."
        elif total_balance < 0:
            text += f"⚠️ **وضعیت کل:** {abs(total_balance):,} تومان بدهکارید."
        else:
            text += "⚖️ **وضعیت کل:** یر به یر هستید."

        await callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("history_"):

        target_user_id = int(data.split("_")[1])

        history = db_manager.get_transaction_history(user.id, target_user_id)

        if not history:
            await callback_query.answer("خطا: تراکنشی یافت نشد!", show_alert=True)
            return

        if history[0].creditor_id == user.id:
            target_name = history[0].debtor.first_name

        else:
            target_name = history[0].creditor.first_name

        text = f"📜 **ریز تراکنش‌های شما با {target_name}:**\n\n"
        keyboard = []

        for txn in history:
            status_emoji = "✅ (تسویه شده)" if txn.is_settled else "⏳ (باز)"
            if txn.creditor_id == user.id:
                text += f"🟢 **طلب:** {txn.amount:,} تومان {status_emoji}\n"
            else:
                text += f"🔴 **بدهی:** {txn.amount:,} تومان {status_emoji}\n"

            text += f"   📝 بابت: {txn.description}\n"
            shamsi_date = jdatetime.datetime.fromgregorian(datetime=txn.created_at)
            text += f"   📅 {shamsi_date.strftime('%Y/%m/%d %H:%M')}\n"
            text += "   ──────────\n"
            if not txn.is_settled:
                btn_text = f"💸 تسویه: {txn.amount:,} ({txn.description[:10]}...)"

                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"settle_{txn.id}")])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست ترازها", callback_data="show_status")])

        await callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("settle_"):

        txn_id = int(data.split("_")[1])
        settled_txn = db_manager.settle_transaction(txn_id)

        if settled_txn:
            target_id = settled_txn.debtor_id if settled_txn.creditor_id == user.id else settled_txn.creditor_id
            await callback_query.answer("✅ تراکنش با موفقیت تسویه شد و از تراز کل کسر گردید!", show_alert=False)
            callback_query.data = f"history_{target_id}"
            await handle_callbacks(client, callback_query)

        else:
            await callback_query.answer("❌ خطا در یافتن تراکنش!", show_alert=True)

    elif data == "main_menu":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ثبت طلب (کسی بدهکاره)", callback_data="add_demand")],
            [InlineKeyboardButton("➖ ثبت بدهی (من بدهکارم)", callback_data="add_owe")],
            [InlineKeyboardButton("📊 مشاهده تراز کلی", callback_data="show_status")]
        ])
        await callback_query.edit_message_text(
            "سلام! به دفترچه حساب شخصی خودت خوش اومدی 🌹\n\n"
            "از منوی زیر انتخاب کن می‌خوای چیکار کنی:",
            reply_markup=keyboard
        )
