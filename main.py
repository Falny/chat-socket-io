import socketio  
from aiohttp import web
import secrets
from datetime import datetime
import sqlite3
import atexit
import json
import secrets
import bcrypt
import os

db = sqlite3.connect('db.db')
cursor = db.cursor()

PORT = int(os.environ.get("PORT", 5000))
HOST = '0.0.0.0'

#таблица пользователей

cursor.execute("""CREATE TABLE IF NOT EXISTS user_token (
                token TEXT PRIMARY KEY,
               user TEXT UNIQUE NOT NULL 
               )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS messages (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               room TEXT ,
               login TEXT NOT NULL, 
               message TEXT NOT NULL,
               time TEXT NOT NULL,
               isRead BOOLEAN
               )""")


# оежит комната:токен комнаты
cursor.execute("""CREATE TABLE IF NOT EXISTS rooms (
                id TEXT,
                room TEXT UNIQUE NOT NULL
                )""")

# лежит логин пользователя: {логин другана: комната(обычная, не токен)}
cursor.execute("""CREATE TABLE IF NOT EXISTS user_room (
            id TEXT KEY PRYMARY,
            rooms JSON
               )""")

db.commit()


now = datetime.now()

sid_to_login = {} # поиск логика по сиду
login_to_sid = {} # поиск сида по логину

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, 'front')

sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

@sio.event
async def connect(sid, environ, auth):

    if not auth:
        return False
    
    if 'login' not in auth or 'token' not in auth:
        return False
    
    cursor.execute("SELECT * FROM user_token WHERE token = ?", (auth['token'],))
    user_token = cursor.fetchone()

    if not user_token:
        return False
        
    token_table, login_table = user_token[0], user_token[1]

    if login_table != auth['login']:
        return False
    

    login_user = auth['login'] # вытаскиваю токен
    sid_to_login[sid] = login_user # добавляю в словарь логин по сиду
    login_to_sid[login_user] = sid

    await sio.emit('get_name', login_user)

@sio.event
async def disconnect(sid):
    await sio.leave_room(sid, 'ico-room')


def key_created(login1, login2):
    log, logFriend = int(login1), int(login2)
    room = sorted([log, logFriend]) #id room
    return f"chat_{room[0]}_{room[1]}"

@sio.event
async def join_room(sid, data):

    login = data['login']
    loginFriend = data['loginFriend']

    # создаю приватную комнату для личного диалога
    tokenRoom = secrets.token_hex(16)
    room = key_created(login, loginFriend) #id room

    # проверяю есть ли уже такая комната, если нет, то создаю
    try: 
        cursor.execute("SELECT * FROM rooms WHERE id = ?", (room,))
        fieldRoom = cursor.fetchone()
        if fieldRoom:
            room, tokenRoom = fieldRoom
        else:
            cursor.execute("INSERT INTO rooms VALUES (?, ?)", (room, tokenRoom))
            room, tokenRoom = room, tokenRoom
            db.commit()
        
    except Exception as e:
        print('ошибка комнаты', e)

    try:
        cursor.execute("SELECT * FROM user_room WHERE id = ?", (login,))
        userRoom = cursor.fetchone()
        if userRoom:
            roomJSON = json.loads(userRoom[1])
            if room not in roomJSON.values():
                roomJSON[loginFriend] = room
                cursor.execute("UPDATE user_room SET rooms = ? WHERE id = ?", (json.dumps(roomJSON), login))
                db.commit()
                cursor.execute("SELECT * FROM user_room")
        else:
            userRoom = {
                    f"{loginFriend}": f"{room}"
                }
            userRoom = json.dumps(userRoom)
            cursor.execute("INSERT INTO user_room VALUES (?, ?)", (login, userRoom))
            db.commit()
    except Exception as e:
        print('ошибка добавления комнаты')


    # преобразованный токен выбранного пользователя, нахожу его сид
    sidFriend = login_to_sid[loginFriend]

    if sidFriend:
            await sio.enter_room(sidFriend, room=room)
            await sio.emit('join_room', {'login': login, 'room': room}, room=room)

    await sio.enter_room(sid, room=room)
    await sio.emit('get_room', {'room': room}, to=sid)


@sio.event
async def message(sid, data):
    loginFriend = data['logFriend']
    login = data['login']

    room = key_created(login, loginFriend) 

    try:
    # нахожу токен комнаты
        cursor.execute("SELECT * FROM rooms WHERE id = ?", (room,))
        fieldRoom = cursor.fetchone()
        
        if fieldRoom:
            room, tokenRoom = fieldRoom
            cursor.execute("INSERT INTO messages (room, login, message, time, isRead) VALUES (?, ?, ?, ?, ?)", (tokenRoom, login, data['message'], now.isoformat(), False))
            db.commit()

    except Exception as e:
        print('ошибка сообщения', e)
    except KeyError as e:
        print('ошибка ключа', e)
    except sqlite3.Error as e:
        print('ошибка бд', e)

    # cursor.execute("DROP TABLE messages")
    # db.commit()


    await sio.emit('message', {'message': data['message'], 'room': room}, room=room, skip_sid=sid)

@sio.event
async def have_room(sid, data):
    messages = []
    room = ''
    tokenRoom = ''

    try:
        cursor.execute("SELECT * FROM rooms WHERE id = ?", (data,))
        fieldRoom = cursor.fetchone()
        if fieldRoom:
            room, tokenRoom = fieldRoom #нахожу токен комнаты
            cursor.execute("SELECT * FROM messages WHERE room = ? ORDER BY time ASC LIMIT 40", (tokenRoom,))
            messagesField = cursor.fetchall()
            if messagesField:
                for i in messagesField:
                    dictMes = {}
                    dictMes['login'] = i[2]
                    dictMes['message'] = i[3]
                    messages.append(dictMes)

            else:
                messages = False # возвращаю пустое сообщение
    except Exception as e:
        print('ошибка переключения комнаты: ', e)


    await sio.enter_room(sid, room=room)
    await sio.emit('get_chat_messages', {'room': room, 'message': messages}, to=sid)



async def get_all_user(request):

    try: 
        data = await request.json()

        cursor.execute("SELECT login FROM users WHERE login != ?", (data['login'],))
        users = cursor.fetchall()

        if not users: 
            response = web.json_response({}, status = 500)
            response.headers['Access-Control-Allow-Origin'] = "*"
            response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
            response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
            return response

        response = web.json_response(users, status = 200)
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
        response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
        return response

    except Exception as e:
        print('error users', e)


async def get_all_chats(request):
    data = await request.json()

    cursor.execute("SELECT rooms FROM user_room WHERE id = ?", (data,))
    chats = cursor.fetchone()
    if chats:
        chats = json.loads(chats[0]) 
        response = web.json_response({'success' : True, 'chats': chats})
    else:
        response = web.json_response({'success': False})

    
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
    response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
    return response

#добавление пользователя
async def registr(request):

    # cursor.execute("DROP TABLE users")
    # cursor.execute("DROP TABLE user_token")
    # db.commit()

    try:
        data = await request.json()

        token = secrets.token_hex(16)

        salt = bcrypt.gensalt()
        hash = bcrypt.hashpw(data['password'].encode('utf-8'), salt)


        cursor.execute("INSERT INTO users (login, password) VALUES (?, ?)", (data['login'], hash))
        db.commit()

        #токен и логин добавляю в таблицу
        cursor.execute("INSERT INTO user_token VALUES (?, ?)", (token, data['login']))
        db.commit()

        response = web.json_response({"message" : 'успешная регистрация'}, status = 200)


    except Exception as e:
        print(f'Exeption: {e}')
        response = web.json_response({"message" : 'ошибка регистрации'}, status = 500)


    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
    response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
    return response


# инициализация и аутентификация 
async def login(request):

    try:        
        data = await request.json()

        login = data['login']
        password = data['password']

        # token = secrets.token_hex(16)
        cursor.execute("SELECT * FROM users WHERE login = ?", (login,))

        user = cursor.fetchone()

        #вытаскиваю токен и логин пользователя из user_token
        cursor.execute("SELECT * FROM user_token WHERE user = ?", (login,))
        token_user = cursor.fetchone()

        if not user:
            response = web.json_response({"message": "ошибка логина или пароля"}, status = 500)
            response.headers['Access-Control-Allow-Origin'] = "*"
            response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
            response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
            return response

        id, log, passwordHash = user

        if token_user:
            token_from_table, login_from_table = token_user[0], token_user[1]

            if login == login_from_table:
                if bcrypt.checkpw(password.encode('utf-8'), passwordHash):
                    response = web.json_response({"token": token_from_table}, status = 200)
                    response.headers['Access-Control-Allow-Origin'] = "*"
                    response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
                    response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"

                    return response
                
        else:
            return web.json_response({"message": "ошибка входа"}, status = 500)

    except Exception as e:
        print('ошибка сервера', e)
        response = web.json_response({"message": "ошибка логина или пароля"}, status = 500)
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
        response.headers['Access-Control-Allow-Headers'] = "Origin, X-Requested-With, Content-Type, Accept"
        return response
    



async def handle_index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, 'index.html'))


async def handle_all_gets(request):
    # Получаем путь из URL
    path = request.match_info.get('path', '')

    file_main = os.path.join(STATIC_DIR, path)

    if os.path.exists(file_main):
        return web.FileResponse(file_main)

    return web.Response(text='File not found', status = 404)


def goodbye():
    db.close()

atexit.register(goodbye)

# api
app.router.add_post('/get-all-users', get_all_user)
app.router.add_post('/get-all-chats', get_all_chats)
app.router.add_post('/registr', registr)
app.router.add_post('/login', login)

# frontend
app.router.add_get('/', handle_index)
app.router.add_get('/{path:.*}', handle_all_gets)


if __name__ == '__main__':
    web.run_app(app, host=HOST, port=PORT)