// Establish Socket.IO connection.
let socket = io();
let canvas = document.getElementById("gameCanvas");
let ctx = canvas.getContext("2d");

// UI elements
let menuDiv = document.getElementById("menu");
let gameOverDiv = document.getElementById("gameOver");
let winnerText = document.getElementById("winnerText");
let returnMenuBtn = document.getElementById("returnMenuBtn");
let lobbyDiv = document.getElementById("lobby");
let chatInput = document.getElementById("chatInput");
let chatMessagesDiv = document.getElementById("chatMessages");

let myPlayer = null;
let gameState = {};
let keysPressed = {};
let lastShotTime = 0;
let shotCooldown = 500; // milliseconds
let gameStarted = false;
let mode = "pve";  // default mode

// Main menu buttons
document.getElementById("pvpBtn").addEventListener("click", () => {
  mode = "pvp";
  startGame();
});
document.getElementById("pveBtn").addEventListener("click", () => {
  mode = "pve";
  startGame();
});
document.getElementById("quitBtn").addEventListener("click", () => {
  window.close(); // May not work in most browsers
});
returnMenuBtn.addEventListener("click", () => {
  location.reload();  // Simple reload to return to menu
});

// Chat input handler.
chatInput.addEventListener("keydown", function(e) {
  if (e.key === "Enter") {
    let message = chatInput.value;
    if (message) {
      socket.emit("chat", { message: message });
      chatInput.value = "";
    }
  }
});

// Handle incoming chat messages.
socket.on("chat", function(msg) {
  let d = new Date(msg.timestamp * 1000);
  let timeStr = d.toLocaleTimeString();
  chatMessagesDiv.innerHTML += `<div>[${timeStr}] ${msg.name}: ${msg.message}</div>`;
  chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
});

// Update lobby info.
socket.on("lobby_update", function(data) {
  lobbyDiv.innerHTML = "<strong>Lobby Players:</strong><br>";
  data.forEach(player => {
    lobbyDiv.innerHTML += player.name + " (" + player.team + ")<br>";
  });
});

// Receive game state updates.
socket.on("game_state", function(state) {
  gameState = state;
  if (!gameStarted) return;
  render();
});

// When game over, display the game over screen.
socket.on("game_over", function(data) {
  gameOverDiv.style.display = "flex";
  winnerText.textContent = "Winner: " + data.winner;
});

// When joined, assign our player data.
socket.on("joined", function(data) {
  myPlayer = data;
});

// Start the game: prompt for a name, send join event, and hide the menu.
function startGame() {
  let name = prompt("Enter your name:") || "Player";
  socket.emit("join", { name: name, mode: mode });
  menuDiv.style.display = "none";
  gameStarted = true;
  gameLoop();
}

// Keyboard input handling.
document.addEventListener("keydown", function(e) {
  keysPressed[e.key] = true;
});
document.addEventListener("keyup", function(e) {
  keysPressed[e.key] = false;
});

// Mouse input for shooting (right-click).
canvas.addEventListener("contextmenu", function(e) {
  e.preventDefault();
  if (!myPlayer) return;
  let rect = canvas.getBoundingClientRect();
  let mouseX = e.clientX - rect.left;
  let mouseY = e.clientY - rect.top;
  let centerX = myPlayer.x + 20;
  let centerY = myPlayer.y + 20;
  let angle = Math.atan2(mouseY - centerY, mouseX - centerX);
  let now = Date.now();
  if (now - lastShotTime > shotCooldown) {
    lastShotTime = now;
    socket.emit("shoot", { x: centerX, y: centerY, angle: angle });
  }
  return false;
});

// Skill activation: keys Q, E, R.
document.addEventListener("keydown", function(e) {
  if (myPlayer && (e.key === "q" || e.key === "e" || e.key === "r")) {
    let centerX = myPlayer.x + 20;
    let centerY = myPlayer.y + 20;
    let angle = myPlayer.angle || 0;
    socket.emit("skill", { skill: e.key, x: centerX, y: centerY, angle: angle });
  }
});

// Update player's angle on mouse move.
canvas.addEventListener("mousemove", function(e) {
  if (!myPlayer) return;
  let rect = canvas.getBoundingClientRect();
  let mouseX = e.clientX - rect.left;
  let mouseY = e.clientY - rect.top;
  let centerX = myPlayer.x + 20;
  let centerY = myPlayer.y + 20;
  myPlayer.angle = Math.atan2(mouseY - centerY, mouseX - centerX);
});

// Main game loop: update and render.
function gameLoop() {
  update();
  requestAnimationFrame(gameLoop);
}

// Update player's position based on WASD.
function update() {
  if (!myPlayer) return;
  let speed = myPlayer.speed || 3;
  let dx = 0, dy = 0;
  if (keysPressed["w"]) dy -= speed;
  if (keysPressed["s"]) dy += speed;
  if (keysPressed["a"]) dx -= speed;
  if (keysPressed["d"]) dx += speed;
  if (dx !== 0 || dy !== 0) {
    let len = Math.sqrt(dx * dx + dy * dy);
    dx = (dx / len) * speed;
    dy = (dy / len) * speed;
  }
  myPlayer.x += dx;
  myPlayer.y += dy;
  // Keep within canvas boundaries.
  myPlayer.x = Math.max(0, Math.min(myPlayer.x, canvas.width - 40));
  myPlayer.y = Math.max(0, Math.min(myPlayer.y, canvas.height - 40));
  socket.emit("player_update", { x: myPlayer.x, y: myPlayer.y, angle: myPlayer.angle });
}

// Render the game state.
function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // Draw obstacles.
  if (gameState.obstacles) {
    gameState.obstacles.forEach(obs => {
      ctx.fillStyle = "#654321"; // brown color for destructible terrain
      ctx.fillRect(obs.x, obs.y, obs.width, obs.height);
      if (obs.health < 50) {
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(obs.x, obs.y, obs.width, obs.height);
      }
    });
  }
  // Draw bushes (with transparency).
  if (gameState.bushes) {
    gameState.bushes.forEach(bush => {
      ctx.fillStyle = "rgba(34,139,34,0.6)";
      ctx.fillRect(bush.x, bush.y, bush.width, bush.height);
    });
  }
  // Draw power-ups.
  if (gameState.powerups) {
    gameState.powerups.forEach(p => {
      let color = "#fff";
      if (p.type === "speed") color = "#00f";
      else if (p.type === "shield") color = "#87CEFA";
      else if (p.type === "damage") color = "#FFA500";
      else if (p.type === "health") color = "#f00";
      else if (p.type === "xp") color = "#ff0";
      ctx.fillStyle = color;
      ctx.fillRect(p.x, p.y, p.width, p.height);
    });
  }
  // Draw players.
  if (gameState.players) {
    gameState.players.forEach(player => {
      ctx.fillStyle = player.team === "blue" ? "#0000FF" : "#FF0000";
      ctx.fillRect(player.x, player.y, 40, 40);
      ctx.strokeStyle = "#000";
      ctx.strokeRect(player.x, player.y, 40, 40);
      // Draw a health bar above the tank.
      ctx.fillStyle = "#f00";
      ctx.fillRect(player.x, player.y - 10, 40, 5);
      ctx.fillStyle = "#0f0";
      ctx.fillRect(player.x, player.y - 10, 40 * (player.health / 100), 5);
      // Draw the player's name.
      ctx.fillStyle = "#fff";
      ctx.font = "10px 'Press Start 2P'";
      ctx.fillText(player.name, player.x, player.y - 15);
    });
  }
  // Draw bullets.
  if (gameState.bullets) {
    gameState.bullets.forEach(bullet => {
      ctx.beginPath();
      ctx.arc(bullet.x, bullet.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = bullet.skill ? "#FFA500" : "#ff0";
      ctx.fill();
    });
  }
  // Draw explosions.
  if (gameState.explosions) {
    gameState.explosions.forEach(exp => {
      let radius = Math.max(0, 30 - exp.timer);
      ctx.beginPath();
      ctx.arc(exp.x, exp.y, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "#FFA500";
      ctx.stroke();
    });
  }
  // Draw remaining time.
  if (gameState.time_left !== undefined) {
    ctx.fillStyle = "#fff";
    ctx.font = "16px 'Press Start 2P'";
    ctx.fillText("Time: " + Math.floor(gameState.time_left) + "s", 600, 30);
  }
}
