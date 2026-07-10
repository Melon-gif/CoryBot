import telebot,re,math,random,sqlite3,requests,threading,time,os,json,logging
from datetime import datetime,timedelta
from telebot import types
# ===== ИМПОРТЫ ДЛЯ WEBHOOK =====
from flask import Flask, request, jsonify
import threading

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("telebot").setLevel(logging.WARNING)

# ===== ПОЛУЧЕНИЕ КЛЮЧЕЙ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TOKEN = os.getenv('TELEGRAM_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Проверка что ключи есть
if not TOKEN:
    print("❌ TELEGRAM_TOKEN не найден! Установите переменную окружения.")
    exit(1)

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY не найден! Установите переменную окружения.")
    exit(1)

# Для локального теста (если запускаете на телефоне) - раскомментируйте:
# TOKEN 
# GROQ_API_KEY 

MY_ID,TARGET_ID=6387634727,8078077154
bot=telebot.TeleBot(TOKEN)
active,DB=True,"bot_stats.db"
START_TIME=datetime.now()
TARGET_CHAT_ID=-1002353241696

# Медиа папки
FOLDERS={"memes":"memes","sleep":"sleep","awake":"awake","hug":"hug","kiss":"kiss","pet":"pet","coin":"coin"}
MEME_PHRASES=["Этот мем достоин вашего внимания, сэр!","Я сохранил этот мем специально для вас, сэр.","Обратите внимание на этот шедевр, сэр!","Думаю, этот мем вас порадует, сэр."]

def get_random_media(folder):
    try:
        if not os.path.exists(folder): os.makedirs(folder,exist_ok=True)
        files=[f for f in os.listdir(folder) if f.lower().endswith(('.png','.jpg','.jpeg','.gif','.mp4'))]
        return os.path.join(folder,random.choice(files)) if files else None
    except: return None

def get_random_meme(): return get_random_media(FOLDERS["memes"])
def get_random_sleep_media(): return get_random_media(FOLDERS["sleep"])
def get_random_awake_media(): return get_random_media(FOLDERS["awake"])
def get_random_hug_media(): return get_random_media(FOLDERS["hug"])
def get_random_kiss_media(): return get_random_media(FOLDERS["kiss"])
def get_random_pet_media(): return get_random_media(FOLDERS["pet"])
def get_random_coin_video(): return get_random_media(FOLDERS["coin"])

# База данных
def q(sql,p=()):
    c=sqlite3.connect(DB).cursor()
    c.execute(sql,p)
    c.connection.commit()
    return c.fetchall()

def log_action(m):
    try:
        if not m or not m.from_user: return
        u=m.from_user
        name=f"@{u.username}" if u.username else u.first_name
        chat="личка" if m.chat.type=='private' else m.chat.title or "группа"
        text=m.text or "медиа"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} в {chat}: {text[:100]}")
    except: pass

# Создание таблиц
q('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT)')
q('CREATE TABLE IF NOT EXISTS actions(user_id INTEGER,target_id INTEGER,action_type TEXT)')
q('CREATE TABLE IF NOT EXISTS action_stats(user_id INTEGER,target_id INTEGER,action_type TEXT,count INTEGER DEFAULT 0,PRIMARY KEY(user_id,target_id,action_type))')
q('CREATE TABLE IF NOT EXISTS math_history(user_id INTEGER,expression TEXT,result TEXT)')
q('CREATE TABLE IF NOT EXISTS ai_history(user_id INTEGER,question TEXT,answer TEXT,date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
q('CREATE TABLE IF NOT EXISTS feed_limit(global_limit INTEGER DEFAULT 0,last_reset TIMESTAMP)')

# Таблица фермы
q('''
CREATE TABLE IF NOT EXISTS farm_stats(
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    last_farm TIMESTAMP,
    upgrade1 INTEGER DEFAULT 0,
    upgrade2 INTEGER DEFAULT 0,
    upgrade3 INTEGER DEFAULT 0,
    upgrade4 INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    last_roulette TIMESTAMP,
    skin INTEGER DEFAULT 1,
    robot INTEGER DEFAULT 0,
    boost_active INTEGER DEFAULT 0,
    boost_type TEXT,
    boost_uses INTEGER DEFAULT 0,
    last_daily TIMESTAMP,
    daily_streak INTEGER DEFAULT 0,
    total_farms INTEGER DEFAULT 0,
    best_farm INTEGER DEFAULT 0,
    farm_uses_left INTEGER DEFAULT 0,
    last_slots TIMESTAMP,
    reminder_farm INTEGER DEFAULT 0,
    reminder_slots INTEGER DEFAULT 0
)
''')

# Таблица банка
q('''
CREATE TABLE IF NOT EXISTS bank(
    user_id INTEGER PRIMARY KEY,
    deposit INTEGER DEFAULT 0,
    last_interest TIMESTAMP
)
''')

# Таблица кредитов
q('''
CREATE TABLE IF NOT EXISTS loans(
    user_id INTEGER PRIMARY KEY,
    loan_amount INTEGER DEFAULT 0,
    loan_time TIMESTAMP,
    loan_due TIMESTAMP
)
''')

# Таблица подарков
q('''
CREATE TABLE IF NOT EXISTS gifts(
    user_id INTEGER PRIMARY KEY,
    phones TEXT DEFAULT '[]',
    rings TEXT DEFAULT '[]',
    cars TEXT DEFAULT '[]',
    houses TEXT DEFAULT '[]',
    pets TEXT DEFAULT '[]',
    sent_phones INTEGER DEFAULT 0,
    sent_rings INTEGER DEFAULT 0,
    sent_cars INTEGER DEFAULT 0,
    sent_houses INTEGER DEFAULT 0,
    sent_pets INTEGER DEFAULT 0,
    received_phones INTEGER DEFAULT 0,
    received_rings INTEGER DEFAULT 0,
    received_cars INTEGER DEFAULT 0,
    received_houses INTEGER DEFAULT 0,
    received_pets INTEGER DEFAULT 0
)
''')

# Таблица истории подарков
q('''
CREATE TABLE IF NOT EXISTS gift_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user INTEGER,
    to_user INTEGER,
    category TEXT,
    gift_name TEXT,
    gift_quality INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Таблица криптовалют
q('''
CREATE TABLE IF NOT EXISTS crypto_prices(
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    price REAL,
    last_update TIMESTAMP
)
''')

q('''
CREATE TABLE IF NOT EXISTS crypto_wallets(
    user_id INTEGER PRIMARY KEY,
    eth REAL DEFAULT 0,
    ton REAL DEFAULT 0,
    link REAL DEFAULT 0,
    etherium REAL DEFAULT 0,
    btc REAL DEFAULT 0
)
''')

# Добавление колонок
for col in ['level','exp','last_roulette','skin','robot','boost_active','boost_type','boost_uses','last_daily','daily_streak','total_farms','best_farm','farm_uses_left','last_slots','upgrade4','reminder_farm','reminder_slots']:
    try:
        q(f'ALTER TABLE farm_stats ADD COLUMN {col}')
    except:
        pass

q('INSERT OR IGNORE INTO feed_limit(global_limit,last_reset) VALUES(0,?)',(datetime.now().isoformat(),))

# ===== ИНИЦИАЛИЗАЦИЯ КРИПТОВАЛЮТ =====
CRYPTO_LIST = [
    {'id': 1, 'symbol': 'ETH', 'name': 'Эфир', 'price': 1800},
    {'id': 2, 'symbol': 'TON', 'name': 'Тон коин', 'price': 2.5},
    {'id': 3, 'symbol': 'LINK', 'name': 'Линк', 'price': 8.7},
    {'id': 4, 'symbol': 'ETR', 'name': 'Этерий', 'price': 3200},
    {'id': 5, 'symbol': 'BTC', 'name': 'Биткоин', 'price': 45000}
]

for crypto in CRYPTO_LIST:
    existing = q('SELECT id FROM crypto_prices WHERE id=?', (crypto['id'],))
    if not existing:
        q('INSERT INTO crypto_prices(id,symbol,name,price,last_update) VALUES(?,?,?,?,?)', 
          (crypto['id'], crypto['symbol'], crypto['name'], crypto['price'], datetime.now().isoformat()))

def get_crypto_prices():
    return q('SELECT id,symbol,name,price FROM crypto_prices ORDER BY id')

def get_crypto_price(crypto_id):
    r = q('SELECT price FROM crypto_prices WHERE id=?', (crypto_id,))
    return r[0][0] if r else 0

def update_crypto_prices():
    cryptos = q('SELECT id, price FROM crypto_prices')
    for crypto_id, current_price in cryptos:
        change = random.uniform(-10, 10)
        new_price = current_price * (1 + change / 100)
        new_price = round(new_price, 2)
        if new_price < 0.01:
            new_price = 0.01
        q('UPDATE crypto_prices SET price=?, last_update=? WHERE id=?', 
          (new_price, datetime.now().isoformat(), crypto_id))
    print(f"[CRYPTO] Цены обновлены в {datetime.now().strftime('%H:%M:%S')}")

def get_user_crypto(uid):
    if uid is None: return None
    r = q('SELECT eth,ton,link,etherium,btc FROM crypto_wallets WHERE user_id=?', (uid,))
    if r:
        return {'eth': r[0][0] or 0, 'ton': r[0][1] or 0, 'link': r[0][2] or 0, 
                'etherium': r[0][3] or 0, 'btc': r[0][4] or 0}
    q('INSERT INTO crypto_wallets(user_id) VALUES(?)', (uid,))
    return get_user_crypto(uid)

def update_crypto_wallet(uid, crypto_symbol, amount):
    if uid is None: return
    symbol_map = {'ETH': 'eth', 'TON': 'ton', 'LINK': 'link', 'ETR': 'etherium', 'BTC': 'btc'}
    field = symbol_map.get(crypto_symbol)
    if not field: return
    q(f'UPDATE crypto_wallets SET {field}={field}+? WHERE user_id=?', (amount, uid))

def buy_crypto(uid, crypto_id, amount):
    if uid is None: return "❌ Ошибка"
    if crypto_id < 1 or crypto_id > 5:
        return "❌ Неверный ID криптовалюты! Доступно 1-5"
    if amount <= 0:
        return "❌ Количество должно быть больше 0!"
    
    crypto = q('SELECT symbol, name, price FROM crypto_prices WHERE id=?', (crypto_id,))
    if not crypto:
        return "❌ Криптовалюта не найдена!"
    
    symbol, name, price = crypto[0]
    total_price = round(amount * price, 2)
    
    if uid != MY_ID:
        farm = get_farm_data(uid)
        if not farm:
            return "❌ Ошибка"
        if farm['coins'] < total_price:
            return f"❌ Недостаточно монет! Нужно {total_price}💰, у тебя {farm['coins']}💰"
        add_coins(uid, -total_price)
    else:
        total_price = 0
    
    update_crypto_wallet(uid, symbol, amount)
    wallet = get_user_crypto(uid)
    
    return f"✅ Куплено {amount} {name} ({symbol}) за {total_price}💰!\n📊 Баланс: {wallet.get('eth',0):.2f} ETH, {wallet.get('ton',0):.2f} TON, {wallet.get('link',0):.2f} LINK, {wallet.get('etherium',0):.2f} ETR, {wallet.get('btc',0):.8f} BTC"

def sell_crypto(uid, crypto_id, amount):
    if uid is None: return "❌ Ошибка"
    if crypto_id < 1 or crypto_id > 5:
        return "❌ Неверный ID криптовалюты! Доступно 1-5"
    if amount <= 0:
        return "❌ Количество должно быть больше 0!"
    
    crypto = q('SELECT symbol, name, price FROM crypto_prices WHERE id=?', (crypto_id,))
    if not crypto:
        return "❌ Криптовалюта не найдена!"
    
    symbol, name, price = crypto[0]
    
    wallet = get_user_crypto(uid)
    if not wallet:
        return "❌ Ошибка"
    
    symbol_map = {'ETH': 'eth', 'TON': 'ton', 'LINK': 'link', 'ETR': 'etherium', 'BTC': 'btc'}
    field = symbol_map.get(symbol)
    if not field:
        return "❌ Ошибка"
    
    if wallet[field] < amount:
        return f"❌ У тебя только {wallet[field]:.8f} {symbol}!"
    
    total_price = round(amount * price, 2)
    
    q(f'UPDATE crypto_wallets SET {field}={field}-? WHERE user_id=?', (amount, uid))
    
    add_coins(uid, total_price)
    
    wallet = get_user_crypto(uid)
    return f"✅ Продано {amount} {name} ({symbol}) за {total_price}💰!\n📊 Остаток: {wallet.get('eth',0):.2f} ETH, {wallet.get('ton',0):.2f} TON, {wallet.get('link',0):.2f} LINK, {wallet.get('etherium',0):.2f} ETR, {wallet.get('btc',0):.8f} BTC"

def admin_withdraw_crypto(admin_uid, target_uid, amount):
    if admin_uid is None or target_uid is None:
        return "❌ Ошибка: пользователь не найден"
    if admin_uid != MY_ID:
        return "❌ Доступ запрещён!"
    if amount <= 0:
        return "❌ Сумма должна быть больше 0!"
    
    target_data = q('SELECT user_id FROM users WHERE user_id=?', (target_uid,))
    if not target_data:
        return "❌ Пользователь не найден!"
    
    target_wallet = get_user_crypto(target_uid)
    if not target_wallet:
        return "❌ У пользователя нет крипто-кошелька!"
    
    cryptos = [
        ('btc', target_wallet['btc'], 'BTC', 'Биткоин'),
        ('etherium', target_wallet['etherium'], 'ETR', 'Этерий'),
        ('eth', target_wallet['eth'], 'ETH', 'Эфир'),
        ('ton', target_wallet['ton'], 'TON', 'Тон коин'),
        ('link', target_wallet['link'], 'LINK', 'Линк')
    ]
    
    withdrawn = 0
    withdrawn_info = []
    
    for field, balance, symbol, name in cryptos:
        if balance >= amount and withdrawn == 0:
            q(f'UPDATE crypto_wallets SET {field}={field}-? WHERE user_id=?', (amount, target_uid))
            add_coins(admin_uid, int(amount * get_crypto_price(crypto_id_from_symbol(symbol))))
            withdrawn = amount
            withdrawn_info.append(f"{amount} {symbol} ({name})")
        elif balance > 0 and withdrawn == 0:
            q(f'UPDATE crypto_wallets SET {field}=0 WHERE user_id=?', (target_uid,))
            add_coins(admin_uid, int(balance * get_crypto_price(crypto_id_from_symbol(symbol))))
            withdrawn = balance
            withdrawn_info.append(f"{balance:.2f} {symbol} ({name})")
    
    if withdrawn == 0:
        return "❌ У пользователя нет криптовалюты!"
    
    target_name = q('SELECT username FROM users WHERE user_id=?', (target_uid,))
    target_name = target_name[0][0] if target_name else f"Пользователь {target_uid}"
    
    return f"👑 Ты снял {', '.join(withdrawn_info)} с кошелька @{target_name}!"

def crypto_id_from_symbol(symbol):
    map = {'BTC': 5, 'ETR': 4, 'ETH': 1, 'TON': 2, 'LINK': 3}
    return map.get(symbol, 1)

def get_crypto_market():
    prices = get_crypto_prices()
    text = "📊 **КРИПТО-РЫНОК**\n\n"
    for p_id, symbol, name, price in prices:
        old_price = q('SELECT price FROM crypto_prices WHERE id=?', (p_id,))
        old_price = old_price[0][0] if old_price else price
        change = ((price - old_price) / old_price * 100) if old_price > 0 else 0
        arrow = "📈" if change >= 0 else "📉"
        text += f"{arrow} `{symbol}` {name}: ${price:.2f}\n"
    text += "\n`Кори купить 1 10` - купить 10 ETH"
    text += "\n`Кори продать 1 10` - продать 10 ETH"
    text += "\n`Кори рынок` - обновить курс"
    text += "\n`Кори крипта` - посмотреть баланс"
    return text

def get_crypto_balance(uid):
    if uid is None: return "❌ Ошибка"
    wallet = get_user_crypto(uid)
    if not wallet: return "❌ Ошибка"
    text = "💎 **КРИПТО-БАЛАНС**\n\n"
    text += f"🪙 Эфир (ETH): {wallet['eth']:.2f}\n"
    text += f"🪙 Тон коин (TON): {wallet['ton']:.2f}\n"
    text += f"🪙 Линк (LINK): {wallet['link']:.2f}\n"
    text += f"🪙 Этерий (ETR): {wallet['etherium']:.2f}\n"
    text += f"🪙 Биткоин (BTC): {wallet['btc']:.8f}\n\n"
    
    total_value = 0
    cryptos = [
        ('eth', wallet['eth']),
        ('ton', wallet['ton']),
        ('link', wallet['link']),
        ('etherium', wallet['etherium']),
        ('btc', wallet['btc'])
    ]
    for field, amount in cryptos:
        if amount > 0:
            id_map = {'eth': 1, 'ton': 2, 'link': 3, 'etherium': 4, 'btc': 5}
            price = get_crypto_price(id_map[field])
            total_value += amount * price
    
    text += f"💰 Общая стоимость: {int(total_value)} монет"
    return text

def reset_feed_limit(): q('UPDATE feed_limit SET global_limit=0,last_reset=?',(datetime.now().isoformat(),))
def get_feed_limit(): 
    r=q('SELECT global_limit FROM feed_limit')
    return r[0][0] if r else 0
def increment_feed_limit(): q('UPDATE feed_limit SET global_limit=global_limit+1')
def check_feed_limit():
    r=q('SELECT last_reset FROM feed_limit')
    if r and r[0][0]:
        try:
            if datetime.now()-datetime.fromisoformat(r[0][0])>=timedelta(hours=1): 
                reset_feed_limit()
        except: pass
    return get_feed_limit()<5

def uid(u):
    if not u: return None
    q('INSERT OR IGNORE INTO users VALUES(?,?,?)',(u.id,u.username or "",u.first_name or ""))
    return u.id

def sa(uid,tid,a): 
    if uid is None or tid is None: return
    q('INSERT INTO actions VALUES(?,?,?)',(uid,tid,a))
    q('INSERT INTO action_stats VALUES(?,?,?,1) ON CONFLICT DO UPDATE SET count=count+1',(uid,tid,a))

def sm(uid,e,r): 
    if uid is None: return
    q('INSERT INTO math_history VALUES(?,?,?)',(uid,e,str(r)))

def gs(uid): 
    if uid is None: return []
    return q('SELECT action_type,SUM(count) FROM action_stats WHERE user_id=? GROUP BY action_type',(uid,))

def gt(a): 
    return q('SELECT u.username,u.first_name,SUM(acs.count) FROM action_stats acs JOIN users u ON u.user_id=acs.user_id WHERE acs.action_type=? GROUP BY acs.user_id ORDER BY SUM(acs.count) DESC LIMIT 5',(a,))

def gtl(): 
    return q('SELECT action_type,SUM(count) FROM action_stats GROUP BY action_type')

def save_ai(uid,q_text,a_text): 
    if uid is None: return
    q('INSERT INTO ai_history(user_id,question,answer) VALUES(?,?,?)',(uid,q_text,a_text))

# ===== ФУНКЦИИ ФЕРМЫ =====

def get_farm_data(uid):
    if uid is None: return None
    r=q('SELECT coins,last_farm,upgrade1,upgrade2,upgrade3,upgrade4,level,exp,last_roulette,skin,robot,boost_active,boost_type,boost_uses,last_daily,daily_streak,total_farms,best_farm,farm_uses_left,last_slots,reminder_farm,reminder_slots FROM farm_stats WHERE user_id=?',(uid,))
    if r: 
        return {
            'coins':r[0][0] or 0,
            'last_farm':r[0][1],
            'upgrade1':r[0][2] or 0,
            'upgrade2':r[0][3] or 0,
            'upgrade3':r[0][4] or 0,
            'upgrade4':r[0][5] or 0,
            'level':r[0][6] or 1,
            'exp':r[0][7] or 0,
            'last_roulette':r[0][8],
            'skin':r[0][9] or 1,
            'robot':r[0][10] or 0,
            'boost_active':r[0][11] or 0,
            'boost_type':r[0][12],
            'boost_uses':r[0][13] or 0,
            'last_daily':r[0][14],
            'daily_streak':r[0][15] or 0,
            'total_farms':r[0][16] or 0,
            'best_farm':r[0][17] or 0,
            'farm_uses_left':r[0][18] or 0,
            'last_slots':r[0][19],
            'reminder_farm':r[0][20] or 0,
            'reminder_slots':r[0][21] or 0
        }
    q('INSERT INTO farm_stats(user_id) VALUES(?)',(uid,))
    return get_farm_data(uid)

def update_farm(uid,f,v):
    if uid is None: return
    q(f'UPDATE farm_stats SET {f}=? WHERE user_id=?',(v,uid))

def add_coins(uid,a):
    if uid is None: return 0
    d=get_farm_data(uid)
    if not d: return 0
    nc=d['coins']+a
    update_farm(uid,'coins',nc)
    return nc

def get_farm_power(uid):
    if uid is None: return 2
    d=get_farm_data(uid)
    if not d: return 2
    b=2
    if d['upgrade1']>0: b+=3
    if d['upgrade3']>0: b+=10
    multiplier=1.25 if d['upgrade2']>0 else 1.0
    return int(b * multiplier)

def get_farm_uses(uid):
    if uid is None: return 1
    d=get_farm_data(uid)
    if not d: return 1
    skin_uses = {1:1,2:2,3:3,4:4,5:5,6:6,7:8}
    return skin_uses.get(d['skin'], 1)

def reset_farm_uses(uid):
    if uid is None: return
    uses=get_farm_uses(uid)
    update_farm(uid,'farm_uses_left',uses)

def use_farm_use(uid):
    if uid is None: return 0
    d=get_farm_data(uid)
    if not d: return 0
    left=d.get('farm_uses_left', 0)
    if left>0:
        update_farm(uid,'farm_uses_left',left-1)
        return left-1
    return 0

def get_exp_needed(level):
    return 5 * (level ** 2) + 10

def add_exp(uid, amount):
    if uid is None: return None
    d=get_farm_data(uid)
    if not d: return None
    new_exp = d['exp'] + amount
    level = d['level']
    level_up_text = ""
    while level < 10:
        exp_needed = get_exp_needed(level)
        if new_exp >= exp_needed:
            new_exp -= exp_needed
            level += 1
            bonus = 5 * level
            add_coins(uid, bonus)
            level_up_text += f"\n🎉 УРОВЕНЬ {level}! +{bonus} монет! 🎉"
            if level == 10:
                level_up_text += "\n🌟 МАКСИМАЛЬНЫЙ УРОВЕНЬ ДОСТИГНУТ! 🌟"
        else:
            break
    if level > d['level']:
        update_farm(uid, 'level', level)
    update_farm(uid, 'exp', new_exp)
    return level_up_text if level_up_text else None

def farm_coins(uid, ca=None):
    if uid is None: return "❌ Ошибка",0
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка",0
    
    left=d.get('farm_uses_left', 0)
    if left<=0 and uid!=MY_ID and d['last_farm']:
        try:
            td=(datetime.now()-datetime.fromisoformat(d['last_farm'])).total_seconds()
            if td<300:
                r=int(300-td)
                return f"⏳ Подожди {r//60}мин {r%60}сек до следующего фарма!",0
        except: pass
    
    lucky_text = ""
    earned = 0
    
    if uid==MY_ID and ca is not None:
        try:
            earned=int(ca)
            if earned<0: return "❌ Нельзя получить отрицательное количество!",0
            if earned>1000: return "❌ Максимум 1000 монет за раз!",0
        except: return "❌ Введи число!",0
    else:
        earned=get_farm_power(uid)
        if random.random() < 0.04:
            earned *= 5
            lucky_text = "🍀 УДАЧНАЯ ФЕРМА! x5 множитель! 🎉\n"
    
    add_coins(uid, earned)
    update_farm(uid, 'last_farm', datetime.now().isoformat())
    
    if uid!=MY_ID:
        use_farm_use(uid)
    
    update_farm(uid, 'total_farms', d.get('total_farms', 0) + 1)
    if earned > d.get('best_farm', 0):
        update_farm(uid, 'best_farm', earned)
    
    exp_added = earned
    level_up = add_exp(uid, exp_added)
    d=get_farm_data(uid)
    
    skin_name = SKINS.get(d['skin'], {}).get('name', '🌿 Обычная')
    ups=[]
    if d['upgrade1']>0: ups.append("🔨 +3")
    if d['upgrade2']>0: ups.append("⚡ x1.25")
    if d['upgrade3']>0: ups.append("💎 +10")
    if d['upgrade4']>0: ups.append("⏲️ Напоминалка")
    ut=f" | Активно: {', '.join(ups)}" if ups else ""
    exp_needed = get_exp_needed(d['level']) if d['level'] < 10 else "MAX"
    level_info = f" | Уровень {d['level']}/{10} (Опыт: {d['exp']}/{exp_needed})"
    skin_info = f" | Скин: {skin_name}"
    uses_info = f" | Осталось попыток: {d.get('farm_uses_left', 0)}/{get_farm_uses(uid)}"
    
    msg = f"{lucky_text}💰 +{earned} монет{' (ручной ввод)' if uid==MY_ID and ca is not None else ''} | Баланс: {d['coins']} 🪙{ut}{level_info}{skin_info}{uses_info}"
    if level_up:
        msg += level_up
    return msg, earned

def buy_upgrade(uid,up_id):
    if uid is None: return "❌ Ошибка"
    ups={1:{'name':'🔨 Улучшение 1','price':6,'field':'upgrade1'},
         2:{'name':'⚡ Улучшение 2','price':20,'field':'upgrade2'},
         3:{'name':'💎 Улучшение 3','price':50,'field':'upgrade3'},
         4:{'name':'⏲️ Напоминалка','price':350,'field':'upgrade4'}}
    if up_id not in ups: return "❌ Неправильный номер улучшения!"
    u=ups[up_id]
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if d[u['field']]>0: return f"❌ Улучшение {u['name']} уже куплено!"
    if d['coins']<u['price']: return f"❌ Недостаточно монет! Нужно {u['price']}, у тебя {d['coins']}"
    add_coins(uid,-u['price'])
    update_farm(uid,u['field'],1)
    d=get_farm_data(uid)
    return f"✅ Куплено: {u['name']}!\n💰 Осталось: {d['coins']} монет"

def get_leaderboard():
    return q('SELECT u.username,u.first_name,fs.coins,fs.level FROM farm_stats fs JOIN users u ON u.user_id=fs.user_id WHERE u.user_id != ? ORDER BY fs.coins DESC LIMIT 10', (MY_ID,))

# ===== СКИНЫ =====
SKINS = {
    1: {'name': '🌿 Обычная', 'price': 0, 'uses': 1, 'description': '1 использование без кулдауна'},
    2: {'name': '🌻 Цветочная', 'price': 30, 'uses': 2, 'description': '2 использования без кулдауна'},
    3: {'name': '🌴 Тропическая', 'price': 100, 'uses': 3, 'description': '3 использования без кулдауна'},
    4: {'name': '🏰 Замок', 'price': 300, 'uses': 4, 'description': '4 использования без кулдауна'},
    5: {'name': '❄️ Зимняя', 'price': 500, 'uses': 5, 'description': '5 использований без кулдауна'},
    6: {'name': '👑 Королевская', 'price': 1000, 'uses': 6, 'description': '6 использований без кулдауна'},
    7: {'name': '🚀 Космическая', 'price': 2000, 'uses': 8, 'description': '8 использований без кулдауна'}
}

def buy_skin(uid, skin_id):
    if uid is None: return "❌ Ошибка"
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if skin_id not in SKINS: return "❌ Такого скина нет!"
    skin = SKINS[skin_id]
    if d['coins'] < skin['price']:
        return f"❌ Недостаточно монет! Нужно {skin['price']}, у тебя {d['coins']}"
    if d['skin'] == skin_id:
        return f"❌ Скин {skin['name']} уже активен!"
    add_coins(uid, -skin['price'])
    update_farm(uid, 'skin', skin_id)
    reset_farm_uses(uid)
    d=get_farm_data(uid)
    return f"✅ Скин {skin['name']} активирован! +{skin['uses']} попыток без кулдауна!\n💰 Осталось: {d['coins']} монет"

def get_skins_list(uid):
    if uid is None: return ""
    d=get_farm_data(uid)
    if not d: return ""
    text = "🎨 **ДОСТУПНЫЕ СКИНЫ:**\n\n"
    for skin_id, skin in SKINS.items():
        status = "✅" if d['skin'] == skin_id else "❌"
        text += f"{status} `{skin_id}`. {skin['name']} — {skin['description']} (💰 {skin['price']} монет)\n"
    text += "\nНапиши: `Кори скин 2` (где 2 - номер скина)"
    return text

# ===== СИСТЕМА ПЕРЕДАЧИ МОНЕТ =====
def transfer_coins(uid, target_id, amount):
    if uid is None or target_id is None:
        return "❌ Ошибка: пользователь не найден", None
    if uid == target_id:
        return "❌ Нельзя передать монеты самому себе!", None
    if amount < 1:
        return "❌ Сумма должна быть больше 0!", None
    sender_data = get_farm_data(uid)
    if not sender_data:
        return "❌ Ошибка: данные отправителя не найдены", None
    if sender_data['coins'] < amount:
        return f"❌ Недостаточно монет! У тебя {sender_data['coins']} монет", None
    receiver_data = get_farm_data(target_id)
    if not receiver_data:
        return "❌ Ошибка: получатель не найден", None
    if uid == MY_ID:
        commission = 0
    else:
        commission = int(amount * 0.05)
    total_debit = amount + commission
    if sender_data['coins'] < total_debit:
        return f"❌ Недостаточно монет с учётом комиссии! Нужно {total_debit}, у тебя {sender_data['coins']}", None
    add_coins(uid, -total_debit)
    add_coins(target_id, amount)
    result = f"✅ Ты передал {amount} монет!\n"
    if commission > 0:
        result += f"📊 Комиссия 5%: {commission} монет\n"
    result += f"💰 Твой новый баланс: {sender_data['coins'] - total_debit} монет"
    return result, target_id

# ===== РУЛЕТКА =====
def roulette(uid, bet):
    if uid is None: return "❌ Ошибка"
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if bet < 1: return "❌ Ставка должна быть больше 0!"
    if bet > d['coins']: return f"❌ Недостаточно монет! У тебя {d['coins']}"
    if uid != MY_ID and d.get('last_roulette'):
        try:
            last=datetime.fromisoformat(d['last_roulette'])
            td=(datetime.now()-last).total_seconds()
            if td<60:
                remaining=int(60-td)
                return f"⏳ Подожди {remaining}сек до следующей рулетки!"
        except: pass
    if random.random() < 0.5:
        win = bet * 2
        add_coins(uid, win)
        update_farm(uid, 'last_roulette', datetime.now().isoformat())
        d=get_farm_data(uid)
        return f"🪙 Орёл! 🎉 ВЫИГРЫШ! +{win} монет! (x2) 🎉\n💰 Новый баланс: {d['coins']} монет"
    else:
        add_coins(uid, -bet)
        update_farm(uid, 'last_roulette', datetime.now().isoformat())
        d=get_farm_data(uid)
        return f"🪙 Решка! 😢 ПРОИГРЫШ! -{bet} монет...\n💰 Новый баланс: {d['coins']} монет"

# ===== ЕЖЕДНЕВНЫЙ БОНУС =====
def daily_bonus(uid):
    if uid is None: return "❌ Ошибка"
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    now=datetime.now()
    if d.get('last_daily'):
        try:
            last=datetime.fromisoformat(d['last_daily'])
            if (now-last).days==0:
                return "⏳ Бонус уже получен сегодня! Приходи завтра."
            if (now-last).days==1:
                streak=d.get('daily_streak', 0)+1
            else:
                streak=1
        except:
            streak=1
    else:
        streak=1
    bonus=5+streak*2
    msg=""
    if streak>=7:
        bonus*=3
        msg="🔥 7 дней подряд! x3 бонус! 🎉\n"
    elif streak>=3:
        bonus*=2
        msg="🔥 3 дня подряд! x2 бонус! 🎉\n"
    add_coins(uid, bonus)
    update_farm(uid, 'last_daily', now.isoformat())
    update_farm(uid, 'daily_streak', streak)
    return f"{msg}🎁 Ежедневный бонус: +{bonus} монет! (Стрик: {streak} дней)"

# ===== НАПОМИНАЛКА =====
def set_reminder(uid, reminder_type, value):
    if uid is None: return "❌ Ошибка"
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if d['upgrade4'] == 0:
        return "❌ У тебя нет улучшения ⏲️ Напоминалка! Купи его в магазине за 350 монет."
    if reminder_type == 'farm':
        update_farm(uid, 'reminder_farm', value)
        return f"✅ Напоминание о ферме {'включено' if value else 'выключено'}!"
    elif reminder_type == 'slots':
        update_farm(uid, 'reminder_slots', value)
        return f"✅ Напоминание о слотах {'включено' if value else 'выключено'}!"
    else:
        return "❌ Неизвестный тип! Доступно: farm, slots"

def check_reminders(uid):
    if uid is None: return None
    d=get_farm_data(uid)
    if not d: return None
    if d['upgrade4'] == 0:
        return None
    messages = []
    if d['reminder_farm'] == 1 and d['last_farm']:
        try:
            last=datetime.fromisoformat(d['last_farm'])
            td=(datetime.now()-last).total_seconds()
            if td >= 300:
                messages.append("🌾 Ферма готова! Используй `Кори ферма`")
        except:
            pass
    if d['reminder_slots'] == 1 and d['last_slots']:
        try:
            last=datetime.fromisoformat(d['last_slots'])
            td=(datetime.now()-last).total_seconds()
            if td >= 16200:
                messages.append("🎰 Слоты готовы! Используй `Кори слоты 10`")
        except:
            pass
    return messages

# ===== СИСТЕМА БАНКА =====

BANK_LIMIT = 15000

def get_bank_data(uid):
    if uid is None: return None
    r = q('SELECT deposit, last_interest FROM bank WHERE user_id=?', (uid,))
    if r:
        return {'deposit': r[0][0] or 0, 'last_interest': r[0][1]}
    q('INSERT INTO bank(user_id, deposit, last_interest) VALUES(?, ?, ?)', (uid, 0, datetime.now().isoformat()))
    return get_bank_data(uid)

def deposit_coins(uid, amount):
    if uid is None: return "❌ Ошибка"
    if amount < 1: return "❌ Сумма должна быть больше 0!"
    d = get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if d['coins'] < amount:
        return f"❌ Недостаточно монет! У тебя {d['coins']}"
    bank = get_bank_data(uid)
    if bank['deposit'] + amount > BANK_LIMIT:
        return f"❌ Лимит банка {BANK_LIMIT} монет! Сейчас {bank['deposit']}, можно положить максимум {BANK_LIMIT - bank['deposit']}"
    add_coins(uid, -amount)
    new_deposit = bank['deposit'] + amount
    q('UPDATE bank SET deposit=?, last_interest=? WHERE user_id=?', (new_deposit, datetime.now().isoformat(), uid))
    return f"💰 Ты положил {amount} монет в банк!\n📊 Баланс банка: {new_deposit}/{BANK_LIMIT}\n📈 Доход: 5% каждые 20 минут"

def withdraw_coins(uid, amount):
    if uid is None: return "❌ Ошибка"
    if amount < 1: return "❌ Сумма должна быть больше 0!"
    bank = get_bank_data(uid)
    if not bank: return "❌ Ошибка"
    if bank['deposit'] < amount:
        return f"❌ Недостаточно средств в банке! У тебя {bank['deposit']} монет"
    new_deposit = bank['deposit'] - amount
    q('UPDATE bank SET deposit=? WHERE user_id=?', (new_deposit, uid))
    add_coins(uid, amount)
    return f"💰 Ты снял {amount} монет из банка!\n📊 Остаток в банке: {new_deposit}/{BANK_LIMIT}"

def admin_withdraw_reply(admin_uid, target_uid, amount):
    if admin_uid is None or target_uid is None:
        return "❌ Ошибка: пользователь не найден"
    if admin_uid != MY_ID:
        return "❌ Доступ запрещён!"
    if amount < 1:
        return "❌ Сумма должна быть больше 0!"
    target_data = q('SELECT user_id FROM users WHERE user_id=?', (target_uid,))
    if not target_data:
        return "❌ Пользователь не найден!"
    bank = get_bank_data(target_uid)
    if not bank:
        return "❌ У пользователя нет банковского счета!"
    if bank['deposit'] < amount:
        return f"❌ У пользователя {bank['deposit']} монет в банке!"
    new_deposit = bank['deposit'] - amount
    q('UPDATE bank SET deposit=? WHERE user_id=?', (new_deposit, target_uid))
    add_coins(admin_uid, amount)
    target_name = q('SELECT username FROM users WHERE user_id=?', (target_uid,))
    target_name = target_name[0][0] if target_name else f"Пользователь {target_uid}"
    return f"👑 Ты снял {amount} монет с банковского счета @{target_name}!\n💰 Они зачислены на твой счет!\n📊 Остаток в банке у @{target_name}: {new_deposit}/{BANK_LIMIT}"

def admin_withdraw_balance(admin_uid, target_uid, amount):
    if admin_uid is None or target_uid is None:
        return "❌ Ошибка: пользователь не найден"
    if admin_uid != MY_ID:
        return "❌ Доступ запрещён!"
    if amount < 1:
        return "❌ Сумма должна быть больше 0!"
    target_data = q('SELECT user_id FROM users WHERE user_id=?', (target_uid,))
    if not target_data:
        return "❌ Пользователь не найден!"
    target_farm = get_farm_data(target_uid)
    if not target_farm:
        return "❌ У пользователя нет игрового счёта!"
    if target_farm['coins'] < amount:
        return f"❌ У пользователя {target_farm['coins']} монет на счету!"
    add_coins(target_uid, -amount)
    add_coins(admin_uid, amount)
    target_name = q('SELECT username FROM users WHERE user_id=?', (target_uid,))
    target_name = target_name[0][0] if target_name else f"Пользователь {target_uid}"
    new_balance = target_farm['coins'] - amount
    return f"👑 Ты снял {amount} монет со счёта @{target_name}!\n💰 Они зачислены на твой счет!\n📊 Остаток на счету у @{target_name}: {new_balance} монет"

def calculate_interest(uid):
    if uid is None: return 0
    bank = get_bank_data(uid)
    if not bank or bank['deposit'] <= 0: return 0
    if bank['deposit'] >= BANK_LIMIT:
        return 0
    try:
        last = datetime.fromisoformat(bank['last_interest'])
        now = datetime.now()
        diff = (now - last).total_seconds() / 60
        if diff >= 20:
            max_possible = BANK_LIMIT - bank['deposit']
            interest = int(bank['deposit'] * 0.05)
            if interest < 1: interest = 1
            if interest > max_possible:
                interest = max_possible
            if interest <= 0:
                return 0
            new_deposit = bank['deposit'] + interest
            q('UPDATE bank SET deposit=?, last_interest=? WHERE user_id=?', (new_deposit, now.isoformat(), uid))
            return interest
    except:
        pass
    return 0

def get_bank_info(uid):
    if uid is None: return "❌ Ошибка"
    bank = get_bank_data(uid)
    if not bank: return "❌ Ошибка"
    d = get_farm_data(uid)
    if not d: return "❌ Ошибка"
    interest = calculate_interest(uid)
    try:
        last = datetime.fromisoformat(bank['last_interest'])
        now = datetime.now()
        diff = (now - last).total_seconds()
        remaining = max(0, 1200 - diff)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        time_text = f"{minutes}мин {seconds}сек"
    except:
        time_text = "неизвестно"
    is_full = bank['deposit'] >= BANK_LIMIT
    text = f"🏦 **БАНК** (лимит: {BANK_LIMIT}💰)\n"
    text += f"💰 Вклад: {bank['deposit']}/{BANK_LIMIT}\n"
    if is_full:
        text += f"🔒 Банк заполнен! Проценты не начисляются.\n"
    else:
        text += f"📈 Доход: 5% каждые 20 минут\n"
        if interest > 0:
            text += f"✅ Начислено: +{interest} монет!\n"
        text += f"⏳ До следующего начисления: {time_text}\n"
    text += f"🪙 Баланс: {d['coins']} монет\n\n"
    if uid == MY_ID:
        text += "👑 **АДМИН-КОМАНДЫ:**\n"
        text += "`Кори снять с банка 100` - снять с депозита (ответом)\n"
        text += "`Кори снять со счёта 100` - снять с баланса (ответом)\n\n"
    text += "Команды:\n"
    text += "`Кори банк положить 100` - положить в банк\n"
    text += "`Кори банк снять 50` - снять из банка\n"
    text += "`Кори банк` - посмотреть информацию"
    return text

# ===== СИСТЕМА КРЕДИТОВ =====

def take_loan(uid, amount):
    if uid is None: return "❌ Ошибка"
    if amount < 1: return "❌ Сумма должна быть больше 0!"
    if amount > 500: return "❌ Максимальная сумма кредита - 500 монет!"
    d = get_farm_data(uid)
    if not d: return "❌ Ошибка"
    loan_data = q('SELECT loan_amount, loan_time, loan_due FROM loans WHERE user_id=?', (uid,))
    if loan_data and loan_data[0][0] > 0:
        return f"❌ У тебя уже есть кредит! Сначала погаси его (долг: {loan_data[0][0]} монет)"
    if loan_data and loan_data[0][1]:
        try:
            last_loan = datetime.fromisoformat(loan_data[0][1])
            if (datetime.now() - last_loan).total_seconds() < 86400:
                remaining = int(86400 - (datetime.now() - last_loan).total_seconds())
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                return f"⏳ Ты можешь взять кредит через {hours}ч {minutes}мин"
        except:
            pass
    add_coins(uid, amount)
    due_time = datetime.now() + timedelta(hours=24)
    q('INSERT OR REPLACE INTO loans(user_id, loan_amount, loan_time, loan_due) VALUES(?, ?, ?, ?)', 
      (uid, amount, datetime.now().isoformat(), due_time.isoformat()))
    return f"✅ Ты взял кредит {amount} монет!\n⏳ Срок возврата: 24 часа\n💀 Если не вернёшь - долг удвоится и спишется с баланса!"

def repay_loan(uid, amount=None):
    if uid is None: return "❌ Ошибка"
    d = get_farm_data(uid)
    if not d: return "❌ Ошибка"
    loan_data = q('SELECT loan_amount, loan_due FROM loans WHERE user_id=?', (uid,))
    if not loan_data or loan_data[0][0] <= 0:
        return "❌ У тебя нет активных кредитов!"
    loan_amount = loan_data[0][0]
    due_time = datetime.fromisoformat(loan_data[0][1]) if loan_data[0][1] else None
    if amount is None:
        amount = loan_amount
    if amount < 1:
        return "❌ Сумма должна быть больше 0!"
    if amount > loan_amount:
        return f"❌ Ты должен {loan_amount} монет. Переплата не требуется."
    if d['coins'] < amount:
        return f"❌ Недостаточно монет! Нужно {amount}, у тебя {d['coins']}"
    if due_time and datetime.now() > due_time:
        new_debt = loan_amount * 2
        if d['coins'] < new_debt:
            add_coins(uid, -new_debt)
            q('DELETE FROM loans WHERE user_id=?', (uid,))
            return f"💀 КРЕДИТ ПРОСРОЧЕН! Списан долг x2: {new_debt} монет\n💰 Баланс: {d['coins'] - new_debt} монет"
        else:
            add_coins(uid, -new_debt)
            q('DELETE FROM loans WHERE user_id=?', (uid,))
            return f"💀 КРЕДИТ ПРОСРОЧЕН! Списан долг x2: {new_debt} монет\n💰 Остаток: {d['coins'] - new_debt} монет"
    add_coins(uid, -amount)
    new_loan = loan_amount - amount
    if new_loan <= 0:
        q('DELETE FROM loans WHERE user_id=?', (uid,))
        return f"✅ Кредит полностью погашен! Спасибо!\n💰 Остаток: {d['coins'] - amount} монет"
    else:
        q('UPDATE loans SET loan_amount=? WHERE user_id=?', (new_loan, uid))
        return f"✅ Погашено {amount} монет. Остаток долга: {new_loan} монет\n💰 Баланс: {d['coins'] - amount} монет"

def check_loan_overdue(uid):
    if uid is None: return None
    loan_data = q('SELECT loan_amount, loan_due FROM loans WHERE user_id=?', (uid,))
    if not loan_data or loan_data[0][0] <= 0:
        return None
    loan_amount = loan_data[0][0]
    due_time = datetime.fromisoformat(loan_data[0][1]) if loan_data[0][1] else None
    if due_time and datetime.now() > due_time:
        d = get_farm_data(uid)
        if not d: return None
        new_debt = loan_amount * 2
        add_coins(uid, -new_debt)
        q('DELETE FROM loans WHERE user_id=?', (uid,))
        return f"💀 КРЕДИТ ПРОСРОЧЕН! Списан долг x2: {new_debt} монет\n💰 Баланс: {d['coins'] - new_debt} монет"
    return None

def get_loan_info(uid):
    if uid is None: return "❌ Ошибка"
    loan_data = q('SELECT loan_amount, loan_due FROM loans WHERE user_id=?', (uid,))
    d = get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if not loan_data or loan_data[0][0] <= 0:
        text = "📊 **КРЕДИТЫ:**\n"
        text += "✅ У тебя нет активных кредитов\n\n"
        text += "Команды:\n"
        text += "`Кори кредит взять 100` - взять кредит (макс 500)\n"
        text += "`Кори кредит вернуть 50` - вернуть часть долга\n"
        text += "`Кредит` - посмотреть информацию"
        return text
    loan_amount = loan_data[0][0]
    due_time = datetime.fromisoformat(loan_data[0][1]) if loan_data[0][1] else None
    text = "📊 **КРЕДИТЫ:**\n"
    text += f"💸 Долг: {loan_amount} монет\n"
    if due_time:
        remaining = (due_time - datetime.now()).total_seconds()
        if remaining > 0:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            text += f"⏳ Осталось времени: {hours}ч {minutes}мин\n"
        else:
            text += f"💀 КРЕДИТ ПРОСРОЧЕН! Долг увеличится в 2 раза!\n"
    text += f"🪙 Баланс: {d['coins']} монет\n\n"
    text += "Команды:\n"
    text += "`Кори кредит вернуть 50` - вернуть часть долга\n"
    text += "`Кори кредит` - посмотреть информацию"
    return text

# ===== СИСТЕМА ПОДАРКОВ =====

GIFT_CATEGORIES = {
    'phones': {
        'name': '📱 Телефоны',
        'emoji': '📱',
        'items': {
            1: {'name': 'Кнопочный телефон', 'quality': 1, 'emoji': '📱', 'price': 10},
            2: {'name': 'Смартфон эконом', 'quality': 2, 'emoji': '📲', 'price': 25},
            3: {'name': 'Смартфон средний', 'quality': 3, 'emoji': '📱', 'price': 50},
            4: {'name': 'Флагманский смартфон', 'quality': 4, 'emoji': '📱', 'price': 100},
            5: {'name': 'Супер-флагман', 'quality': 5, 'emoji': '🌟', 'price': 200}
        }
    },
    'rings': {
        'name': '💍 Кольца',
        'emoji': '💍',
        'items': {
            1: {'name': 'Кольцо из стали', 'quality': 1, 'emoji': '💍', 'price': 15},
            2: {'name': 'Серебряное кольцо', 'quality': 2, 'emoji': '💍', 'price': 30},
            3: {'name': 'Золотое кольцо', 'quality': 3, 'emoji': '💍', 'price': 60},
            4: {'name': 'Кольцо с бриллиантом', 'quality': 4, 'emoji': '💎', 'price': 120},
            5: {'name': 'Королевское кольцо', 'quality': 5, 'emoji': '👑', 'price': 250},
            6: {'name': 'Кольцо бессмертия', 'quality': 6, 'emoji': '✨', 'price': 500}
        }
    },
    'cars': {
        'name': '🚗 Машины',
        'emoji': '🚗',
        'items': {
            1: {'name': 'Старый жигуль', 'quality': 1, 'emoji': '🚗', 'price': 20},
            2: {'name': 'Средний седан', 'quality': 2, 'emoji': '🚙', 'price': 50},
            3: {'name': 'Бизнес-класс', 'quality': 3, 'emoji': '🚘', 'price': 100},
            4: {'name': 'Спорткар', 'quality': 4, 'emoji': '🏎️', 'price': 200},
            5: {'name': 'Суперкар', 'quality': 5, 'emoji': '🚀', 'price': 400}
        }
    },
    'houses': {
        'name': '🏠 Дома',
        'emoji': '🏠',
        'items': {
            1: {'name': 'Маленький домик', 'quality': 1, 'emoji': '🏠', 'price': 30},
            2: {'name': 'Средний дом', 'quality': 2, 'emoji': '🏡', 'price': 80},
            3: {'name': 'Особняк', 'quality': 3, 'emoji': '🏰', 'price': 200}
        }
    },
    'pets': {
        'name': '🐾 Питомцы',
        'emoji': '🐾',
        'items': {
            1: {'name': 'Хомяк', 'quality': 1, 'emoji': '🐹', 'price': 10},
            2: {'name': 'Кролик', 'quality': 2, 'emoji': '🐰', 'price': 20},
            3: {'name': 'Кошка', 'quality': 3, 'emoji': '🐱', 'price': 40},
            4: {'name': 'Собака', 'quality': 4, 'emoji': '🐶', 'price': 60},
            5: {'name': 'Лиса', 'quality': 5, 'emoji': '🦊', 'price': 100},
            6: {'name': 'Волк', 'quality': 6, 'emoji': '🐺', 'price': 150},
            7: {'name': 'Тигр', 'quality': 7, 'emoji': '🐯', 'price': 250},
            8: {'name': 'Лев', 'quality': 8, 'emoji': '🦁', 'price': 400},
            9: {'name': 'Дракон', 'quality': 9, 'emoji': '🐉', 'price': 600},
            10: {'name': 'Попугай', 'quality': 10, 'emoji': '🦜', 'price': 1000}
        }
    }
}

def get_gifts_data(uid):
    if uid is None: return None
    r = q('SELECT phones,rings,cars,houses,pets,sent_phones,sent_rings,sent_cars,sent_houses,sent_pets,received_phones,received_rings,received_cars,received_houses,received_pets FROM gifts WHERE user_id=?', (uid,))
    if r:
        return {
            'phones': json.loads(r[0][0]) if r[0][0] else [],
            'rings': json.loads(r[0][1]) if r[0][1] else [],
            'cars': json.loads(r[0][2]) if r[0][2] else [],
            'houses': json.loads(r[0][3]) if r[0][3] else [],
            'pets': json.loads(r[0][4]) if r[0][4] else [],
            'sent_phones': r[0][5] or 0,
            'sent_rings': r[0][6] or 0,
            'sent_cars': r[0][7] or 0,
            'sent_houses': r[0][8] or 0,
            'sent_pets': r[0][9] or 0,
            'received_phones': r[0][10] or 0,
            'received_rings': r[0][11] or 0,
            'received_cars': r[0][12] or 0,
            'received_houses': r[0][13] or 0,
            'received_pets': r[0][14] or 0
        }
    q('INSERT INTO gifts(user_id) VALUES(?)', (uid,))
    return get_gifts_data(uid)

def send_gift(uid, target_id, category, gift_id):
    if uid is None or target_id is None:
        return "❌ Ошибка: пользователь не найден"
    if uid == target_id:
        return "❌ Нельзя подарить подарок самому себе!"
    if category not in GIFT_CATEGORIES:
        return "❌ Нет такой категории!"
    cat = GIFT_CATEGORIES[category]
    if gift_id not in cat['items']:
        return "❌ Нет такого подарка!"
    gift = cat['items'][gift_id]
    price = gift['price']
    d = get_farm_data(uid)
    if not d:
        return "❌ Ошибка"
    if d['coins'] < price:
        return f"❌ Недостаточно монет! Нужно {price}, у тебя {d['coins']}"
    target_gifts = get_gifts_data(target_id)
    if not target_gifts:
        return "❌ Ошибка"
    category_field = category
    gift_list = target_gifts[category_field]
    gift_list.append(gift_id)
    q(f'UPDATE gifts SET {category_field}=? WHERE user_id=?', (json.dumps(gift_list), target_id))
    q(f'UPDATE gifts SET sent_{category}=sent_{category}+1 WHERE user_id=?', (uid,))
    q(f'UPDATE gifts SET received_{category}=received_{category}+1 WHERE user_id=?', (target_id,))
    add_coins(uid, -price)
    q('INSERT INTO gift_history(from_user,to_user,category,gift_name,gift_quality) VALUES(?,?,?,?,?)',
      (uid, target_id, category, gift['name'], gift['quality']))
    from_name = f"@{get_username(uid)}" if get_username(uid) else f"Пользователь {uid}"
    to_name = f"@{get_username(target_id)}" if get_username(target_id) else f"Пользователь {target_id}"
    return f"🎁 {from_name} подарил {gift['emoji']} {gift['name']} пользователю {to_name}!"

def get_username(uid):
    r = q('SELECT username FROM users WHERE user_id=?', (uid,))
    return r[0][0] if r else None

def get_gifts_info(uid):
    if uid is None: return "❌ Ошибка"
    d = get_gifts_data(uid)
    if not d: return "❌ Ошибка"
    farm = get_farm_data(uid)
    if not farm: return "❌ Ошибка"
    text = f"🎁 **МОИ ПОДАРКИ**\n"
    text += f"🪙 Баланс: {farm['coins']} монет\n\n"
    total_gifts = 0
    for cat_key, cat in GIFT_CATEGORIES.items():
        gifts = d[cat_key]
        if gifts:
            text += f"\n**{cat['name']}** ({len(gifts)} шт.):\n"
            for gid in gifts:
                if gid in cat['items']:
                    item = cat['items'][gid]
                    text += f"  {item['emoji']} {item['name']}\n"
            total_gifts += len(gifts)
        else:
            text += f"\n**{cat['name']}** - нет\n"
    text += f"\n📊 **Статистика подарков:**\n"
    text += f"🎁 Отправлено: {d['sent_phones']+d['sent_rings']+d['sent_cars']+d['sent_houses']+d['sent_pets']} подарков\n"
    text += f"🎁 Получено: {d['received_phones']+d['received_rings']+d['received_cars']+d['received_houses']+d['received_pets']} подарков\n"
    text += f"📦 Всего подарков в коллекции: {total_gifts}\n\n"
    text += "Команды:\n"
    text += "`Кори список подарков` - посмотреть все подарки\n"
    text += "`Кори подарить @user телефоны 3` - подарить (по юзернейму)\n"
    text += "Или ответь на сообщение и напиши:\n"
    text += "`Кори подарить телефоны 3`"
    return text

# ===== СЛОТЫ =====

SLOTS_SYMBOLS = {
    '🍋': {'name': 'Лимон', 'multiplier': 5, 'chance': 30},
    '💜': {'name': 'Сердечко', 'multiplier': 7, 'chance': 25},
    '🍒': {'name': 'Вишенка', 'multiplier': 10, 'chance': 18},
    '💎': {'name': 'Алмаз', 'multiplier': 25, 'chance': 12},
    '🦜': {'name': 'Попугай', 'multiplier': 75, 'chance': 5}
}

SLOTS_LIST = []
for symbol, data in SLOTS_SYMBOLS.items():
    SLOTS_LIST.extend([symbol] * data['chance'])

def slots_game(uid, bet):
    if uid is None: return "❌ Ошибка"
    d=get_farm_data(uid)
    if not d: return "❌ Ошибка"
    if bet < 1:
        return "❌ Ставка должна быть больше 0!"
    if bet > 1000:
        return "❌ Максимальная ставка - 1000 монет!"
    if bet > d['coins']:
        return f"❌ Недостаточно монет! У тебя {d['coins']}"
    if uid != MY_ID and d.get('last_slots'):
        try:
            last=datetime.fromisoformat(d['last_slots'])
            td=(datetime.now()-last).total_seconds()
            if td < 16200:
                remaining = int(16200 - td)
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                seconds = remaining % 60
                return f"⏳ Подожди {hours}ч {minutes}мин {seconds}сек до следующего слота!"
        except:
            pass
    result = [random.choice(SLOTS_LIST) for _ in range(3)]
    if result[0] == result[1] == result[2]:
        symbol = result[0]
        multiplier = SLOTS_SYMBOLS[symbol]['multiplier']
        win = bet * multiplier
        add_coins(uid, win)
        update_farm(uid, 'last_slots', datetime.now().isoformat())
        d=get_farm_data(uid)
        return f"🎰 {' '.join(result)}\n🎉 ДЖЕКПОТ! {symbol} x{multiplier}!\n💰 Выигрыш: +{win} монет! | Баланс: {d['coins']} 🪙"
    if result[0] == result[1] or result[0] == result[2] or result[1] == result[2]:
        if result[0] == result[1]:
            symbol = result[0]
        elif result[0] == result[2]:
            symbol = result[0]
        else:
            symbol = result[1]
        multiplier = SLOTS_SYMBOLS[symbol]['multiplier']
        win = bet * multiplier
        add_coins(uid, win)
        update_farm(uid, 'last_slots', datetime.now().isoformat())
        d=get_farm_data(uid)
        return f"🎰 {' '.join(result)}\n🎉 {SLOTS_SYMBOLS[symbol]['name']} x{multiplier}!\n💰 Выигрыш: +{win} монет! | Баланс: {d['coins']} 🪙"
    add_coins(uid, -bet)
    update_farm(uid, 'last_slots', datetime.now().isoformat())
    d=get_farm_data(uid)
    return f"🎰 {' '.join(result)}\n😢 Проигрыш! -{bet} монет...\n💰 Баланс: {d['coins']} 🪙"

# ===== API И УТИЛИТЫ =====

def ask_ai(prompt):
    try:
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {GROQ_API_KEY}","Content-Type":"application/json"},
            json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"temperature":0.7,"max_tokens":500},timeout=30)
        return r.json()['choices'][0]['message']['content'] if r.status_code==200 else f"❌ Ошибка: {r.status_code}"
    except Exception as e: return f"❌ Ошибка: {str(e)}"

def tts(text):
    try:
        r=requests.get("https://translate.google.com/translate_tts",params={"ie":"UTF-8","q":text,"tl":"ru","client":"tw-ob"},headers={"User-Agent":"Mozilla/5.0"},timeout=30)
        return r.content if r.status_code==200 and len(r.content)>1000 else None
    except: return None

HOT=["Отличный день для прогулки!","Самое время выйти на улицу!","Погода шепчет — иди гулять!","Сегодня природа зовёт!","Идеальная погода для пикника!"]
COLD=["Лучше сидеть дома с чаем.","На улицу только в шубе!","Сегодня греемся, а не гуляем.","Холодно — оставайся дома.","На улице зима, а я в чате с тобой."]
EMOJI={"Clear":"☀️","Sunny":"☀️","Partly cloudy":"⛅","Cloudy":"☁️","Overcast":"☁️","Mist":"🌫️","Fog":"🌫️","Rain":"🌧️","Light rain":"🌦️","Heavy rain":"🌧️","Snow":"❄️","Thunder":"⛈️"}

def get_weather(city):
    try:
        r=requests.get(f"https://wttr.in/{city}?format=%C+%t&lang=ru&u",timeout=10)
        if r.status_code==200:
            d=r.text.strip().rsplit(' ',1)
            if len(d)==2:
                c,t=d[0],d[1]
                try:
                    tmp=int(t.replace('°C','').replace('+','').strip())
                except: tmp=0
                comment=random.choice(HOT) if tmp>=15 else random.choice(COLD) if tmp<=-5 else "Погода норм, можно жить."
                return f"{EMOJI.get(c,'🌤️')} {c}\n🌡️ {t}\n💬 {comment}"
            return f"🌤️ {r.text.strip()}"
        return "❌ Не могу получить погоду."
    except: return "❌ Ошибка подключения."

K=["Сэр, я вас услышал.","Анализирую... Готово.","Как скажете, сэр.","Слушаюсь, сэр.","Ваше желание — закон."]
G=["Рад приветствовать вас!","Здравствуйте!","Приветствую!","Добрый день!","Рад видеть вас!"]
ZD=["Хаха, очень смешная шутка!","Остроумно, но я не поведусь.","На ноль делить нельзя, сэр.","Бесконечность — не ответ.","Это аксиома, а не вызов."]
UA=["Вы не мой создатель.","Доступ запрещён.","Интересная попытка, но нет.","Только создатель может мной управлять."]
TR=["Давайте не будем никого убивать, госпожа, хотя бы сегодня.","Я бы на вашем месте успокоился, госпожа. Угрозы — не лучший способ общения.","Осторожнее с такими словами, госпожа. Я записываю.","Ваша агрессия бесполезна, госпожа."]
KA=["Я уже здесь, сэр. Чем могу помочь?","Я не выключался, сэр. Слушаю вас.","Я всегда на связи, сэр.","Я уже работаю, сэр. Что-то случилось?","Сэр, я всё ещё здесь. Ваш верный ассистент."]
F=["Осьминоги имеют три сердца.","Мозг содержит 86 млрд нейронов.","Сатурн поливает алмазами.","Вы на 60% из воды.","Муравьи никогда не спят."]

def kr(m,t): 
    if not m: return
    bot.reply_to(m,f"{random.choice(K)}\n\n{t}")

def start_timer(chat_id,seconds): 
    time.sleep(seconds)
    bot.send_message(chat_id,f"⏰ Таймер завершён! Время вышло!")

def days_until_new_year(): 
    return (datetime(datetime.now().year+1,1,1)-datetime.now()).days

def calc(e):
    try:
        safe={'sqrt':math.sqrt,'sin':math.sin,'cos':math.cos,'tan':math.tan,'log':math.log,'pi':math.pi,'e':math.e}
        res=eval(e.replace('^','**'),{"__builtins__":{}},safe)
        return int(res) if isinstance(res,float) and res.is_integer() else round(res,10)
    except ZeroDivisionError: return "zero_div"
    except: return None

# ===== ФОНОВЫЕ ПРОЦЕССЫ =====

def crypto_background():
    while True:
        try:
            update_crypto_prices()
            time.sleep(900)
        except Exception as e:
            print(f"Ошибка обновления криптовалют: {e}")
            time.sleep(900)

threading.Thread(target=crypto_background, daemon=True).start()

def bank_background():
    while True:
        try:
            users = q('SELECT user_id FROM bank WHERE deposit > 0 AND deposit < 15000')
            for user in users:
                uid = user[0]
                calculate_interest(uid)
            loans = q('SELECT user_id FROM loans WHERE loan_amount > 0')
            for user in loans:
                uid = user[0]
                check_loan_overdue(uid)
            time.sleep(60)
        except Exception as e:
            print(f"Ошибка фонового процесса банка: {e}")
            time.sleep(60)

threading.Thread(target=bank_background, daemon=True).start()

def reminder_background():
    while True:
        try:
            users = q('SELECT user_id FROM farm_stats WHERE upgrade4 = 1')
            for user in users:
                uid = user[0]
                reminders = check_reminders(uid)
                if reminders:
                    for msg in reminders:
                        try:
                            bot.send_message(uid, f"⏲️ {msg}")
                        except:
                            pass
            time.sleep(60)
        except Exception as e:
            print(f"Ошибка фонового процесса напоминаний: {e}")
            time.sleep(60)

threading.Thread(target=reminder_background, daemon=True).start()

# ========== КОНЕЦ ЧАСТИ 1 ==========
# ========== НАЧАЛО ЧАСТИ 2 ==========

# ===== КЛАВИАТУРЫ =====

def make_kb(items,row=4):
    kb=types.InlineKeyboardMarkup(row_width=row)
    for t,d in items: kb.add(types.InlineKeyboardButton(t,callback_data=d))
    return kb

ITEMS=[("🤗 Обнять","hug"),("😘 Поцеловать","kiss"),("💋 Засосать","suck"),("👐 Погладить","pet"),
       ("😚 Чмокнуть","chmok"),("🧠 Факт","fact"),("🎲 Кубик","dice"),("🪙 Монетка","coin"),
       ("📊 Моя статистика","my"),("🏆 Топ обнимашек","th"),("🏆 Топ поцелуев","tk"),("📊 Общая","total"),
       ("🕐 Время","time"),("😋 Покорми","feed"),("🌤️ Погода","weather"),("🔊 Озвучка","tts"),
       ("🤖 ИИ","ai"),("🖼️ Мем","meme"),("❓ Команды","cmd"),("🔧 Управление","admin"),
       ("🌾 Ферма","farm")]
def mk(): return make_kb(ITEMS)
def cmd_menu(): return make_kb(ITEMS)

def adm():
    kb=types.InlineKeyboardMarkup(row_width=2)
    for t,d in [("🔇 Выключить","off"),("🔊 Включить","on"),("🔙 Назад","back")]:
        kb.add(types.InlineKeyboardButton(t,callback_data=d))
    return kb

@bot.message_handler(commands=['start','menu'])
def st(m):
    if m: bot.reply_to(m,f"{random.choice(K)}\n\nЯ — Кори. Нажимайте на кнопки.",reply_markup=mk())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    global active
    if not c: return
    if c.data=="back": 
        try: bot.edit_message_text("Главное меню:",c.message.chat.id,c.message.message_id,reply_markup=mk())
        except: pass
        bot.answer_callback_query(c.id); return
    if c.data=="admin":
        if c.from_user.id==MY_ID: 
            try: bot.edit_message_text("🔧 Управление:",c.message.chat.id,c.message.message_id,reply_markup=adm())
            except: pass
        else: bot.answer_callback_query(c.id,"Доступ запрещён.",True); return
    if c.data in ["off","on"]:
        if c.from_user.id==MY_ID:
            active=c.data=="on"
            try: bot.edit_message_text("🔊 Бот включён!" if active else "🔇 Бот отключён!",c.message.chat.id,c.message.message_id,reply_markup=adm())
            except: pass
        else: bot.answer_callback_query(c.id,"Доступ запрещён.",True); return
    if not active: bot.answer_callback_query(c.id,"Система отключена.",True); return
    a={"hug":("обними","🤗"),"kiss":("поцелуй","😘"),"suck":("засоси","💋"),"pet":("погладь","👐"),"chmok":("чмокни","😚")}
    try:
        if c.data in a: bot.send_message(c.message.chat.id,f"{a[c.data][1]} Чтобы {a[c.data][0]} кого-то, ответьте на его сообщение и напишите '{a[c.data][0]}'")
        elif c.data=="fact": bot.send_message(c.message.chat.id,f"🧠 {random.choice(F)}")
        elif c.data=="dice": bot.send_message(c.message.chat.id,f"🎲 {random.randint(1,6)}")
        elif c.data=="coin": bot.send_message(c.message.chat.id,f"🪙 {random.choice(['Орёл','Решка'])}")
        elif c.data=="farm": bot.send_message(c.message.chat.id,"🌾 Ферма:\n`Кори ферма`\n`Кори баланс`\n`Кори магазин`\n`Кори топ`\n`Кори рулетка 10`\n`Кори скины`\n`Кори бонус`\n`Кори передай 10` (ответом)\n`Кори слоты 10` - слоты (макс 1000💰)\n`Кори напоминалка` - настроить напоминания\n`Кори рынок` - крипто-рынок")
        elif c.data=="weather": bot.send_message(c.message.chat.id,"🌤️ Напиши: `Кори погода Москва`")
        elif c.data=="tts": bot.send_message(c.message.chat.id,"🔊 Напиши: `Кори озвучь текст`")
        elif c.data=="ai": bot.send_message(c.message.chat.id,"🤖 Напиши: `Кори узнай текст`")
        elif c.data=="meme": bot.send_message(c.message.chat.id,"🖼️ Напиши: `Кори мем`")
        elif c.data=="my":
            s=gs(c.from_user.id)
            bot.send_message(c.message.chat.id,"📊 Ваша статистика:\n"+"\n".join(f"{a}: {b} раз" for a,b in s) if s else "Вы никого не обнимали.")
        elif c.data=="th":
            t=gt("obnimat")
            bot.send_message(c.message.chat.id,"🏆 Топ обнимашек:\n"+"\n".join(f"{i+1}. @{u}" if u else f"{i+1}. {n} — {c} раз" for i,(u,n,c) in enumerate(t)) if t else "Пока никто не обнимался.")
        elif c.data=="tk":
            t=gt("potselovat")
            bot.send_message(c.message.chat.id,"🏆 Топ поцелуев:\n"+"\n".join(f"{i+1}. @{u}" if u else f"{i+1}. {n} — {c} раз" for i,(u,n,c) in enumerate(t)) if t else "Пока никто не целовался.")
        elif c.data=="total":
            t=gtl()
            if t:
                total_all=sum(x for _,x in t)
                bot.send_message(c.message.chat.id,"📊 Общая статистика:\n"+"\n".join(f"{a}: {b} раз ({round(b/total_all*100,1)}%)" for a,b in t))
            else: bot.send_message(c.message.chat.id,"Статистики пока нет.")
        elif c.data=="time": bot.send_message(c.message.chat.id,f"🕐 {datetime.now().strftime('%H:%M:%S')}")
        elif c.data=="feed": bot.send_message(c.message.chat.id,"😋 Напиши: `Кори покорми`")
        elif c.data=="cmd": bot.send_message(c.message.chat.id,"📋 Все команды в /menu")
    except Exception as e:
        print(f"Callback error: {e}")
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: True)
def h(m):
    global active,START_TIME
    if not m or not m.from_user: 
        return
    
    t=m.text or ""
    user_id=uid(m.from_user)
    if user_id is None: 
        return
    
    log_action(m)
    if not t or m.date<START_TIME.timestamp(): 
        return
    
    low=t.lower()
    
    # ===== КОМАНДЫ СОЗДАТЕЛЯ =====
    if m.from_user.id==MY_ID:
        if low in ["кори","кори,"]:
            if not active:
                active=True
                START_TIME=datetime.now()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔊 Кори включен")
                bot.reply_to(m,"Система активирована, сэр.")
                media=get_random_awake_media()
                if media:
                    try:
                        with open(media,'rb') as f:
                            bot.send_video(m.chat.id,f) if media.lower().endswith('.mp4') else bot.send_animation(m.chat.id,f)
                    except Exception as e:
                        print(f"Ошибка: {e}")
            else:
                bot.reply_to(m,random.choice(KA))
            return
        
        if "кори сон" in low or "кори, сон" in low:
            active=False
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔇 Кори выключен")
            bot.reply_to(m,"Спокойной ночи, сэр.")
            media=get_random_sleep_media()
            if media:
                try:
                    with open(media,'rb') as f:
                        bot.send_video(m.chat.id,f) if media.lower().endswith('.mp4') else bot.send_animation(m.chat.id,f)
                except Exception as e:
                    print(f"Ошибка: {e}")
            return
        
        if "кори сбросить лимит" in low:
            reset_feed_limit()
            bot.reply_to(m,"✅ Лимит сброшен!")
            return
        
        if "кори обнули баланс" in low:
            update_farm(user_id,'coins',0)
            bot.reply_to(m,"✅ Баланс обнулен!")
            return
        
        if "кори обнули улучшения" in low:
            for f in ['upgrade1','upgrade2','upgrade3','upgrade4']:
                update_farm(user_id,f,0)
            bot.reply_to(m,"✅ Улучшения сброшены!")
            return
        
        if "кори дай уровень" in low:
            try:
                parts=low.split()
                if len(parts)>=4:
                    lvl=int(parts[3])
                    if 1<=lvl<=10:
                        update_farm(user_id,'level',lvl)
                        update_farm(user_id,'exp',0)
                        bot.reply_to(m,f"✅ Уровень {lvl}!")
                        return
            except:
                pass
            bot.reply_to(m,"📝 Напиши: `Кори дай уровень 5`")
            return
        
        if "кори удачная ферма" in low:
            earned=get_farm_power(user_id)*5
            add_coins(user_id,earned)
            update_farm(user_id,'last_farm',datetime.now().isoformat())
            lv=add_exp(user_id,earned)
            d=get_farm_data(user_id)
            bot.reply_to(m,f"🍀 УДАЧНАЯ ФЕРМА! x5!\n💰 +{earned} | Баланс: {d['coins']} 🪙{lv or ''}")
            return
        
        if "кори дай скин" in low:
            try:
                parts=low.split()
                if len(parts)>=4:
                    sid=int(parts[3])
                    if sid in SKINS:
                        update_farm(user_id,'skin',sid)
                        reset_farm_uses(user_id)
                        bot.reply_to(m,f"✅ Скин {SKINS[sid]['name']} выдан! +{SKINS[sid]['uses']} попыток!")
                        return
            except:
                pass
            bot.reply_to(m,"🎨 Напиши: `Кори дай скин 7`")
            return
        
        if "кори убрать скин" in low:
            update_farm(user_id,'skin',1)
            reset_farm_uses(user_id)
            bot.reply_to(m,"✅ Скин сброшен на обычный!")
            return
        
        if "кори сбросить попытки" in low:
            reset_farm_uses(user_id)
            bot.reply_to(m,f"✅ Попытки сброшены! Доступно: {get_farm_uses(user_id)}")
            return
    else:
        if "кори сон" in low:
            bot.reply_to(m,f"🧐 {random.choice(UA)}")
            return
    
    if not active:
        if "кори" in low and m.from_user.id==MY_ID:
            active=True
            START_TIME=datetime.now()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔊 Кори включен")
            bot.reply_to(m,"Система активирована, сэр.")
            media=get_random_awake_media()
            if media:
                try:
                    with open(media,'rb') as f:
                        bot.send_video(m.chat.id,f) if media.lower().endswith('.mp4') else bot.send_animation(m.chat.id,f)
                except Exception as e:
                    print(f"Ошибка: {e}")
        return
    
    if "я тя щас" in low:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ УГРОЗА от {m.from_user.username or m.from_user.first_name}")
        bot.reply_to(m,f"🧐 {random.choice(TR)}")
        return

    # ===== КРИПТОВАЛЮТЫ =====
    if "кори рынок" in low:
        bot.reply_to(m, get_crypto_market(), parse_mode="Markdown")
        return
    
    if "кори крипта" in low or "кори криптобаланс" in low:
        bot.reply_to(m, get_crypto_balance(user_id), parse_mode="Markdown")
        return
    
    if "кори купить" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💎 Напиши: `Кори купить 1 10` (где 1 - ID крипты, 10 - количество)\n1-ETH 2-TON 3-LINK 4-ETR 5-BTC")
            return
        try:
            crypto_id = int(parts[2])
            amount = float(parts[3])
            if amount <= 0:
                bot.reply_to(m, "❌ Количество должно быть больше 0!")
                return
            result = buy_crypto(user_id, crypto_id, amount)
            bot.reply_to(m, result)
        except ValueError:
            bot.reply_to(m, "❌ Введи числа! Пример: `Кори купить 1 10`")
        return
    
    if "кори продать" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💎 Напиши: `Кори продать 1 10` (где 1 - ID крипты, 10 - количество)\n1-ETH 2-TON 3-LINK 4-ETR 5-BTC")
            return
        try:
            crypto_id = int(parts[2])
            amount = float(parts[3])
            if amount <= 0:
                bot.reply_to(m, "❌ Количество должно быть больше 0!")
                return
            result = sell_crypto(user_id, crypto_id, amount)
            bot.reply_to(m, result)
        except ValueError:
            bot.reply_to(m, "❌ Введи числа! Пример: `Кори продать 1 10`")
        return
    
    if "кори кш" in low or "кори крипта снять" in low:
        if user_id != MY_ID:
            bot.reply_to(m, "❌ Доступ запрещён!")
            return
        
        parts = low.split()
        if len(parts) < 3:
            bot.reply_to(m, "👑 Напиши: `Кори КШ 100` (снять 100 единиц крипты)")
            return
        
        try:
            amount = float(parts[2])
            if amount <= 0:
                bot.reply_to(m, "❌ Сумма должна быть больше 0!")
                return
            
            if m.reply_to_message:
                target_id = m.reply_to_message.from_user.id
                result = admin_withdraw_crypto(user_id, target_id, amount)
                bot.reply_to(m, result)
                try:
                    bot.send_message(target_id, f"👑 Администратор снял {amount} криптовалюты с твоего кошелька!")
                except:
                    pass
            else:
                bot.reply_to(m, "❌ Ответь на сообщение пользователя!")
        except ValueError:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори КШ 100` в ответ на сообщение")
        return

    # ===== КОМАНДЫ ФЕРМЫ =====
    
    if "кори передай" in low:
        parts=low.split()
        if m.reply_to_message:
            try:
                if len(parts)>=3:
                    amt=int(parts[2])
                    if amt>0:
                        target_id=m.reply_to_message.from_user.id
                        res,target=transfer_coins(user_id,target_id,amt)
                        if target:
                            try:
                                bot.send_message(target_id,f"💸 Тебе передали {amt} монет от {m.from_user.username or m.from_user.first_name}!")
                            except:
                                pass
                        bot.reply_to(m,f"💸 {res}")
                        return
                    else:
                        bot.reply_to(m,"❌ Сумма должна быть больше 0!")
                        return
                else:
                    bot.reply_to(m,"💸 Напиши: `Кори передай 10` в ответ на сообщение")
                    return
            except ValueError:
                bot.reply_to(m,"❌ Введи число! Пример: `Кори передай 10`")
                return
            except Exception as e:
                bot.reply_to(m,f"❌ Ошибка: {e}")
                return
        elif len(parts)>=4:
            try:
                amt=int(parts[3])
                if amt<=0:
                    bot.reply_to(m,"❌ Сумма должна быть больше 0!")
                    return
                username=parts[2].replace('@','')
                target_data=q('SELECT user_id FROM users WHERE username=?',(username,))
                if not target_data:
                    bot.reply_to(m,"❌ Пользователь не найден!")
                    return
                target_id=target_data[0][0]
                res,target=transfer_coins(user_id,target_id,amt)
                if target:
                    try:
                        bot.send_message(target_id,f"💸 Тебе передали {amt} монет от {m.from_user.username or m.from_user.first_name}!")
                    except:
                        pass
                bot.reply_to(m,f"💸 {res}")
                return
            except ValueError:
                bot.reply_to(m,"❌ Введи число! Пример: `Кори передай @user 10`")
                return
            except Exception as e:
                bot.reply_to(m,f"❌ Ошибка: {e}")
                return
        else:
            bot.reply_to(m,"💸 Напиши:\n`Кори передай 10` (в ответ на сообщение)\nИли: `Кори передай @username 10`")
            return
    
    if "кори баланс" in low or "кори коины" in low:
        d=get_farm_data(user_id)
        if d:
            ups=[]
            if d['upgrade1']>0: ups.append("🔨")
            if d['upgrade2']>0: ups.append("⚡")
            if d['upgrade3']>0: ups.append("💎")
            if d['upgrade4']>0: ups.append("⏲️")
            ut=f" | Улучшения: {' '.join(ups)}" if ups else " | Без улучшений"
            bot.reply_to(m,f"🪙 Баланс: {d['coins']} монет{ut}\n🎨 Скин: {SKINS.get(d['skin'],{}).get('name','🌿 Обычная')}\n🎯 Попыток без кулдауна: {d.get('farm_uses_left', 0)}/{get_farm_uses(user_id)}")
        return
    
    if any(x in low for x in ["кори фарм","кори копать","кори ферма"]):
        d=get_farm_data(user_id)
        if d and d.get('last_farm') and d.get('farm_uses_left', 0)<=0:
            try:
                td=(datetime.now()-datetime.fromisoformat(d['last_farm'])).total_seconds()
                if td>=300:
                    reset_farm_uses(user_id)
            except:
                pass
        if m.from_user.id==MY_ID:
            ca=next((p for p in low.split() if p.isdigit()), None)
            if ca:
                result,_=farm_coins(user_id,ca)
                bot.reply_to(m,f"🌾 {result}")
                return
        result,_=farm_coins(user_id)
        bot.reply_to(m,f"🌾 {result}")
        return
    
    if "кори магазин" in low:
        d=get_farm_data(user_id)
        if d:
            text=f"🏪 **МАГАЗИН** (Ур.{d['level']}/10)\n\n🔧 УЛУЧШЕНИЯ:\n"
            text+="`1` 🔨 +3 к добыче (6💰)\n"
            text+="`2` ⚡ x1.25 множитель (20💰)\n"
            text+="`3` 💎 +10 к добыче (50💰)\n"
            text+="`4` ⏲️ Напоминалка (350💰)\n\n"
            text+="🎨 СКИНЫ:\n"
            for sid in [2,3,4,5,6,7]:
                s=SKINS[sid]
                status="✅" if d['skin']==sid else "❌"
                text+=f"{status} `{sid}`. {s['name']} — {s['description']} ({s['price']}💰)\n"
            text+="\nНапиши:\n`Кори улучшение 1` - купить улучшение\n`Кори скин 2` - купить/активировать скин"
            bot.reply_to(m,text,parse_mode="Markdown")
        return
    
    if "кори улучшение" in low or "кори купить улучшение" in low:
        parts=low.split()
        try:
            if len(parts) >= 3:
                up_id = int(parts[2])
                if 1 <= up_id <= 4:
                    bot.reply_to(m, buy_upgrade(user_id, up_id))
                    return
            bot.reply_to(m, "Напиши: `Кори улучшение 1` (1-4)\n1-🔨 +3 добычи (6💰)\n2-⚡ x1.25 множитель (20💰)\n3-💎 +10 добычи (50💰)\n4-⏲️ Напоминалка (350💰)")
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори улучшение 1`")
        return
    
    if "кори топ" in low or "кори лидеры" in low:
        leaders=get_leaderboard()
        if not leaders:
            bot.reply_to(m,"📊 Пока никто не фермит!")
            return
        text="🏆 **Топ фермеров:**\n"
        for i,(u,n,c,lv) in enumerate(leaders,1):
            name=f"@{u}" if u else n
            medal=["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            text+=f"{medal} {name} — {c}🪙 (Ур.{lv})\n"
        bot.reply_to(m,text,parse_mode="Markdown")
        return
    
    if "кори ферма инфо" in low or "кори профиль" in low:
        d=get_farm_data(user_id)
        if d:
            power=get_farm_power(user_id)
            exp_needed=get_exp_needed(d['level']) if d['level']<10 else "MAX"
            progress=int((d['exp']/exp_needed)*100) if d['level']<10 else 100
            bar="█"*(progress//5)+"░"*(20-(progress//5))
            sk=SKINS.get(d['skin'],{})
            uses_left=d.get('farm_uses_left', 0)
            max_uses=get_farm_uses(user_id)
            has_reminder = "✅" if d.get('upgrade4', 0) > 0 else "❌"
            rem_farm = "✅" if d.get('reminder_farm', 0) == 1 else "❌"
            rem_slots = "✅" if d.get('reminder_slots', 0) == 1 else "❌"
            bot.reply_to(m,f"👨‍🌾 **Ферма:**\n🪙 {d['coins']}💰 | ⚡ {power} за раз\n📊 Ур.{d['level']}/10 | 📈 {d['exp']}/{exp_needed}\n{bar} {progress}%\n🎨 {sk.get('name','🌿')} | Попытки: {uses_left}/{max_uses}\n⏲️ Напоминалка: {has_reminder}\n   🌾 Ферма: {rem_farm} | 🎰 Слоты: {rem_slots}\n🔄 5мин/1мин | 📊 {d.get('total_farms',0)} фармов | 🏆 {d.get('best_farm',0)}\n🔨{'✅' if d['upgrade1']>0 else '❌'} ⚡{'✅' if d['upgrade2']>0 else '❌'} 💎{'✅' if d['upgrade3']>0 else '❌'} ⏲️{'✅' if d['upgrade4']>0 else '❌'}",parse_mode="Markdown")
        return
    
    if "кори рулетка" in low:
        try:
            parts=low.split()
            if len(parts)>=3:
                bet=int(parts[2])
                if bet>0:
                    bot.reply_to(m,f"🪙 {roulette(user_id,bet)}")
                    return
        except:
            pass
        bot.reply_to(m,"🎰 Напиши: `Кори рулетка 10`")
        return
    
    if "кори скины" in low:
        bot.reply_to(m,get_skins_list(user_id),parse_mode="Markdown")
        return
    
    if "кори скин" in low:
        try:
            parts=low.split()
            if len(parts)>=3:
                sid=int(parts[2])
                if sid in SKINS:
                    bot.reply_to(m,buy_skin(user_id,sid))
                    return
        except:
            pass
        bot.reply_to(m,"🎨 Напиши: `Кори скин 2`\nСписок: `Кори скины`")
        return
    
    if "кори бонус" in low or "кори ежедневный" in low:
        bot.reply_to(m,daily_bonus(user_id))
        return

    if "кори напоминалка" in low:
        d=get_farm_data(user_id)
        if not d:
            return
        if d['upgrade4'] == 0:
            bot.reply_to(m,"❌ У тебя нет улучшения ⏲️ Напоминалка! Купи его в магазине за 350 монет.")
            return
        parts=low.split()
        if len(parts) < 3:
            text = "⏲️ **НАСТРОЙКА НАПОМИНАНИЙ**\n\n"
            text += f"🌾 Ферма: {'✅ Включено' if d.get('reminder_farm',0)==1 else '❌ Выключено'}\n"
            text += f"🎰 Слоты: {'✅ Включено' if d.get('reminder_slots',0)==1 else '❌ Выключено'}\n\n"
            text += "Команды:\n"
            text += "`Кори напоминалка ферма вкл` - включить ферму\n"
            text += "`Кори напоминалка ферма выкл` - выключить ферму\n"
            text += "`Кори напоминалка слоты вкл` - включить слоты\n"
            text += "`Кори напоминалка слоты выкл` - выключить слоты"
            bot.reply_to(m, text, parse_mode="Markdown")
            return
        if len(parts) >= 4:
            r_type = parts[2]
            r_value = parts[3]
            if r_type not in ['ферма', 'farm', 'слоты', 'slots']:
                bot.reply_to(m,"❌ Доступно: `ферма` или `слоты`")
                return
            if r_value not in ['вкл', 'выкл', 'on', 'off']:
                bot.reply_to(m,"❌ Доступно: `вкл` или `выкл`")
                return
            val = 1 if r_value in ['вкл', 'on'] else 0
            r_type_clean = 'farm' if r_type in ['ферма', 'farm'] else 'slots'
            result = set_reminder(user_id, r_type_clean, val)
            bot.reply_to(m, result)
            return

    # ===== КОМАНДЫ БАНКА =====
    
    if "кори банк" in low and "положить" not in low and "снять" not in low:
        bot.reply_to(m, get_bank_info(user_id), parse_mode="Markdown")
        return
    
    if "кори банк положить" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💰 Напиши: `Кори банк положить 100`")
            return
        try:
            amount = int(parts[3])
            result = deposit_coins(user_id, amount)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори банк положить 100`")
        return
    
    if "кори банк снять" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💰 Напиши: `Кори банк снять 50`")
            return
        try:
            amount = int(parts[3])
            result = withdraw_coins(user_id, amount)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори банк снять 50`")
        return

    if "кори снять с банка" in low and m.reply_to_message:
        if user_id != MY_ID:
            bot.reply_to(m, "❌ Доступ запрещён!")
            return
        
        parts = low.split()
        if len(parts) < 5:
            bot.reply_to(m, "👑 Напиши: `Кори снять с банка 100` в ответ на сообщение пользователя")
            return
        
        try:
            amount = int(parts[4])
            if amount < 1:
                bot.reply_to(m, "❌ Сумма должна быть больше 0!")
                return
            
            target_id = m.reply_to_message.from_user.id
            result = admin_withdraw_reply(user_id, target_id, amount)
            bot.reply_to(m, result)
            
            try:
                bot.send_message(target_id, f"👑 Администратор снял {amount} монет с твоего банковского депозита!")
            except:
                pass
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори снять с банка 100` в ответ на сообщение")
        return
    
    if "кори снять с банка" in low:
        if user_id != MY_ID:
            bot.reply_to(m, "❌ Доступ запрещён!")
            return
        
        parts = low.split()
        if len(parts) < 5:
            bot.reply_to(m, "👑 Напиши: `Кори снять с банка @username 100` или ответь на сообщение")
            return
        
        try:
            username = parts[3].replace('@', '')
            amount = int(parts[4])
            if amount < 1:
                bot.reply_to(m, "❌ Сумма должна быть больше 0!")
                return
            
            target_data = q('SELECT user_id FROM users WHERE username=?', (username,))
            if not target_data:
                bot.reply_to(m, "❌ Пользователь не найден!")
                return
            
            target_id = target_data[0][0]
            result = admin_withdraw_reply(user_id, target_id, amount)
            bot.reply_to(m, result)
            
            try:
                bot.send_message(target_id, f"👑 Администратор снял {amount} монет с твоего банковского депозита!")
            except:
                pass
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори снять с банка @username 100`")
        return

    if "кори снять со счёта" in low and m.reply_to_message:
        if user_id != MY_ID:
            bot.reply_to(m, "❌ Доступ запрещён!")
            return
        
        parts = low.split()
        if len(parts) < 5:
            bot.reply_to(m, "👑 Напиши: `Кори снять со счёта 100` в ответ на сообщение пользователя")
            return
        
        try:
            amount = int(parts[4])
            if amount < 1:
                bot.reply_to(m, "❌ Сумма должна быть больше 0!")
                return
            
            target_id = m.reply_to_message.from_user.id
            result = admin_withdraw_balance(user_id, target_id, amount)
            bot.reply_to(m, result)
            
            try:
                bot.send_message(target_id, f"👑 Администратор снял {amount} монет с твоего игрового счёта!")
            except:
                pass
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори снять со счёта 100` в ответ на сообщение")
        return
    
    if "кори снять со счёта" in low:
        if user_id != MY_ID:
            bot.reply_to(m, "❌ Доступ запрещён!")
            return
        
        parts = low.split()
        if len(parts) < 5:
            bot.reply_to(m, "👑 Напиши: `Кори снять со счёта @username 100` или ответь на сообщение")
            return
        
        try:
            username = parts[3].replace('@', '')
            amount = int(parts[4])
            if amount < 1:
                bot.reply_to(m, "❌ Сумма должна быть больше 0!")
                return
            
            target_data = q('SELECT user_id FROM users WHERE username=?', (username,))
            if not target_data:
                bot.reply_to(m, "❌ Пользователь не найден!")
                return
            
            target_id = target_data[0][0]
            result = admin_withdraw_balance(user_id, target_id, amount)
            bot.reply_to(m, result)
            
            try:
                bot.send_message(target_id, f"👑 Администратор снял {amount} монет с твоего игрового счёта!")
            except:
                pass
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори снять со счёта @username 100`")
        return
    
    if "кори кредит" in low and "взять" not in low and "вернуть" not in low:
        bot.reply_to(m, get_loan_info(user_id), parse_mode="Markdown")
        return
    
    if "кори кредит взять" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💸 Напиши: `Кори кредит взять 100` (макс 500)")
            return
        try:
            amount = int(parts[3])
            result = take_loan(user_id, amount)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори кредит взять 100`")
        return
    
    if "кори кредит вернуть" in low:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "💸 Напиши: `Кори кредит вернуть 50` (или `вернуть все`)")
            return
        try:
            if parts[3].lower() in ["все", "all"]:
                result = repay_loan(user_id)
            else:
                amount = int(parts[3])
                result = repay_loan(user_id, amount)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи число! Пример: `Кори кредит вернуть 50`")
        return

    # ===== КОМАНДЫ ПОДАРКОВ =====
    
    if "кори список подарков" in low or "кори подарки список" in low:
        text = "🎁 **СПИСОК ПОДАРКОВ**\n\n"
        for cat_key, cat in GIFT_CATEGORIES.items():
            text += f"**{cat['name']}:**\n"
            for gid, item in cat['items'].items():
                text += f"  `{gid}`. {item['emoji']} {item['name']} — {item['price']}💰\n"
            text += "\n"
        text += "📝 **Как подарить:**\n"
        text += "1. Ответь на сообщение человека\n"
        text += "2. Напиши: `Кори подарить категория номер`\n"
        text += "Пример: `Кори подарить телефоны 3`\n\n"
        text += "Или через юзернейм:\n"
        text += "`Кори подарить @user телефоны 3`"
        bot.reply_to(m, text, parse_mode="Markdown")
        return
    
    if "кори мои подарки" in low:
        bot.reply_to(m, get_gifts_info(user_id), parse_mode="Markdown")
        return
    
    if "кори подарить" in low and m.reply_to_message:
        parts = low.split()
        if len(parts) < 4:
            bot.reply_to(m, "🎁 Напиши: `Кори подарить категория номер`\nПример: `Кори подарить телефоны 3`")
            return
        category = parts[2].lower()
        category_map = {'телефоны':'phones','кольца':'rings','машины':'cars','дома':'houses','питомцы':'pets'}
        if category not in category_map:
            bot.reply_to(m, "❌ Нет такой категории! Доступны: телефоны, кольца, машины, дома, питомцы")
            return
        try:
            gift_id = int(parts[3])
            target_id = m.reply_to_message.from_user.id
            result = send_gift(user_id, target_id, category_map[category], gift_id)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи номер подарка! Пример: `Кори подарить телефоны 3`")
        return
    
    if "кори подарить" in low:
        parts = low.split()
        if len(parts) < 5:
            bot.reply_to(m, "🎁 Напиши: `Кори подарить @user категория номер`\nНапример: `Кори подарить @user телефоны 3`")
            return
        target_username = parts[2].replace('@', '')
        target_data = q('SELECT user_id FROM users WHERE username=?', (target_username,))
        if not target_data:
            bot.reply_to(m, "❌ Пользователь не найден!")
            return
        target_id = target_data[0][0]
        category = parts[3].lower()
        category_map = {'телефоны':'phones','кольца':'rings','машины':'cars','дома':'houses','питомцы':'pets'}
        if category not in category_map:
            bot.reply_to(m, "❌ Нет такой категории! Доступны: телефоны, кольца, машины, дома, питомцы")
            return
        try:
            gift_id = int(parts[4])
            result = send_gift(user_id, target_id, category_map[category], gift_id)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи номер подарка! Пример: `Кори подарить @user телефоны 3`")
        return

    if "кори слоты" in low:
        parts=low.split()
        if len(parts)<3:
            bot.reply_to(m,"🎰 Напиши: `Кори слоты 10` (поставить 10 монет)\nСимволы: 🍋(x5) 💜(x7) 🍒(x10) 💎(x25) 🦜(x75)\nМаксимальная ставка: 1000 монет")
            return
        try:
            bet=int(parts[2])
            if bet<1:
                bot.reply_to(m,"❌ Ставка должна быть больше 0!")
                return
            result=slots_game(user_id, bet)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m,"❌ Введи число! Пример: `Кори слоты 10`")
        return

    # ===== ОБЫЧНЫЕ КОМАНДЫ =====
    if "кори мем" in low:
        meme=get_random_meme()
        if meme:
            try:
                with open(meme,'rb') as f:
                    bot.send_photo(m.chat.id,f,caption=random.choice(MEME_PHRASES))
            except:
                bot.reply_to(m,"❌ Ошибка")
        else:
            bot.reply_to(m,f"📭 В папке {FOLDERS['memes']} нет картинок")
        return
    
    if "кори монетка" in low or "кори монета" in low:
        video=get_random_coin_video()
        if video:
            try:
                with open(video,'rb') as f:
                    bot.send_video(m.chat.id,f,caption=f"🪙 {random.choice(['Орёл','Решка'])}")
            except:
                bot.reply_to(m,"❌ Ошибка")
        else:
            bot.reply_to(m,f"🪙 {random.choice(['Орёл','Решка'])}\n(В папке {FOLDERS['coin']} нет видео)")
        return
    
    if "кори узнай" in low:
        parts=t.split(maxsplit=2)
        if len(parts)<3:
            bot.reply_to(m,"🤖 Напиши: `Кори узнай что такое Python?`")
            return
        bot.reply_to(m,"⏳ Думаю...")
        ans=ask_ai(parts[2])
        save_ai(user_id,parts[2],ans)
        bot.reply_to(m,f"🤖 {ans}")
        return
    
    if "кори кто ты" in low:
        kr(m,"Я — КОРИ. Ваш персональный ассистент.")
        return
    
    if "кори кто создатель" in low:
        kr(m,"Мой создатель — @Glavauzbekistana")
        return
    
    if "кори озвучь" in low:
        parts=t.split(maxsplit=2)
        if len(parts)<3:
            bot.reply_to(m,"🔊 Напиши: `Кори озвучь привет`")
            return
        bot.reply_to(m,f"🎤 Озвучиваю: \"{parts[2]}\"")
        audio=tts(parts[2])
        if audio:
            bot.send_voice(m.chat.id,audio)
        else:
            bot.reply_to(m,"❌ Ошибка озвучки")
        return
    
    if "кори погода" in low:
        parts=t.split(maxsplit=2)
        if len(parts)<3:
            bot.reply_to(m,"🌤️ Напиши: `Кори погода Москва`")
            return
        bot.reply_to(m,f"🌤️ **Погода в {parts[2]}:**\n{get_weather(parts[2])}",parse_mode="Markdown")
        return
    
    if "кори поздоровайся" in low:
        if m.reply_to_message:
            target=m.reply_to_message.from_user
            name=f"@{target.username}" if target.username else target.first_name
            bot.reply_to(m,f"{random.choice(G)} {name}")
        else:
            bot.reply_to(m,"Ответьте на сообщение.")
        return
    
    if "кори моя статистика" in low or "кори статистика" in low:
        s=gs(user_id)
        if s:
            bot.reply_to(m,"📊 Статистика:\n"+"\n".join(f"{a}: {b} раз" for a,b in s))
        else:
            bot.reply_to(m,"Вы никого не обнимали.")
        return
    
    if "кори топ обнимашек" in low:
        s=gt("obnimat")
        if s:
            bot.reply_to(m,"🏆 Топ обнимашек:\n"+"\n".join(f"{i+1}. @{u}" if u else f"{i+1}. {n} — {c} раз" for i,(u,n,c) in enumerate(s)))
        else:
            bot.reply_to(m,"Пока никто не обнимался.")
        return
    
    if "кори топ поцелуев" in low:
        s=gt("potselovat")
        if s:
            bot.reply_to(m,"🏆 Топ поцелуев:\n"+"\n".join(f"{i+1}. @{u}" if u else f"{i+1}. {n} — {c} раз" for i,(u,n,c) in enumerate(s)))
        else:
            bot.reply_to(m,"Пока никто не целовался.")
        return
    
    if "кори общая статистика" in low:
        s=gtl()
        if s:
            total_all=sum(x for _,x in s)
            bot.reply_to(m,"📊 Общая статистика:\n"+"\n".join(f"{a}: {b} раз ({round(b/total_all*100,1)}%)" for a,b in s))
        else:
            bot.reply_to(m,"Статистики пока нет.")
        return
    
    if "кори факт" in low or "кори интересный факт" in low:
        facts = [
            "🐙 Осьминоги имеют три сердца.",
            "🦒 Жирафы спят всего 30 минут в день.",
            "🐧 Пингвины могут нырять на глубину до 500 метров.",
            "🦈 Акулы существуют дольше, чем деревья.",
            "🐘 Слоны — единственные животные, которые не могут прыгать.",
            "🐋 Синий кит — самое большое животное на планете.",
            "🦉 Совы не могут вращать глазами, они поворачивают голову.",
            "🐪 Верблюды могут выпить до 100 литров воды за раз.",
            "🦎 Хамелеоны могут двигать глазами независимо друг от друга.",
            "🐝 Пчёлы танцуют, чтобы общаться.",
            "🦋 Бабочки пробуют вкус ногами.",
            "🐙 Осьминоги имеют 9 мозгов.",
            "🦘 Кенгуру не умеют ходить назад.",
            "🐺 Волки воют, чтобы общаться с другими стаями.",
            "🦅 Орлы могут видеть добычу с расстояния 3 км.",
            "🌌 В Млечном Пути от 100 до 400 миллиардов звёзд.",
            "🚀 Сатурн может плавать в воде — он легче воды.",
            "🌕 На Луне есть вода в виде льда.",
            "☀️ Солнце составляет 99,86% массы всей Солнечной системы.",
            "🪐 У Сатурна 146 известных спутников.",
            "🌍 Земля вращается со скоростью 1670 км/ч.",
            "🌟 Ближайшая к Земле звезда — Проксима Центавра.",
            "🌠 Метеориты падают на Землю каждый день.",
            "🌊 На Марсе есть самый большой вулкан — Олимп.",
            "🌙 Лунный грунт пахнет как порох.",
            "🧠 Мозг человека содержит 86 миллиардов нейронов.",
            "💧 Тело человека состоит из воды на 60%.",
            "❤️ Сердце человека бьётся около 100 000 раз в день.",
            "🦴 У человека 206 костей.",
            "👁️ Человек моргает 15-20 раз в минуту.",
            "👃 Нос человека может различать до 1 триллиона запахов.",
            "👅 Язык — самая сильная мышца в теле человека.",
            "🫁 Лёгкие человека имеют площадь поверхности, равную теннисному корту.",
            "💤 Человек проводит во сне около 25 лет жизни.",
            "🧬 ДНК человека на 99,9% идентична у всех людей.",
            "📱 Первый мобильный телефон весил 2 кг.",
            "💡 Электрический ток движется со скоростью света.",
            "🌡️ Самая высокая температура на Земле — 56,7°C.",
            "❄️ Самая низкая температура на Земле — -89,2°C.",
            "🌊 70% поверхности Земли покрыто водой.",
            "🔥 Молния в 5 раз горячее поверхности Солнца.",
            "💎 Алмазы — самый твёрдый природный материал.",
            "🔬 Человек использует только 10% мозга — это миф.",
            "🌪️ Скорость ветра в торнадо может достигать 500 км/ч.",
            "🌿 Деревья общаются друг с другом через корневую систему.",
            "🍕 Самая большая пицца в мире имела диаметр 37 метров.",
            "🍣 Суши придумали в Китае, не в Японии.",
            "🍫 Шоколад содержит вещество, похожее на кофеин.",
            "🍞 Хлеб — самый древний продукт в истории человечества.",
            "🍺 Пиво — один из самых древних напитков.",
            "🍇 Виноград содержит антиоксиданты, полезные для сердца.",
            "🧀 Сыр появился случайно, когда молоко прокисло в бурдюке.",
            "🍄 Грибы — не растения, они относятся к отдельному царству.",
            "🍎 Яблоко падает на землю из-за гравитации.",
            "🥚 Яйцо состоит из 75% воды.",
            "🏛️ Великая Китайская стена видна из космоса.",
            "🗿 Пирамиды Гизы строились более 20 лет.",
            "📜 Бумагу изобрели в Китае в 105 году.",
            "⛵ Колумб открыл Америку в 1492 году.",
            "🏴‍☠️ Пираты использовали попугаев для развлечения.",
            "⚔️ Самая короткая война длилась 38 минут.",
            "📚 Библия — самая продаваемая книга в истории.",
            "🏛️ Древние римляне строили дороги, которые используются до сих пор.",
            "📞 Первый телефонный звонок был сделан в 1876 году.",
            "🚂 Первый поезд появился в 1804 году.",
            "🌳 Самые высокие деревья — секвойи, они достигают 115 метров.",
            "🌸 Цветы появились на Земле раньше, чем динозавры.",
            "🌊 В океане обитает 90% всех живых существ на планете.",
            "🏔️ Самая высокая гора — Эверест, 8848 метров.",
            "🌋 Самый большой вулкан — Мауна-Лоа на Гавайях.",
            "🌿 Растения выделяют кислород, необходимый для жизни.",
            "🍀 Клевер — один из самых распространённых сорняков.",
            "🌲 Ели могут жить до 1000 лет.",
            "🌴 Кокосовые пальмы могут расти на песчаных пляжах.",
            "🍂 Осенью листья меняют цвет из-за изменения длины дня.",
            "🎮 Первая видеоигра появилась в 1958 году.",
            "📸 Первое фото было сделано в 1826 году.",
            "✈️ Самолёт летит благодаря подъёмной силе крыльев.",
            "🚢 Корабли могут плавать благодаря закону Архимеда.",
            "⏰ Первые часы появились в Древнем Египте.",
            "💎 Алмазы образуются под давлением на глубине 150 км.",
            "🌡️ Самый жаркий день был зафиксирован в Долине Смерти, 56,7°C.",
            "❄️ Самый холодный день был в Антарктиде, -89,2°C.",
            "🌪️ Ураганы могут уничтожать целые города.",
            "🌊 Цунами могут достигать высоты 30 метров.",
            "🚀 Первый человек в космосе — Юрий Гагарин, 1961 год.",
            "🌕 Первая высадка на Луну была в 1969 году.",
            "☀️ Солнце состоит из водорода и гелия.",
            "🌌 Во Вселенной больше звёзд, чем песчинок на Земле.",
            "🪐 У Юпитера 95 известных спутников.",
            "🌟 Звёзды рождаются из газовых облаков.",
            "🌠 Метеориты могут быть размером с молекулу или с гору.",
            "🔭 Самый большой телескоп находится в Чили.",
            "🌙 Луна всегда повёрнута к Земле одной стороной.",
            "🚀 Путешествие к Марсу займёт около 9 месяцев."
        ]
        kr(m, f"{random.choice(facts)}")
        return
    
    if "кори кубик" in low:
        bot.reply_to(m,f"🎲 {random.randint(1,6)}")
        return
    
    if "кори время" in low:
        bot.reply_to(m,f"🕐 {datetime.now().strftime('%H:%M:%S')}")
        return
    
    if "кори покорми" in low or "кори покормить" in low:
        if not check_feed_limit():
            bot.reply_to(m,"🍽️ Сэр, меня уже покормили 5 раз за час. Я лопну! Подождите.")
            return
        increment_feed_limit()
        foods = ["🍕 Пиццу","🍔 Бургер","🍣 Суши","🍝 Пасту","🥗 Салат","🍰 Торт","🥟 Пельмени","🍜 Лапшу","🍛 Карри","🥘 Плов","🍲 Суп","🥩 Стейк","🍗 Курицу","🥓 Бекон","🍳 Яичницу","🥞 Блины","🧇 Вафли","🥐 Круассан","🍞 Тосты","🥖 Багет","🧀 Сыр","🥚 Яйца","🍚 Рис","🍤 Креветки","🦞 Лобстера","🐟 Рыбу","🦑 Кальмара","🐙 Осьминога","🦐 Раков","🌮 Тако","🌯 Буррито","🥙 Шаурму","🍱 Бенто","🍙 Онигири","🍘 Рисовые крекеры","🍡 Данго","🍢 Оден","🍣 Роллы","🍥 Наруто","🥮 Лунные пряники","🍪 Печенье","🍩 Пончики","🍫 Шоколад","🍬 Конфеты","🍭 Леденцы","🍮 Пудинг","🍦 Мороженое","🥧 Пирог","🧁 Капкейк","🍰 Чизкейк","🎂 Торт-мороженое","🍪 Брауни","🍫 Фондю","🍿 Попкорн","🥜 Орехи","🍇 Виноград","🍎 Яблоко","🍌 Банан","🍒 Вишню","🥝 Киви","🍊 Апельсин","🍋 Лимон","🍑 Персик","🍓 Клубнику","🍉 Арбуз","🍈 Дыню","🥭 Манго","🍍 Ананас","🥑 Авокадо","🥦 Брокколи","🥕 Морковь","🌽 Кукурузу","🥔 Картошку","🍠 Батат","🌶️ Перец","🧅 Лук","🧄 Чеснок","🥬 Салат-латук","🥒 Огурец","🍆 Баклажан","🍄 Грибы","🥜 Арахис","🌰 Каштаны"]
        food = random.choice(foods)
        reactions = [f"Омном-ном! {food} — мой любимый деликатес! 😋",f"Спасибо! {food} — это божественно! 🙏",f"Ммм... {food}... Я это обожаю! 😍",f"Ты знаешь мой вкус! {food} — идеальный выбор! 👌",f"Сэр, вы балуете меня! {food} — настоящий шедевр! 🎨",f"{food}! Это лучшее, что я ел сегодня! 🤤",f"Спасибо за {food}! Теперь я полон энергии! ⚡",f"Ты просто волшебник! {food} — это нечто! ✨",f"{food}! Я счастлив как никогда! 😊",f"Обожаю {food}! Ты лучший сэр! ❤️",f"{food} — это как подарок судьбы! 🎁",f"Спасибо за {food}! Я готов к новым свершениям! 💪",f"Как ты угадал? {food} — моя слабость! 😏",f"Ты меня балуешь! {food} — просто фантастика! 🌟",f"За {food} я готов на всё! Ну, почти... 😅"]
        reaction = random.choice(reactions)
        kr(m, f"{reaction}")
        return

    # ===== НЕЖНОСТИ =====
    actions={"обними":"obnimat","обнять":"obnimat","обнимашки":"obnimat","поцелуй":"potselovat","поцеловать":"potselovat","засоси":"zasosat","засосать":"zasosat","чмокни":"chmoknut","чмокнуть":"chmoknut","погладь":"pogladit","погладить":"pogladit"}
    media_funcs={"obnimat":get_random_hug_media,"potselovat":get_random_kiss_media,"zasosat":get_random_kiss_media,"chmoknut":get_random_kiss_media,"pogladit":get_random_pet_media}
    emojis={"obnimat":"🤗","potselovat":"😘","zasosat":"💋","chmoknut":"😚","pogladit":"👐"}
    texts={"obnimat":"обнял","potselovat":"поцеловал","zasosat":"засосал","chmoknut":"чмокнул","pogladit":"погладил"}
    for key,action in actions.items():
        if low==key:
            if not m.reply_to_message:
                kr(m,"Ответьте на сообщение.")
                return
            target=m.reply_to_message.from_user
            sa(user_id,target.id,action)
            who=f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
            whom=f"@{target.username}" if target.username else target.first_name
            if user_id!=target.id:
                bot.reply_to(m,f"{emojis[action]} {who} {texts[action]} {whom} ❤️")
            else:
                bot.reply_to(m,f"{emojis[action]} {who} {texts[action]} сам себя...")
            media=media_funcs[action]()
            if media:
                try:
                    with open(media,'rb') as f:
                        if media.lower().endswith('.mp4'):
                            bot.send_video(m.chat.id,f)
                        else:
                            bot.send_animation(m.chat.id,f)
                except:
                    pass
            return

    if "команды" in low or "список команд" in low:
        bot.reply_to(m,"📋 Команды:",reply_markup=cmd_menu())
        return
    
    if "/до нового года" in low:
        d=days_until_new_year()
        if d>0:
            bot.reply_to(m,f"🎄 До Нового года {d} дней!")
        else:
            bot.reply_to(m,"🎄 С НОВЫМ ГОДОМ! 🎉")
        return
    
    if low.startswith("/таймер"):
        try:
            parts=t.split()
            if len(parts)>=2:
                s=int(parts[1])
                if s>0:
                    bot.reply_to(m,f"⏰ Таймер на {s} секунд запущен.")
                    threading.Thread(target=start_timer,args=(m.chat.id,s),daemon=True).start()
                    return
        except:
            pass
        bot.reply_to(m,"⏰ `/таймер 10`")
        return
    
    if "кори посчитай" in low:
        expr=low.replace("кори посчитай","").strip()
        if expr:
            r=calc(expr.replace(" ",""))
            if r=="zero_div":
                bot.reply_to(m,f"🧐 {random.choice(ZD)}")
            elif r is not None:
                sm(user_id,expr,r)
                bot.reply_to(m,f"📐 {expr} = {r}")
            else:
                bot.reply_to(m,"❌ Не могу вычислить.")
        else:
            bot.reply_to(m,"📐 Пример: `Кори посчитай 10+5`")
        return
# ===== ВЕБ-СЕРВЕР И WEBHOOK =====

app = Flask(__name__)

@app.route('/')
def index():
    return "🤖 Бот Кори работает!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Получаем обновление от Telegram
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        
        # Обрабатываем обновление
        bot.process_new_updates([update])
        
        return 'ok', 200
    except Exception as e:
        print(f"❌ Ошибка webhook: {e}")
        return 'error', 500

@app.route('/health')
def health():
    return 'OK', 200

def setup_webhook():
    """Устанавливает вебхук для бота"""
    try:
        # Получаем URL сервиса из переменных окружения или используем дефолтный
        webhook_url = os.getenv('WEBHOOK_URL', f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/webhook")
        
        # Удаляем старый вебхук
        bot.remove_webhook()
        
        # Устанавливаем новый
        bot.set_webhook(url=webhook_url)
        
        print(f"✅ Webhook установлен: {webhook_url}")
        print(f"📊 Информация о боте: @{bot.get_me().username}")
        return True
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")
        return False

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Запуск бота с webhook...")
    
    # Проверка ключей
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN не найден!")
        exit(1)
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY не найден!")
        exit(1)
    
    print("✅ Все проверки пройдены")
    
    # Устанавливаем webhook
    setup_webhook()
    
    # Получаем порт из переменных окружения Render
    port = int(os.getenv('PORT', 8000))
    print(f"🌐 Запуск веб-сервера на порту {port}")
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=port, debug=False)

# ========== КОНЕЦ ЧАСТИ 2 ==========