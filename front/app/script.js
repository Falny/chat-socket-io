let listMessage = document.querySelector(".list-message");
let sendBtn = document.querySelector(".send-btn");
let text = document.querySelector(".input-text");
let chatDiv = document.querySelector(".chat");
let users = document.querySelector(".users");
let dropMenu = document.querySelector(".drop-menu");
let profileName = document.querySelector(".profile-name");
let stateOnline = document.querySelector(".state-online");
let groupChats = document.querySelector(".group-chats");
let blockMessage = document.querySelector(".message");

// достаю токен из url
const paramsString = window.location.search;
const searchParams = new URLSearchParams(paramsString);
const login = searchParams.get("login");
const tokenLocalStorage = window.localStorage.getItem("token");

if (!tokenLocalStorage) {
  window.location.href = "/";
}
console.log("2222");
let socket = io(`${window.location.origin}`, {
  auth: {
    login: login,
    token: tokenLocalStorage,
  },
});

let toggle = false; // состояние меню
let toggleChoiceUser = false; // состояние выбора человека
let logFriend = ""; // token другана
let myName = login;
let checkRoom = ""; // проверка комнаты при переключении диалогов

initLoad();
emptyChat();
funcToggle();
getChat();

socket.on("join_room", joinRoom); // получение токена и имени друга для комнаты
socket.on("get_room", getRoom); // получение комнаты
socket.on("message", getMessage);
socket.on("connect", async () => {
  await addUserInMenu();
}); // вызов выпадающего меню

socket.on("get_name", (data) => {
  console.log(data);
  myName = data;
});

// очищаю и добавляю прошлые сообщения при переходе между чатами
socket.on("get_chat_messages", (data) => getChatMessages(data));

text.addEventListener("keypress", sendMessageKey);
sendBtn.addEventListener("click", sendMessage);
users.addEventListener("click", funcToggle);
// выпадающее меню
dropMenu.addEventListener("click", (event) => toggleMenu(event));
// клик по чатам и подгрузка сообщений
groupChats.addEventListener("click", (event) => clickOnChat(event));

async function getChat() {
  try {
    let response = await fetch("http://localhost:5000/get-all-chats", {
      method: "POST",
      body: JSON.stringify(myName),
    });
    let data = await response.json();
    if (data["success"]) {
      Object.entries(data["chats"]).map((el) => addGroupChat(el[0], el[1])); // показываю существующие чаты
    }

    return data;
  } catch (error) {
    console.log("ошибка получения чатов");
  }
}

// получение людей и добавление в выпадающее меню
const getUsers = async () => {
  try {
    let response = await fetch("http://localhost:5000/get-all-users", {
      method: "POST",
      body: JSON.stringify({ login: login }),
    });
    let data = await response.json();
    return data;
  } catch (err) {
    console.log(err);
  }
};

function clickOnChat(event) {
  const room = event.target.dataset.tokenRoom;
  checkRoom = room;
  socket.emit("have_room", room);
  profileName.textContent = event.target.textContent;
  let findTagP = event.target.querySelector(".list-chat_name");
  logFriend = findTagP.dataset.loginFriend;

  setTimeout(() => {
    blockMessage.scrollTo({
      top: blockMessage.scrollHeight,
      left: 0,
      behavior: "smooth",
    });
  }, 100);
}

function toggleMenu(event) {
  if (event.target.tagName === "LI") {
    const loginFriend = event.target.dataset.login;
    const nameElement = event.target.textContent;

    let checkChat = funcCheckChat(nameElement);
    // проверка имени чтобы чаты не повторялись
    if (!checkChat) {
      socket.emit("join_room", { login, loginFriend });
      logFriend = loginFriend; // токен другана
      profileName.textContent = event.target.textContent; //имя другана
      listMessage.innerHTML = "";
      dropMenu.style.opacity = "0"; // скрываю выпадающую меню с именами
      toggleChoiceUser = true; // состояние скрывающейся менюшки
      initLoad(); // начальный экран
      addGroupChat(event.target.textContent, login + loginFriend); // добавление чатов
    }
  }
}

function getChatMessages(data) {
  if (!data["message"]) {
    listMessage.innerHTML = "";
    toggleChoiceUser = true; // я давно сделала эту тему и переделывать не буду, в общем это состояние на открытие еогла с выбором пользователей, без него функция ниже не робит
    initLoad();
    return;
  }

  if (checkRoom === data["room"]) {
    listMessage.innerHTML = "";
    toggleChoiceUser = true; // я давно сделала эту тему и переделывать не буду, в общем это состояние на открытие еогла с выбором пользователей, без него функция ниже не робит
    initLoad();
    // добавляю в чат сообщения в зависимости от отправителя
    data["message"].map((el) => {
      let elToken = el["login"];
      let mes = el["message"];
      if (elToken === login) {
        addClassToSendMessage(mes);
      } else {
        getMessage({ room: data["room"], message: mes });
      }
    });
  }
}

// проверка имени чтобы чаты не повторялись
function funcCheckChat(name) {
  let allChatsName = document.querySelectorAll(".list-chat_name");
  return Array.from(allChatsName).some(
    (el) => el.textContent.toLowerCase() === name.toLowerCase()
  );
}

// создание чата в панели
function addGroupChat(friendName, room) {
  let li = document.createElement("li");
  li.classList.add("list-chats_item");
  li.dataset.tokenRoom = room;

  let img = document.createElement("div");
  img.classList.add("list-chat_img");

  let block = document.createElement("div");
  img.classList.add("list-chat_block");

  let p = document.createElement("p");
  p.classList.add("list-chat_name");
  p.textContent = friendName;
  p.dataset.loginFriend = friendName;

  block.append(p);
  li.append(img);
  li.append(block);

  groupChats.append(li);
}

function getRoom(data) {
  checkRoom = data["room"];
}

// присоединение к комнате
function joinRoom(data) {
  listMessage.innerHTML = ""; // при клике на новый чат убираю лишние сообщения
  profileName.textContent = data["login"];
  logFriend = data["login"];
  checkRoom = data["room"];

  addGroupChat(logFriend, data["room"]);

  toggleChoiceUser = true;
  initLoad();
}

// начальная закгрузка экрана
function initLoad() {
  if (!toggleChoiceUser) {
    chatDiv.style.backgroundColor = "#1e1e1e";
    chatDiv.style.display = "none";
  } else {
    chatDiv.style.display = "flex";
  }
}

// добавление людей в меню
async function addUserInMenu() {
  let userDict = await getUsers();
  userDict.map((el) => {
    let li = document.createElement("li");
    li.textContent = el;
    li.classList.add("menu-item");
    li.dataset.login = el;
    dropMenu.appendChild(li);
  });
}

// состояние меню
function funcToggle() {
  if (toggle) {
    dropMenu.style.opacity = "1";
    dropMenu.style.visibility = "visible";
    dropMenu.style.pointerEvents = "auto";
    dropMenu.style.zIndex = "100";
  } else {
    dropMenu.style.opacity = "0";
    dropMenu.style.visibility = "hidden";
    dropMenu.style.pointerEvents = "none";
    dropMenu.style.zIndex = "-100";
  }
  toggle = !toggle;
}

// проверка пустого чата
function emptyChat() {
  let mes = chatDiv.querySelector(".block-empty-chat");
  if (listMessage.children.length !== 0 && mes) {
    chatDiv.removeChild(mes);
  }
}

function getMessage(data) {
  if (data["room"] === checkRoom) {
    let item = document.createElement("li");
    item.classList.add("message-item-get");
    item.classList.add("message-item");
    item.textContent = data["message"];
    listMessage.appendChild(item);
    emptyChat();
  }
}

function sendMessageKey(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
}

function sendMessage() {
  const message = text.value.trim();
  if (message.trim().length === 0) return;

  socket.emit("message", { message, logFriend, login });
  addClassToSendMessage(message);

  text.value = "";
  emptyChat();
}

// сами сообщения
function addClassToSendMessage(message) {
  let item = document.createElement("li");
  item.classList.add("message-item-send");
  item.classList.add("message-item");
  item.textContent = message;
  listMessage.appendChild(item);
}
