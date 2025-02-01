import math
import random
import time

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()  # Required for proper async support with Socket.IO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# -------------------------------
# GLOBAL GAME STATE
# -------------------------------
players = {}    # key: sid (or AI id), value: player dictionary
bullets = []    # list of bullet dictionaries
obstacles = []  # destructible terrain objects
bushes = []     # bushes for stealth
powerups = []   # power-up objects
explosions = [] # explosion effects

# Game settings
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
GAME_DURATION = 10 * 60  # in seconds (10 minutes)
game_start_time = None
game_mode = None       # "pvp" or "pve"
game_active = False

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def spawn_obstacles():
    global obstacles
    obstacles = []
    for _ in range(5):
        x = random.randint(100, CANVAS_WIDTH - 150)
        y = random.randint(100, CANVAS_HEIGHT - 150)
        width = random.randint(40, 100)
        height = random.randint(40, 100)
        obstacles.append({
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'health': 50
        })

def spawn_bushes():
    global bushes
    bushes = []
    for _ in range(4):
        x = random.randint(50, CANVAS_WIDTH - 100)
        y = random.randint(50, CANVAS_HEIGHT - 100)
        bushes.append({
            'x': x,
            'y': y,
            'width': 60,
            'height': 60
        })

def spawn_powerup():
    types = ["speed", "shield", "damage", "health", "xp"]
    p_type = random.choice(types)
    x = random.randint(50, CANVAS_WIDTH - 50)
    y = random.randint(50, CANVAS_HEIGHT - 50)
    powerup = {
        'x': x,
        'y': y,
        'width': 20,
        'height': 20,
        'type': p_type,
        'duration': 5000  # effect duration (handled client‐side)
    }
    powerups.append(powerup)

# -------------------------------
# FLASK ROUTE
# -------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# -------------------------------
# SOCKET.IO EVENT HANDLERS
# -------------------------------
@socketio.on('join')
def handle_join(data):
    global game_start_time, game_mode, game_active
    sid = request.sid
    name = data.get('name', 'Player')
    mode = data.get('mode', 'pve')  # default to PvE
    game_mode = mode
    # Initialize player properties
    x = random.randint(0, CANVAS_WIDTH - 40)
    y = random.randint(0, CANVAS_HEIGHT - 40)
    players[sid] = {
        'sid': sid,
        'name': name,
        'x': x,
        'y': y,
        'angle': 0,
        'health': 100,
        'lives': 3,
        'xp': 0,
        'level': 1,
        'damage': 20,
        'speed': 3,
        'mode': 'human',  # human-controlled
        'last_shot': 0,
        'cooldowns': {'q': 0, 'e': 0, 'r': 0},
        'inBush': False,
        'team': 'blue'  # For PvP you might assign teams differently
    }
    emit('joined', players[sid])
    update_lobby()
    print(f"{name} joined as {sid} in mode {mode}")
    # If playing versus computer, spawn an AI tank if none exists
    if mode == 'pve':
        ai_exists = any(p for p in players.values() if p.get('mode') == 'ai')
        if not ai_exists:
            spawn_ai()

    # Start the game if not already active.
    if not game_active:
        game_start_time = time.time()
        game_active = True
        spawn_obstacles()
        spawn_bushes()
        spawn_powerup()

@socketio.on('player_update')
def handle_player_update(data):
    sid = request.sid
    if sid in players:
        players[sid]['x'] = data.get('x', players[sid]['x'])
        players[sid]['y'] = data.get('y', players[sid]['y'])
        players[sid]['angle'] = data.get('angle', players[sid]['angle'])

@socketio.on('shoot')
def handle_shoot(data):
    sid = request.sid
    now = int(time.time() * 1000)
    player = players.get(sid)
    if not player:
        return
    # Enforce a 500ms shot cooldown
    if now - player['last_shot'] < 500:
        return
    player['last_shot'] = now
    bullet = {
        'x': data.get('x', player['x']+20),
        'y': data.get('y', player['y']+20),
        'angle': data.get('angle', player['angle']),
        'speed': 5,
        'damage': player['damage'],
        'owner': sid,
        'skill': None
    }
    bullets.append(bullet)
    print(f"{player['name']} fired a bullet.")

@socketio.on('skill')
def handle_skill(data):
    sid = request.sid
    player = players.get(sid)
    if not player:
        return
    skill = data.get('skill', 'q')
    now = int(time.time() * 1000)
    # Skill cooldowns: q=1000ms, e=1500ms, r=2000ms
    cooldowns = {'q': 1000, 'e': 1500, 'r': 2000}
    if now - player['cooldowns'].get(skill, 0) < cooldowns.get(skill, 1000):
        return
    player['cooldowns'][skill] = now
    # Skill bullet: faster and more damaging (with multipliers)
    bullet = {
        'x': data.get('x', player['x']+20),
        'y': data.get('y', player['y']+20),
        'angle': data.get('angle', player['angle']),
        'speed': 7,
        'damage': player['damage'] * (1.5 if skill=='e' else (2.5 if skill=='r' else 1)),
        'owner': sid,
        'skill': skill
    }
    bullets.append(bullet)
    print(f"{player['name']} used skill {skill}.")

@socketio.on('chat')
def handle_chat(data):
    sid = request.sid
    player = players.get(sid, {})
    name = player.get('name', 'Unknown')
    timestamp = int(time.time())
    msg = {
        'sid': sid,
        'name': name,
        'message': data.get('message', ''),
        'timestamp': timestamp
    }
    socketio.emit('chat', msg)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in players:
        print(f"{players[sid]['name']} disconnected.")
        del players[sid]
    update_lobby()

def update_lobby():
    socketio.emit('lobby_update', list(players.values()))

def spawn_ai():
    # Create an AI-controlled tank with slightly lower stats
    ai_id = "AI_" + str(random.randint(1000,9999))
    players[ai_id] = {
        'sid': ai_id,
        'name': "Computer",
        'x': random.randint(0, CANVAS_WIDTH - 40),
        'y': random.randint(0, CANVAS_HEIGHT - 40),
        'angle': 0,
        'health': 100,
        'lives': 3,
        'xp': 0,
        'level': 1,
        'damage': 18,   # a bit lower than the human
        'speed': 2.5,
        'mode': 'ai',
        'last_shot': 0,
        'cooldowns': {'q': 0, 'e': 0, 'r': 0},
        'inBush': False,
        'team': 'red'
    }
    print("Spawned AI tank.")

def update_ai(player):
    # A simple AI that chases the first human player found
    human_players = [p for p in players.values() if p.get('mode') == 'human']
    if not human_players:
        return
    target = human_players[0]
    dx = target['x'] - player['x']
    dy = target['y'] - player['y']
    distance = math.hypot(dx, dy)
    if distance > 0:
        player['x'] += (dx/distance) * player['speed'] * 0.5  # move at half speed
        player['y'] += (dy/distance) * player['speed'] * 0.5
        player['angle'] = math.atan2(dy, dx)
    # Shoot if in range and cooldown elapsed
    now = int(time.time() * 1000)
    if distance < 300 and now - player['last_shot'] > 1000:
        player['last_shot'] = now
        bullet = {
            'x': player['x'] + 20,
            'y': player['y'] + 20,
            'angle': player['angle'],
            'speed': 5,
            'damage': player['damage'],
            'owner': player['sid'],
            'skill': None
        }
        bullets.append(bullet)
        print("AI fired a bullet.")

# -------------------------------
# GAME LOOP (Background Task)
# -------------------------------
def game_loop():
    global game_active, game_start_time
    powerup_spawn_timer = time.time() + 5  # every 5 seconds
    while True:
        socketio.sleep(0.05)  # ~20 FPS
        now = time.time()
        # Update AI-controlled tanks
        for p in players.values():
            if p.get('mode') == 'ai':
                update_ai(p)
        # Update bullet positions and check collisions with players
        for bullet in bullets[:]:
            angle = bullet['angle']
            bullet['x'] += bullet['speed'] * math.cos(angle)
            bullet['y'] += bullet['speed'] * math.sin(angle)
            if (bullet['x'] < 0 or bullet['x'] > CANVAS_WIDTH or
                bullet['y'] < 0 or bullet['y'] > CANVAS_HEIGHT):
                if bullet in bullets:
                    bullets.remove(bullet)
                continue
            # Check collision with players (simple rectangle collision, assuming tank size 40×40)
            for p in players.values():
                if bullet['owner'] == p['sid']:
                    continue
                if (p['x'] < bullet['x'] < p['x']+40 and
                    p['y'] < bullet['y'] < p['y']+40):
                    p['health'] -= bullet['damage']
                    if bullet in bullets:
                        bullets.remove(bullet)
                    if p['health'] <= 0:
                        p['lives'] -= 1
                        p['health'] = 100
                        p['x'] = random.randint(0, CANVAS_WIDTH - 40)
                        p['y'] = random.randint(0, CANVAS_HEIGHT - 40)
                        # Award XP to the bullet’s owner if that player is human
                        owner = players.get(bullet['owner'])
                        if owner and owner.get('mode') == 'human':
                            owner['xp'] += 20
                            if owner['xp'] >= owner['level'] * 100 and owner['level'] < 4:
                                owner['level'] += 1
                                owner['damage'] += 5
                                print(f"{owner['name']} leveled up to {owner['level']}!")
                    break

        # Check bullet collisions with obstacles (destructible terrain)
        for bullet in bullets[:]:
            for obs in obstacles[:]:
                if (obs['x'] < bullet['x'] < obs['x']+obs['width'] and
                    obs['y'] < bullet['y'] < obs['y']+obs['height']):
                    obs['health'] -= bullet['damage']
                    if obs['health'] <= 0:
                        obstacles.remove(obs)
                        explosions.append({
                            'x': obs['x'] + obs['width']/2,
                            'y': obs['y'] + obs['height']/2,
                            'timer': 30
                        })
                    if bullet in bullets:
                        bullets.remove(bullet)
                    break

        # Update explosion effects
        for exp in explosions[:]:
            exp['timer'] -= 1
            if exp['timer'] <= 0:
                explosions.remove(exp)

        # Check collisions with power-ups and apply effects
        for power in powerups[:]:
            for p in players.values():
                if (p['x'] < power['x'] < p['x']+40 and
                    p['y'] < power['y'] < p['y']+40):
                    if power['type'] == 'speed':
                        p['speed'] += 1
                    elif power['type'] == 'shield':
                        # (Shield effect could be implemented with a temporary flag)
                        pass
                    elif power['type'] == 'damage':
                        p['damage'] += 5
                    elif power['type'] == 'health':
                        p['health'] = min(100, p['health'] + 30)
                    elif power['type'] == 'xp':
                        p['xp'] += 30
                        if p['xp'] >= p['level'] * 100 and p['level'] < 4:
                            p['level'] += 1
                            p['damage'] += 5
                    powerups.remove(power)
                    break

        # Spawn new power-ups periodically
        if now > powerup_spawn_timer:
            spawn_powerup()
            powerup_spawn_timer = now + 5

        # Check game-over conditions: time expiration or a human losing all lives
        if game_active and game_start_time:
            if now - game_start_time > GAME_DURATION:
                game_active = False
                determine_winner()
            else:
                human_players = [p for p in players.values() if p.get('mode')=='human']
                if human_players and any(p['lives'] <= 0 for p in human_players):
                    game_active = False
                    determine_winner()

        # Broadcast overall game state to all clients
        state = {
            'players': list(players.values()),
            'bullets': bullets,
            'obstacles': obstacles,
            'bushes': bushes,
            'powerups': powerups,
            'explosions': explosions,
            'time_left': max(0, GAME_DURATION - (now - game_start_time)) if game_start_time else GAME_DURATION
        }
        socketio.emit('game_state', state)

def determine_winner():
    human_players = [p for p in players.values() if p.get('mode')=='human']
    if not human_players:
        winner = "No human players"
    else:
        winner = max(human_players, key=lambda p: (p['lives'], p['xp']))['name']
    socketio.emit('game_over', {'winner': winner})
    print(f"Game over! Winner: {winner}")
    reset_game()

def reset_game():
    global players, bullets, obstacles, bushes, powerups, explosions, game_active, game_start_time
    players = {}
    bullets = []
    obstacles = []
    bushes = []
    powerups = []
    explosions = []
    game_active = False
    game_start_time = None

if __name__ == '__main__':
    socketio.start_background_task(game_loop)
    socketio.run(app, debug=True)
