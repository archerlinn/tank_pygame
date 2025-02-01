import pygame
import sys
import random
import math

# =============================
# INITIALIZATION & CONSTANTS
# =============================
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pixel Tank Battle")
clock = pygame.time.Clock()
FPS = 60

# Colors
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)
RED        = (255, 0, 0)
GREEN      = (0, 255, 0)
BLUE       = (0, 0, 255)
YELLOW     = (255, 255, 0)
GREY       = (100, 100, 100)
BROWN      = (139, 69, 19)
ORANGE     = (255, 165, 0)
DARK_GREEN = (0, 100, 0)

# Fonts
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 40)

# Global game object lists
bullets = []
obstacles = []
bushes = []
powerups = []
explosions = []

# =============================
# CLASS DEFINITIONS
# =============================

class Tank:
    def __init__(self, x, y, color, controls, is_ai=False):
        self.pos = pygame.Vector2(x, y)
        self.color = color
        self.controls = controls  # dictionary mapping actions to pygame key codes
        self.width = 40
        self.height = 40
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.speed = 2.5
        self.health = 100
        self.lives = 3
        self.level = 1
        self.xp = 0
        self.direction = pygame.Vector2(0, -1)  # initially facing upward
        self.last_shot_time = 0
        self.shot_cooldown = 500  # milliseconds delay between shots
        self.is_ai = is_ai
        self.in_bush = False  # For stealth: if inside a bush, becomes “invisible”
        # Active power-ups stored as expiration times (or 0 if inactive)
        self.active_powerups = {"speed": 0, "shield": 0, "damage": 0, "xp": 0}
        self.damage = 20
        # Skill cooldown trackers (skills: "q", "e", "r")
        self.skill_cooldowns = {"q": 0, "e": 0, "r": 0}

    def handle_input(self, keys, current_time):
        # (AI tanks do not handle keyboard input)
        if self.is_ai:
            return

        move = pygame.Vector2(0, 0)
        # Movement (WASD or custom keys based on self.controls)
        if keys[self.controls["up"]]:
            move.y -= 1
        if keys[self.controls["down"]]:
            move.y += 1
        if keys[self.controls["left"]]:
            move.x -= 1
        if keys[self.controls["right"]]:
            move.x += 1
        if move.length() > 0:
            move = move.normalize() * self.speed
            # Apply speed boost if active
            if self.active_powerups["speed"] and current_time < self.active_powerups["speed"]:
                move *= 1.5
            self.pos += move
            self.direction = move.normalize()
        # Shooting (pressing the shoot key fires a bullet)
        if keys[self.controls["shoot"]]:
            self.shoot(current_time)
        # Skills:
        if keys[self.controls["skill_q"]]:
            self.use_skill("q", current_time)
        if self.level >= 2 and keys[self.controls["skill_e"]]:
            self.use_skill("e", current_time)
        if self.level >= 4 and keys[self.controls["skill_r"]]:
            self.use_skill("r", current_time)

    def update(self, current_time):
        self.rect.topleft = (int(self.pos.x), int(self.pos.y))
        self.stay_in_bounds()
        # Determine if tank is hiding in any bush:
        self.in_bush = any(self.rect.colliderect(bush.rect) for bush in bushes)
        # Expire power-ups if their time is up:
        for key in ["speed", "shield", "damage", "xp"]:
            if self.active_powerups[key] and current_time > self.active_powerups[key]:
                self.active_powerups[key] = 0

    def stay_in_bounds(self):
        if self.pos.x < 0:
            self.pos.x = 0
        if self.pos.x > WIDTH - self.width:
            self.pos.x = WIDTH - self.width
        if self.pos.y < 0:
            self.pos.y = 0
        if self.pos.y > HEIGHT - self.height:
            self.pos.y = HEIGHT - self.height

    def shoot(self, current_time):
        # Limit firing rate using cooldown
        if current_time - self.last_shot_time < self.shot_cooldown:
            return
        self.last_shot_time = current_time
        bullet_speed = 5
        dmg_multiplier = 1.5 if self.active_powerups["damage"] and current_time < self.active_powerups["damage"] else 1
        bullet = Bullet(self.pos + pygame.Vector2(self.width/2, self.height/2),
                        self.direction, bullet_speed, self.damage * dmg_multiplier, self)
        bullets.append(bullet)

    def use_skill(self, skill, current_time):
        # Determine the skill’s cooldown (in milliseconds)
        if skill == "q":
            cooldown = 1000
        elif skill == "e":
            cooldown = 1500
        elif skill == "r":
            cooldown = 2000
        else:
            return
        if current_time - self.skill_cooldowns[skill] < cooldown:
            return
        self.skill_cooldowns[skill] = current_time
        # Skill effect: fire a special bullet with increased speed/damage
        bullet_speed = 7
        if skill == "q":
            dmg = self.damage
        elif skill == "e":
            dmg = self.damage * 1.5
        elif skill == "r":
            dmg = self.damage * 2.5
        bullet = Bullet(self.pos + pygame.Vector2(self.width/2, self.height/2),
                        self.direction, bullet_speed, dmg, self, skill=skill)
        bullets.append(bullet)
        # Using a skill “breaks” stealth so the tank becomes visible
        self.in_bush = False

    def draw(self, screen):
        # If in a bush (and not AI), draw with reduced opacity to simulate stealth
        if self.in_bush and not self.is_ai:
            s = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            s.fill((self.color[0], self.color[1], self.color[2], 100))
            screen.blit(s, (self.pos.x, self.pos.y))
        else:
            pygame.draw.rect(screen, self.color, self.rect)
        # Draw a small health bar above the tank
        bar_width = self.width
        health_ratio = self.health / 100
        pygame.draw.rect(screen, RED, (self.pos.x, self.pos.y - 10, bar_width, 5))
        pygame.draw.rect(screen, GREEN, (self.pos.x, self.pos.y - 10, bar_width * health_ratio, 5))


class Bullet:
    def __init__(self, pos, direction, speed, damage, owner, skill="normal"):
        self.pos = pygame.Vector2(pos)
        self.direction = direction.normalize()
        self.speed = speed
        self.damage = damage
        self.owner = owner
        self.radius = 5
        self.skill = skill
        self.rect = pygame.Rect(self.pos.x, self.pos.y, self.radius*2, self.radius*2)

    def update(self):
        self.pos += self.direction * self.speed
        self.rect.topleft = (int(self.pos.x), int(self.pos.y))
        # Remove bullet if it goes off-screen
        if (self.pos.x < 0 or self.pos.x > WIDTH or
            self.pos.y < 0 or self.pos.y > HEIGHT):
            if self in bullets:
                bullets.remove(self)

    def draw(self, screen):
        color = YELLOW if self.skill == "normal" else ORANGE
        pygame.draw.circle(screen, color, (int(self.pos.x), int(self.pos.y)), self.radius)


class Obstacle:
    def __init__(self, x, y, width, height, health=50):
        self.rect = pygame.Rect(x, y, width, height)
        self.health = health

    def draw(self, screen):
        pygame.draw.rect(screen, GREY, self.rect)


class Bush:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, screen):
        s = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        s.fill((34, 139, 34, 150))
        screen.blit(s, (self.rect.x, self.rect.y))


class PowerUp:
    def __init__(self, x, y, type):
        self.rect = pygame.Rect(x, y, 20, 20)
        self.type = type  # one of "speed", "shield", "damage", "health", "xp"

    def draw(self, screen):
        # Choose a color based on the type of power-up
        if self.type == "speed":
            color = BLUE
        elif self.type == "shield":
            color = (135, 206, 250)
        elif self.type == "damage":
            color = ORANGE
        elif self.type == "health":
            color = RED
        elif self.type == "xp":
            color = YELLOW
        else:
            color = WHITE
        pygame.draw.rect(screen, color, self.rect)


class Explosion:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.timer = 30  # frames

    def update(self):
        self.timer -= 1
        if self.timer <= 0 and self in explosions:
            explosions.remove(self)

    def draw(self, screen):
        # Draw an expanding circle to simulate an explosion effect
        radius = max(0, 30 - self.timer)
        pygame.draw.circle(screen, ORANGE, (int(self.pos.x), int(self.pos.y)), radius, 2)


# =============================
# HELPER FUNCTIONS & AI LOGIC
# =============================

def ai_control(ai_tank, target_tank, current_time):
    """
    A simple AI that:
      - Moves toward the target tank.
      - Shoots when the target is near.
      - Occasionally uses skills.
    """
    direction = target_tank.pos - ai_tank.pos
    if direction.length() != 0:
        ai_tank.direction = direction.normalize()
    # Move toward the player (scaled down so AI isn’t too perfect)
    move_vector = ai_tank.direction * ai_tank.speed
    ai_tank.pos += move_vector * 0.5
    # If within a certain range, fire normally
    if direction.length() < 300:
        ai_tank.shoot(current_time)
    # Occasionally use skills
    if current_time % 2000 < 50:
        ai_tank.use_skill("q", current_time)
        if ai_tank.level >= 2:
            ai_tank.use_skill("e", current_time)
        if ai_tank.level >= 4:
            ai_tank.use_skill("r", current_time)

def spawn_powerup():
    types = ["speed", "shield", "damage", "health", "xp"]
    type_choice = random.choice(types)
    x = random.randint(50, WIDTH - 50)
    y = random.randint(50, HEIGHT - 50)
    powerup = PowerUp(x, y, type_choice)
    powerups.append(powerup)

def spawn_obstacles():
    # Create a few random obstacles (destructible terrain)
    for _ in range(5):
        x = random.randint(100, WIDTH - 150)
        y = random.randint(100, HEIGHT - 150)
        width = random.randint(40, 100)
        height = random.randint(40, 100)
        obstacles.append(Obstacle(x, y, width, height, health=50))

def spawn_bushes():
    # Create bushes that allow tanks to hide (stealth)
    for _ in range(5):
        x = random.randint(50, WIDTH - 100)
        y = random.randint(50, HEIGHT - 100)
        bushes.append(Bush(x, y, 60, 60))

# =============================
# UI SCREENS: MAIN MENU & GAME OVER
# =============================

def main_menu():
    menu = True
    selected_mode = None
    while menu:
        screen.fill(BLACK)
        title_text = big_font.render("Pixel Tank Battle", True, WHITE)
        pvp_text = font.render("1. Player vs Player", True, WHITE)
        pve_text = font.render("2. Player vs AI", True, WHITE)
        settings_text = font.render("3. Settings (Not Implemented)", True, WHITE)
        quit_text = font.render("4. Quit", True, WHITE)
        screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, 100))
        screen.blit(pvp_text, (WIDTH // 2 - pvp_text.get_width() // 2, 200))
        screen.blit(pve_text, (WIDTH // 2 - pve_text.get_width() // 2, 250))
        screen.blit(settings_text, (WIDTH // 2 - settings_text.get_width() // 2, 300))
        screen.blit(quit_text, (WIDTH // 2 - quit_text.get_width() // 2, 350))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    selected_mode = "pvp"
                    menu = False
                elif event.key == pygame.K_2:
                    selected_mode = "pve"
                    menu = False
                elif event.key == pygame.K_4:
                    pygame.quit()
                    sys.exit()
        clock.tick(FPS)
    return selected_mode

def game_over(winner_text):
    over = True
    while over:
        screen.fill(BLACK)
        over_text = big_font.render("Game Over!", True, RED)
        winner_display = font.render(winner_text, True, WHITE)
        menu_text = font.render("Press M to return to Main Menu", True, WHITE)
        screen.blit(over_text, (WIDTH // 2 - over_text.get_width() // 2, 150))
        screen.blit(winner_display, (WIDTH // 2 - winner_display.get_width() // 2, 220))
        screen.blit(menu_text, (WIDTH // 2 - menu_text.get_width() // 2, 300))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    over = False
        clock.tick(FPS)

# =============================
# MAIN GAME LOOP
# =============================

def game_loop(mode):
    # Reset global objects
    global bullets, obstacles, bushes, powerups, explosions
    bullets = []
    obstacles = []
    bushes = []
    powerups = []
    explosions = []

    # Spawn initial obstacles, bushes, and a power-up
    spawn_obstacles()
    spawn_bushes()
    spawn_powerup()
    powerup_spawn_timer = pygame.time.get_ticks() + 5000  # new power-up every 5 seconds

    # Create tanks with distinct controls.
    # For Player 1 (blue): use WASD for movement, SPACE for shooting, and Q/E/R for skills.
    player1_controls = {
        "up": pygame.K_w,
        "down": pygame.K_s,
        "left": pygame.K_a,
        "right": pygame.K_d,
        "shoot": pygame.K_SPACE,
        "skill_q": pygame.K_q,
        "skill_e": pygame.K_e,
        "skill_r": pygame.K_r
    }
    player1 = Tank(100, 100, BLUE, player1_controls, is_ai=False)

    # For Player 2 (red) or AI:
    if mode == "pvp":
        # Use IJKL for movement, Right Shift for shooting, and U/O/P for skills.
        player2_controls = {
            "up": pygame.K_i,
            "down": pygame.K_k,
            "left": pygame.K_j,
            "right": pygame.K_l,
            "shoot": pygame.K_RSHIFT,
            "skill_q": pygame.K_u,
            "skill_e": pygame.K_o,
            "skill_r": pygame.K_p
        }
        player2 = Tank(600, 400, RED, player2_controls, is_ai=False)
    elif mode == "pve":
        # In PvE, the enemy is AI controlled.
        player2 = Tank(600, 400, RED, {}, is_ai=True)

    tanks = [player1, player2]

    # Set a game duration of 10 minutes (600,000 milliseconds)
    game_duration = 10 * 60 * 1000
    start_time = pygame.time.get_ticks()

    running = True
    while running:
        current_time = pygame.time.get_ticks()
        elapsed_time = current_time - start_time
        remaining_time = max(0, game_duration - elapsed_time)

        # End the match if time runs out or a tank loses all lives.
        if remaining_time <= 0 or any(tank.lives <= 0 for tank in tanks):
            running = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        keys = pygame.key.get_pressed()
        # Process input (or AI logic) for each tank:
        for tank in tanks:
            if not tank.is_ai:
                tank.handle_input(keys, current_time)
            else:
                # In PvE, AI always targets player1.
                ai_control(tank, player1, current_time)
        for tank in tanks:
            tank.update(current_time)

        # Update bullets and handle collisions:
        for bullet in bullets[:]:
            bullet.update()
            # Check collision with obstacles (destructible terrain)
            for obs in obstacles[:]:
                if bullet.rect.colliderect(obs.rect):
                    obs.health -= bullet.damage
                    if obs.health <= 0:
                        obstacles.remove(obs)
                        explosions.append(Explosion(obs.rect.center))
                    if bullet in bullets:
                        bullets.remove(bullet)
                    break
            # Check collision with tanks (but not the bullet’s owner)
            for tank in tanks:
                if tank != bullet.owner and bullet.rect.colliderect(tank.rect):
                    if tank.active_powerups["shield"] and current_time < tank.active_powerups["shield"]:
                        # Shield power-up negates damage
                        pass
                    else:
                        tank.health -= bullet.damage
                    if tank.health <= 0:
                        tank.lives -= 1
                        tank.health = 100  # Reset health on respawn
                        bullet.owner.xp += 20
                        # Level-up: each level requires more XP (here, level × 100 XP)
                        if bullet.owner.xp >= 100 * bullet.owner.level:
                            bullet.owner.level += 1
                            bullet.owner.damage += 5  # Increase damage with each level
                    if bullet in bullets:
                        bullets.remove(bullet)
                    break

        # Update explosions
        for explosion in explosions[:]:
            explosion.update()

        # Check for collisions with power-ups:
        for powerup in powerups[:]:
            for tank in tanks:
                if tank.rect.colliderect(powerup.rect):
                    if powerup.type == "speed":
                        tank.active_powerups["speed"] = current_time + 5000  # lasts 5 seconds
                    elif powerup.type == "shield":
                        tank.active_powerups["shield"] = current_time + 5000
                    elif powerup.type == "damage":
                        tank.active_powerups["damage"] = current_time + 5000
                    elif powerup.type == "health":
                        tank.health = min(100, tank.health + 30)
                    elif powerup.type == "xp":
                        tank.xp += 30
                        if tank.xp >= 100 * tank.level:
                            tank.level += 1
                            tank.damage += 5
                    powerups.remove(powerup)
                    break

        # Spawn new power-ups periodically
        if current_time > powerup_spawn_timer:
            spawn_powerup()
            powerup_spawn_timer = current_time + 5000

        # =============================
        # DRAWING
        # =============================
        screen.fill(DARK_GREEN)
        for obs in obstacles:
            obs.draw(screen)
        for bush in bushes:
            bush.draw(screen)
        for powerup in powerups:
            powerup.draw(screen)
        for tank in tanks:
            tank.draw(screen)
        for bullet in bullets:
            bullet.draw(screen)
        for explosion in explosions:
            explosion.draw(screen)

        # UI overlay for each tank: lives, health, level and XP
        for idx, tank in enumerate(tanks):
            info = f"Player {idx+1}: Lives {tank.lives}  Health {tank.health}  Level {tank.level}  XP {tank.xp}"
            info_text = font.render(info, True, WHITE)
            screen.blit(info_text, (10, 10 + idx * 20))
        # Draw the remaining game time (in seconds)
        timer_text = font.render(f"Time Left: {remaining_time // 1000}s", True, WHITE)
        screen.blit(timer_text, (WIDTH - 150, 10))

        pygame.display.flip()
        clock.tick(FPS)

    # =============================
    # DETERMINE & SHOW WINNER
    # =============================
    if tanks[0].lives > tanks[1].lives:
        winner_text = "Player 1 Wins!"
    elif tanks[1].lives > tanks[0].lives:
        winner_text = "Player 2 Wins!"
    else:
        winner_text = "It's a Draw!"
    game_over(winner_text)

# =============================
# MAIN PROGRAM LOOP
# =============================

while True:
    mode = main_menu()
    game_loop(mode)
