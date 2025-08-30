import socketio  
import random
from aiohttp import web
import secrets
from datetime import datetime

now = datetime.now()

user_dict = {}
sid_to_token = {}
token_to_sid = {}
token_user = ''

room_private = {}
user_room = {}

userRoomMessage = {} # хрнаилище сообщений

sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

@sio.event
async def connect(sid, environ, auth):
    global token_user

    if auth and 'token' in auth:
        token_user = auth['token'] # вытаскиваю токен
        sid_to_token[sid] = token_user # добавляю в словарь
        token_to_sid[token_user] = sid

    if token_user in user_dict:
        await sio.emit('get_name', user_dict[token_user])

@sio.event
async def disconnect(sid):
    await sio.leave_room(sid, 'ico-room')

@sio.event
async def join_room(sid, data):
    global room_private

    print(data, 'JOIN ROOM')

    token = list(data['token'])
    tokenFriend = list(data['tokenFriend'])

    # создаю приватную комнату для личного диалога
    room = token + tokenFriend
    random.shuffle(room)
    room = ''.join(room)

    #преобразовать токены обратно в строку
    tokenFriend = ''.join(tokenFriend)
    token = ''.join(token)

    if (token, tokenFriend) in room_private:
        return 

    #личные комнаты
    room_private[token, tokenFriend] = room

    user_room.setdefault(token, [])
    user_room.setdefault(tokenFriend, [])

    user_room[token].append(room)
    user_room[tokenFriend].append(room)

    # преобразованный токен выбранного пользователя, нахожу его сид
    sidFriend = token_to_sid[tokenFriend]

    # иницилизация хранилища сообщений
    if room not in userRoomMessage:
        userRoomMessage[room] = []


    if sidFriend:
            await sio.enter_room(sidFriend, room=room)
            print(room, 'join room')
            await sio.emit('join_room', {'token': token, 'name': user_dict[token], 'room': room}, room=room)

    await sio.enter_room(sid, room=room)
    await sio.emit('get_room', room, to=sid)


@sio.event
async def message(sid, data):
    global room_private
    tokenFriend = data['toggleFriend']
    token = data['token']

    print(token, tokenFriend, 'token tokenFriend')


    if (token, tokenFriend) in room_private:
        room = room_private[(token, tokenFriend)]
    else: 
        room = room_private[(tokenFriend, token)]
    print(room, 'room in messages')
    #хранилище сообщений
    userRoomMessage[room].append({'token': sid_to_token[sid], 'message': data['message'], 'time': now.time().isoformat(), 'room':room})
    print(userRoomMessage)
    await sio.emit('message', {'message': data['message'], 'room': room}, room=room, skip_sid=sid)

@sio.event
async def name(sid, data):
    # создаю токен
    token = secrets.token_hex(16)
    user_dict[token] = data
    # отправляю обратно на страницу с именем
    await sio.emit('return_token', token)


@sio.event
async def have_room(sid, data):
    print(data, 'DATA')
    token = sid_to_token.get(sid)
    lastRoom = user_room.get(token)
    messages = userRoomMessage[data]

    for i in lastRoom:
        await sio.leave_room(sid, room=i)


    await sio.enter_room(sid, room=data)
    print(sio.rooms(sid), 'connect roooms')
    await sio.emit('get_chat_messages', {'room': data, 'message': messages})



async def get_all_user(request):
    user_dict_copy = dict(user_dict)
    if token_user in user_dict_copy:
        del user_dict_copy[token_user]
    response = web.json_response(user_dict_copy)
    response.headers['Access-Control-Allow-Origin'] = "*"
    return response




app.router.add_get('/get-all-users', get_all_user)


if __name__ == '__main__':
    web.run_app(app, port=5000)