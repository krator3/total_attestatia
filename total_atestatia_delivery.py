from dataclasses import dataclass
from typing import List
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ParseMode, LabeledPrice
from aiogram.utils import executor
import sqlite3
import config

# config.py
# TOKEN = "token"
# if not TOKEN:
#     exit('Error: token not found!')
# PAYMASTER_TOKEN = 'paymaster_token'

msg_text = ""
buy_price = 0
username = ""
btn = []


conn = sqlite3.connect('products.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS products
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  price FLOAT NOT NULL,
                  category TEXT NOT NULL,
                  delivery FLOAT NOT NULL)''')
conn.commit()
cursor.execute("INSERT INTO products (name, price, category, delivery) VALUES ('Fallout', '1499', 'RPG', '233')")
conn.commit()

connect = sqlite3.connect('database.db')
cursor1 = connect.cursor()
cursor1.execute(
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        buy TEXT NOT NULL
    );"""
)
connect.commit()


bot = Bot(token=config.TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class OrderStates(StatesGroup):
    CHOICE_PRODUCT = State()
    CHOICE_GAME = State()


@dataclass
class Item:
    title:str
    description:str
    start_parameter:str
    currency:str
    prices:List[LabeledPrice]
    provider_data:dict=None
    photo_url:str=None
    photo_size:int=None
    photo_width:int=None
    photo_height:int=None
    need_name:bool=False
    need_phone_number:bool=False
    need_email:bool=False
    need_shipping_address:bool=False
    send_phone_number_to_provider:bool=False
    send_email_to_provider:bool=False
    is_flexible:bool=False
    provider_token:str=config.PAYMASTER_TOKEN

    def generate_invoices(self):
        return self.__dict__


class AddProduct(StatesGroup):
    name = State()
    category = State()
    price = State()
    delivery = State()


class DelProduct(StatesGroup):
    name = State()

def kb_category():
    btn_action = "ACTION"
    btn_mmo = "MMO"
    btn_rpg = "RPG"
    kb_category = ReplyKeyboardMarkup(row_width=1,resize_keyboard=True).add(btn_action,btn_mmo,btn_rpg)
    return kb_category


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer('Привет! Я бот-магазин. Чтобы посмотреть мои возможности, отправь мне /help')

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer('''/start - функция приветсвия,
    \n/help - возможности бота (это сообщение),
    \n/add - функция для добавления товара,
    \n/del - функция для удаления товара,
    \n/buy - функция для покупки товара''')


@dp.message_handler(commands=['buy'])
async def cmd_buy(message: types.Message):
    await bot.send_message(text="Выбери жанр игры:", chat_id=message.chat.id, reply_markup=kb_category())
    await OrderStates.CHOICE_GAME.set()

@dp.message_handler(state=OrderStates.CHOICE_GAME)
async def process_catalog(message: types.Message, state: FSMContext):

    choose_category = message.text
    cursor.execute("SELECT id, name, price, delivery FROM products WHERE category=?", (choose_category,))
    products = cursor.fetchall()

    if products:
        catalog_text = "<b>Каталог товаров:</b>\n\n"
        for product in products:
            catalog_text += f"<b>{product[1]} </b>\n<i>ID:</i> {product[0]}\n<i>Цена:</i> {product[2]}₽\n<i>Доставка:</i> {product[3]}₽\n\n"
        await message.answer(catalog_text, parse_mode=ParseMode.HTML)

        global btn
        btn = [product[1] for product in products]

        global buy_price
        buy_price = [product[2] for product in products]

        global username
        username = message.from_user.username

        buttons = [KeyboardButton(product[1]) for product in products]
        keyboard = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True).add(*buttons)
        await bot.send_message(text="Выбери товар:", chat_id=message.chat.id, reply_markup=keyboard)
        await OrderStates.CHOICE_PRODUCT.set()

    else:
        await message.answer("Каталог пуст")
        await state.finish()


@dp.message_handler(state=OrderStates.CHOICE_PRODUCT)
async def process_product(msg: types.Message, state: FSMContext):
    await state.finish()

    try:

        global msg_text
        msg_text = msg.text

        global username
        username = msg.from_user.username

        cursor.execute("SELECT price FROM products WHERE name=?", (msg_text,))
        price = cursor.fetchone()[0]

        cursor.execute("SELECT delivery FROM products WHERE name=?", (msg_text,))
        delivery = cursor.fetchone()[0]

        product = Item(
            title='Покупка товара',
            description='Оформление покупки товара',
            currency='RUB',
            prices=[LabeledPrice(label='Покупка товара', amount=int(price * 100)),
                    LabeledPrice(label='Доставка',amount=int(delivery * 100))],
            start_parameter=f'create_invoice_product_{msg_text.lower()}',
            photo_url="https://storage.pravo.ru/image/145/72601.png?v=1629973650",
            photo_size=600,
            need_shipping_address=True,
            is_flexible=False)

        await bot.send_invoice(msg.from_user.id, **product.generate_invoices(), payload='12345')

    except Exception as e:
        print(f"Error!\n{e}")


@dp.pre_checkout_query_handler(lambda query: True)
async def checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    cursor1.execute("INSERT INTO users (username, buy) VALUES (?, ?)", (username, msg_text))
    connect.commit()

    await message.answer("Оплата прошла успешно. Спасибо, что выбрали наш магазин!")


@dp.message_handler(commands=['add'])
async def cmd_addproduct_start(message: types.Message):
    await message.answer("Введите название товара")
    await AddProduct.name.set()


@dp.message_handler(state=AddProduct.name)
async def process_addproduct_name(message: types.Message, state: FSMContext):
    name = message.text
    await state.update_data(name=name)
    await message.answer("Укажите категорию товара",reply_markup=kb_category())
    await AddProduct.category.set()

@dp.message_handler(state=AddProduct.category)
async def process_addproduct_category(message: types.Message,state: FSMContext):
    category = message.text
    await state.update_data(category=category)
    await message.answer("Введите цену товара в ₽")
    await AddProduct.price.set()


@dp.message_handler(state=AddProduct.price)
async def process_addproduct_delivery(message: types.Message, state: FSMContext):
    price = message.text
    await state.update_data(price=price)
    await message.answer("Введите цену доставки в ₽")
    await AddProduct.delivery.set()

@dp.message_handler(state=AddProduct.delivery)
async def process_addproduct_price(message: types.Message, state: FSMContext):
    delivery = message.text
    data = await state.get_data()
    name = data.get('name')
    category = data.get('category')
    price = data.get('price')
    cursor.execute("INSERT INTO products (name, price, category, delivery) VALUES (?, ?, ?, ?)", (name, price, category, delivery))
    conn.commit()
    await message.answer("Товар добавлен в каталог!")
    await state.finish()


@dp.message_handler(commands=['del'])
async def cmd_delete_product(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    cursor.execute("SELECT name FROM products")
    products = cursor.fetchall()
    buttons = [KeyboardButton(product[0]) for product in products]
    keyboard = markup.add(*buttons)

    try:
        await bot.send_message(chat_id=message.chat.id, text="Выберите продукт, который хотите удалить:",
                               reply_markup=keyboard)
        await DelProduct.name.set()

    except Exception as e:
        await message.reply(f'Error: {e}')


@dp.message_handler(state=DelProduct.name)
async def process_del_product(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['product_name'] = message.text

    name = data['product_name']
    cursor.execute(f"SELECT * FROM products WHERE name='{name}'")
    result = cursor.fetchone()

    if result is None:
        await message.reply(f'Продукта под названием "{name}" не существует.')
        await state.finish()
    else:
        cursor.execute(f"DELETE FROM products WHERE name='{name}'")
        conn.commit()
        await message.reply(f'Продукт "{name}" успешно удалён из каталога.')
        await state.finish()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)