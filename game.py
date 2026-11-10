"""Lost in Toyland — a side-view platformer built with Pygame Zero.

A mother carries her child into an abandoned Toyland. To escape they
must survive a wind-up robot, crawl through a tiny tunnel to find a
stolen bear eye, repair the angry bear from its blind side and then
reach the exit door together.
"""

import math

import pgzero

WIDTH = 1300
HEIGHT = 708
TITLE = 'Lost in Toyland'

# Physics (pixels, seconds)
GRAVITY = 1500
MOTHER_SPEED = 270
CHILD_SPEED = 210
MOTHER_JUMP = -650

# Gameplay tuning
CHILD_RADIUS = 260          # max distance the child may stray from mother
CARRY_DISTANCE = 120        # how close mother must be to pick the child up
INTERACT_DISTANCE = 150     # range for repair / exit hints
INTRO_TIME = 6.0            # seconds the control banner stays visible
MOMMY_TIME = 1.4            # seconds the "Mommy!" call stays on screen
WALK_FRAME_TIME = 0.12      # seconds per walk-animation frame
POSE_TIME = 0.5             # seconds a one-off pose (pickup/drop) shows
TUNNEL_ALPHA = 160          # tunnel transparency: 0 = invisible, 255 = solid

# Level geometry
FLOOR = Rect((0, 660), (WIDTH, 48))
PLATFORMS = [
    Rect((60, 440), (120, 20)),    # upper step near the spawn
    Rect((180, 540), (130, 20)),   # lower step near the spawn
    Rect((360, 410), (120, 20)),   # bridge step toward the tunnel
]
# The tunnel block sits ON the floor. It is solid for the mother
# (who can jump over it - it is shorter than her jump), but the baby,
# who cannot jump, crawls straight THROUGH it (the tunnel is excluded
# from the baby's collision solids). The bear's eye hides inside.
TUNNEL = Rect((560, FLOOR.top - images.tunnel.get_height()),
              (images.tunnel.get_width(), images.tunnel.get_height()))
SOLIDS = [FLOOR] + PLATFORMS + [TUNNEL]
CHILD_SOLIDS = [FLOOR] + PLATFORMS
EYE_POS = (TUNNEL.centerx, FLOOR.top - 23)
DOOR = Rect((1255, 545), (45, 115))

# Game states
MENU = 'menu'
PLAYING = 'playing'
PAUSED = 'paused'
WIN = 'win'
LOSE = 'lose'

# Colors
INK = (255, 255, 255)
GOLD = (255, 210, 90)
PINK = (255, 120, 200)
BUTTON_FILL = (60, 50, 110)
OVERLAY_COLOR = (25, 20, 45)
DOOR_LOCKED = (150, 60, 50)
DOOR_OPEN = (60, 180, 90)
FRIENDLY_GREEN = (90, 220, 130)


def play_sound():
    """Play the (single, placeholder) sound effect if audio is on."""
    if game.audio_on:
        sounds.eep.play()


def distance(a, b):
    """Distance between the centres of two game objects."""
    return math.hypot(a.x - b.x, a.y - b.y)


class Animation:
    """A looping sprite-frame sequence driven by elapsed time."""

    def __init__(self, frames, frame_duration):
        self.frames = frames
        self.frame_duration = frame_duration
        self.elapsed = 0.0
        self.index = 0

    def update(self, dt):
        self.elapsed += dt
        while self.elapsed >= self.frame_duration:
            self.elapsed -= self.frame_duration
            self.index = (self.index + 1) % len(self.frames)

    def reset(self):
        self.elapsed = 0.0
        self.index = 0

    @property
    def frame(self):
        return self.frames[self.index]


class Character:
    """A controllable character with gravity, jumping and collisions.

    The collision box has a FIXED size (box_width/box_height), separate
    from the sprite artwork, so differently sized sprite frames never
    change the gameplay. Sprites are anchored at the bottom-centre, so
    the character's feet always stay on the ground.
    """

    box_width = 66
    box_height = 92

    def __init__(self, image_name, start_x, speed, jump_velocity):
        self.base_image = image_name
        self.start_x = start_x
        self.speed = speed
        self.jump_velocity = jump_velocity
        self.actor = Actor(image_name, (start_x, FLOOR.top))
        self.idle_image = image_name
        self.jump_image = image_name
        self.walk_animation = Animation([image_name], WALK_FRAME_TIME)
        self.transition_image = None
        self.transition_timer = 0.0
        self.calling = False
        self.reset()

    def set_image(self, image_name):
        """Swap to another sprite frame, keeping the feet planted.

        pgzero anchors are PIXEL offsets from the top-left corner, so
        the anchor must be re-calculated whenever a frame with a
        different size is loaded. After this, actor.x is the centre of
        the sprite and actor.y is the soles of its feet.
        """
        center_x = self.actor.x
        feet = self.actor.y
        self.actor.image = image_name
        self.actor.anchor = (self.actor.width / 2, self.actor.height)
        self.actor.x = center_x
        self.actor.y = feet

    def flash_frame(self, image_name, duration=POSE_TIME):
        """Briefly show a one-off pose (e.g. just picked up the child)."""
        self.transition_image = image_name
        self.transition_timer = duration

    def reset(self):
        self.set_image(self.base_image)
        self.actor.x = self.start_x
        self.actor.y = FLOOR.top
        self.velocity_y = 0.0
        self.on_ground = False
        self.facing = 1
        self.walk_animation.reset()
        self.transition_timer = 0.0
        self.calling = False

    @property
    def rect(self):
        """The fixed gameplay hitbox (feet-anchored)."""
        return Rect((self.actor.x - self.box_width / 2,
                     self.actor.y - self.box_height),
                    (self.box_width, self.box_height))

    @property
    def x(self):
        return self.actor.x

    @property
    def y(self):
        return self.actor.y

    @property
    def bottom(self):
        return self.actor.y

    def jump(self):
        self.velocity_y = self.jump_velocity
        self.on_ground = False

    def _overlaps(self, solid):
        """Float-precise overlap test between the fixed box and `solid`."""
        left = self.actor.x - self.box_width / 2
        top = self.actor.y - self.box_height
        return (left < solid.right
                and left + self.box_width > solid.left
                and top < solid.bottom
                and top + self.box_height > solid.top)

    def update(self, dt, move_direction, solids):
        """Apply horizontal input, gravity and collisions with solids."""
        if move_direction:
            self.facing = move_direction
        self.actor.x += move_direction * self.speed * dt

        for solid in solids:
            if self._overlaps(solid):
                if move_direction > 0:
                    self.actor.x = solid.left - self.box_width / 2
                elif move_direction < 0:
                    self.actor.x = solid.right + self.box_width / 2

        self.velocity_y += GRAVITY * dt
        self.actor.y += self.velocity_y * dt
        self.on_ground = False
        for solid in solids:
            if self._overlaps(solid):
                if self.velocity_y >= 0:
                    self.actor.y = solid.top
                    self.on_ground = True
                else:
                    self.actor.y = solid.bottom + self.box_height
                self.velocity_y = 0.0

        half_width = self.box_width / 2
        if self.actor.x < half_width:
            self.actor.x = half_width
        if self.actor.x > WIDTH - half_width:
            self.actor.x = WIDTH - half_width

        self.animate(dt, move_direction)

    def animate(self, dt, move_direction):
        """Choose and apply the sprite frame for the current state."""
        if self.transition_timer > 0:
            self.transition_timer -= dt
            frame = self.transition_image
        elif not self.on_ground:
            frame = self.jump_image
        elif move_direction:
            self.walk_animation.update(dt)
            frame = self.walk_animation.frame
        else:
            self.walk_animation.reset()
            frame = self.idle_image
        if frame != self.actor.image:
            self.set_image(frame)


class Mother(Character):
    """The mother: carries her child; too big for the tunnel."""

    FRAMES_ALONE = {
        'idle': 'mom_idle',
        'walk': ['mom_walk_1', 'mom_walk_2', 'mom_walk_3', 'mom_walk_4'],
        'jump': 'mom_jump',
    }
    FRAMES_CARRYING = {
        'idle': 'mom_baby_idle',
        'walk': ['mom_baby_walk_1', 'mom_baby_walk_2',
                 'mom_baby_walk_3', 'mom_baby_walk_4'],
        'jump': 'mom_baby_jump',
    }

    def __init__(self, image_name, start_x, speed, jump_velocity):
        super().__init__(image_name, start_x, speed, jump_velocity)
        self.carrying = False
        self.show_carrying(False)

    def show_carrying(self, carrying):
        """Switch between the alone and carrying animation sets."""
        frames = self.FRAMES_CARRYING if carrying else self.FRAMES_ALONE
        self.carrying = carrying
        self.idle_image = frames['idle']
        self.jump_image = frames['jump']
        self.walk_animation = Animation(frames['walk'], WALK_FRAME_TIME)
        self.set_image(frames['idle'])


class Child(Character):
    """The child: small, quick, and the only one who fits in the tunnel."""

    box_width = 33
    box_height = 46

    def __init__(self, image_name, start_x, speed, jump_velocity):
        super().__init__(image_name, start_x, speed, jump_velocity)
        self.idle_image = 'baby_idle'
        self.jump_image = 'baby_idle'
        self.calling_image = 'baby_calling_mom'
        self.walk_animation = Animation(
            ['baby_carwl_1', 'baby_carwl_2', 'baby_carwl_3'],
            WALK_FRAME_TIME)

    def animate(self, dt, move_direction):
        """Show the calling pose while the child wants its mother."""
        if self.calling:
            if self.actor.image != self.calling_image:
                self.set_image(self.calling_image)
            return
        super().animate(dt, move_direction)


class Enemy:
    """Base class for patrolling enemies with a telegraphed charge."""

    killer_label = 'enemy'

    def __init__(self, patrol_left, patrol_right, speed, charge_speed,
                 alert_time, detect_range):
        self.patrol_left = patrol_left
        self.patrol_right = patrol_right
        self.speed = speed
        self.charge_speed = charge_speed
        self.alert_time = alert_time
        self.detect_range = detect_range
        self.state = 'patrol'
        self.direction = -1
        self.alert_timer = 0.0
        self.charge_direction = -1

    def reset(self):
        self.state = 'patrol'
        self.direction = -1
        self.alert_timer = 0.0
        self.charge_direction = -1

    def advance(self, distance):
        """Move by `distance`, bouncing off patrol bounds.

        Returns True when a patrol bound was reached.
        """
        self.x += distance
        hit_bound = False
        if self.x < self.patrol_left:
            self.x = self.patrol_left
            self.direction = 1
            hit_bound = True
        elif self.x > self.patrol_right:
            self.x = self.patrol_right
            self.direction = -1
            hit_bound = True
        return hit_bound

    def sees_target(self, target, vertical_tolerance=100):
        """True when a target stands in front of the enemy, in range."""
        offset = target.x - self.x
        if offset * self.direction <= 0:
            return False
        if abs(offset) > self.detect_range:
            return False
        return abs(target.bottom - self.bottom) < vertical_tolerance

    def touches(self, target):
        return self.box.colliderect(target.rect)

    def update_brain(self, dt, targets):
        """Shared patrol -> alert -> charge behaviour."""
        if self.state == 'patrol':
            self.advance(self.direction * self.speed * dt)
            for target in targets:
                if self.sees_target(target):
                    self.state = 'alert'
                    self.alert_timer = self.alert_time
                    self.charge_direction = 1 if target.x > self.x else -1
                    play_sound()
                    break
        elif self.state == 'alert':
            self.alert_timer -= dt
            if self.alert_timer <= 0:
                self.state = 'charge'
        else:
            if self.advance(self.charge_direction * self.charge_speed * dt):
                self.state = 'patrol'


class Robot(Enemy):
    """The wind-up robot guarding the corridor before the tunnel."""

    killer_label = 'robot'
    BODY_COLOR = (150, 155, 170)
    ALERT_COLOR = (210, 70, 60)

    def __init__(self):
        super().__init__(260, 470, speed=55, charge_speed=300,
                         alert_time=0.9, detect_range=170)
        self.width = 56
        self.height = 72
        self.reset()

    def reset(self):
        super().reset()
        self.x = 360

    @property
    def y(self):
        return FLOOR.top - self.height / 2

    @property
    def bottom(self):
        return FLOOR.top

    @property
    def box(self):
        return Rect((self.x - self.width / 2, self.bottom - self.height),
                    (self.width, self.height))

    def update(self, dt, targets):
        self.update_brain(dt, targets)

    def draw(self):
        left = self.x - self.width / 2
        top = self.bottom - self.height
        flashing = self.state == 'alert' and int(self.alert_timer * 8) % 2 == 0
        body_color = self.ALERT_COLOR if flashing else self.BODY_COLOR
        screen.draw.filled_rect(
            Rect((left, top + 14), (self.width, self.height - 14)),
            body_color)
        screen.draw.filled_circle((self.x, top + 14), 14, body_color)
        eye_color = (255, 60, 60) if self.state != 'patrol' else (35, 35, 55)
        for offset in (-8, 8):
            screen.draw.filled_circle(
                (self.x + offset + self.direction * 3, top + 12), 4,
                eye_color)
        key_x = self.x - self.direction * (self.width / 2 + 10)
        screen.draw.filled_circle((key_x, top + 30), 6, (200, 170, 70))
        screen.draw.line((key_x, top + 30), (key_x, top + 6), (200, 170, 70))
        if self.state == 'alert':
            screen.draw.text('!', center=(self.x, top - 22), fontsize=40,
                            color=(255, 80, 80))


class Bear(Enemy):
    """The broken bear: attacks what it sees until it is saved."""

    killer_label = 'toy'
    BASE_IMAGE = 'bear'
    HAPPY_IMAGE = 'bear_happy'
    BOX_WIDTH = 66
    BOX_HEIGHT = 99

    def __init__(self):
        super().__init__(1090, 1240, speed=50, charge_speed=230,
                         alert_time=0.7, detect_range=240)
        self.actor = Actor(self.BASE_IMAGE, (1150, FLOOR.top))
        self.repaired = False
        self.happy_sprite = False
        self.reset()

    def set_image(self, image_name):
        """Swap sprite frames while keeping the bear's feet planted."""
        center_x = self.actor.x
        feet = self.actor.y
        self.actor.image = image_name
        self.actor.anchor = (self.actor.width / 2, self.actor.height)
        self.actor.x = center_x
        self.actor.y = feet

    def reset(self):
        super().reset()
        self.repaired = False
        self.happy_sprite = False
        self.set_image(self.BASE_IMAGE)
        self.actor.x = 1150
        self.actor.y = FLOOR.top

    def show_saved(self):
        """Swap to the happy sprite once the artwork is available.

        Until images/bear_happy.png exists, the bear keeps its angry
        sprite and a green heart is drawn above it instead.
        """
        try:
            self.set_image(self.HAPPY_IMAGE)
            self.happy_sprite = True
        except KeyError:
            self.happy_sprite = False

    @property
    def x(self):
        return self.actor.x

    @x.setter
    def x(self, value):
        self.actor.x = value

    @property
    def y(self):
        return self.actor.y

    @property
    def bottom(self):
        return self.actor.y

    @property
    def box(self):
        return Rect((self.actor.x - self.BOX_WIDTH / 2,
                     self.actor.y - self.BOX_HEIGHT),
                    (self.BOX_WIDTH, self.BOX_HEIGHT))

    def update(self, dt, targets):
        if self.repaired:
            self.advance(self.direction * self.speed * 0.6 * dt)
            return
        self.update_brain(dt, targets)

    def draw(self):
        self.actor.draw()
        center_x = self.actor.x
        top = self.box.top
        if self.repaired:
            if not self.happy_sprite:
                screen.draw.rect(self.box, FRIENDLY_GREEN)
                screen.draw.text('<3', center=(center_x, top - 16),
                                 fontsize=26, color=FRIENDLY_GREEN)
        elif self.state == 'alert':
            screen.draw.text('!', center=(center_x, top - 22), fontsize=40,
                            color=(255, 80, 80))
        else:
            direction = self.direction
            screen.draw.line(
                (center_x - 6 * direction, top - 18),
                (center_x + 6 * direction, top - 12), GOLD)
            screen.draw.line(
                (center_x - 6 * direction, top - 6),
                (center_x + 6 * direction, top - 12), GOLD)


class Game:
    """Owns the world, the characters and the current state."""

    def __init__(self):
        self.mother = Mother('mom_idle', 70, MOTHER_SPEED, MOTHER_JUMP)
        self.child = Child('baby_idle', 70, CHILD_SPEED, 0.0)
        self.robot = Robot()
        self.bear = Bear()
        self.audio_on = True
        self.state = MENU
        self.reset_level()

    def reset_level(self):
        self.mother.reset()
        self.child.reset()
        self.robot.reset()
        self.bear.reset()
        self.carrying = True
        self.active = self.mother
        self.eye_taken = False
        self.intro_timer = INTRO_TIME
        self.mommy_timer = 0.0
        self.message = ''
        self.message_timer = 0.0
        self.prompt = ''
        self.killer = None
        self.mother.show_carrying(True)

    def start(self):
        self.reset_level()
        self.state = PLAYING

    def flash(self, message):
        self.message = message
        self.message_timer = 2.5

    def targets(self):
        """Characters an enemy can currently hit."""
        if self.carrying:
            return [self.mother]
        return [self.mother, self.child]

    def behind_bear(self, hero):
        """True when `hero` stands on the bear's blind side."""
        return (hero.x - self.bear.x) * self.bear.direction < 0

    def both_at_door(self):
        if self.carrying:
            return True
        return (abs(self.child.actor.x - DOOR.centerx) < 110
                and abs(self.mother.actor.x - DOOR.centerx) < 130)

    def solids_for(self, character):
        """The baby crawls through the tunnel; the mother cannot."""
        if character is self.child:
            return CHILD_SOLIDS
        return SOLIDS

    def update_playing(self, dt):
        move_direction = 0
        if keyboard.left or keyboard.a:
            move_direction = -1
        elif keyboard.right or keyboard.d:
            move_direction = 1

        if self.carrying:
            self.mother.update(dt, move_direction, SOLIDS)
        else:
            self.active.update(dt, move_direction,
                               self.solids_for(self.active))
            other = self.child if self.active is self.mother else self.mother
            other.update(dt, 0, self.solids_for(other))
            self.enforce_child_radius()
            self.try_take_eye()
            self.child.calling = self.mommy_timer > 0

        if (keyboard.up or keyboard.w) and self.active is self.mother \
                and self.active.on_ground:
            self.active.jump()

        targets = self.targets()
        self.robot.update(dt, targets)
        self.bear.update(dt, targets)

        deadly_enemies = [self.robot]
        if not self.bear.repaired:
            deadly_enemies.append(self.bear)
        for enemy in deadly_enemies:
            for target in targets:
                if enemy.touches(target):
                    self.state = LOSE
                    self.killer = enemy.killer_label
                    play_sound()
                    return

        if self.bear.repaired:
            self.try_use_exit()
        else:
            self.try_repair_bear()

        self.intro_timer = max(0.0, self.intro_timer - dt)
        self.mommy_timer = max(0.0, self.mommy_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)
        self.prompt = self.build_prompt()

    def enforce_child_radius(self):
        """Keep whoever is moving within CHILD_RADIUS of the other.

        The child stops and calls "Mommy!" at the limit; the mother
        cannot walk away and abandon the child either.
        """
        mover = self.active
        anchor = self.child if mover is self.mother else self.mother
        offset = mover.actor.x - anchor.actor.x
        if abs(offset) > CHILD_RADIUS:
            sign = 1 if offset > 0 else -1
            mover.actor.x = anchor.actor.x + CHILD_RADIUS * sign
            if self.mommy_timer <= 0:
                self.mommy_timer = MOMMY_TIME
                play_sound()

    def try_take_eye(self):
        """The child picks up the bear's eye automatically on contact."""
        if self.eye_taken:
            return
        offset_x = self.child.actor.x - EYE_POS[0]
        offset_y = self.child.actor.y - EYE_POS[1]
        if math.hypot(offset_x, offset_y) < 30:
            self.eye_taken = True
            play_sound()
            self.flash("You found the bear's eye!")

    def try_repair_bear(self):
        """The bear is repaired automatically when someone with the eye
        stands on its blind side while it is calm."""
        if not self.eye_taken or self.bear.state != 'patrol':
            return
        for character in self.targets():
            if (distance(character, self.bear) < 110
                    and self.behind_bear(character)):
                self.bear.repaired = True
                self.bear.show_saved()
                play_sound()
                self.flash('You saved the bear! The exit is open!')
                if character is self.mother and self.mother.carrying:
                    self.mother.flash_frame('mom_baby_sucess', 1.0)
                return

    def try_use_exit(self):
        """The escape happens automatically once both reach the open door."""
        hero = self.active
        if abs(hero.x - DOOR.centerx) < 90 and self.both_at_door():
            self.state = WIN
            play_sound()

    def build_prompt(self):
        hero = self.active
        hints = []
        if self.carrying:
            hints.append('E: put the child down')
        elif (hero is self.mother and self.child.on_ground
                and distance(self.mother, self.child) < CARRY_DISTANCE):
            hints.append('E: pick up the child')
        if (not self.bear.repaired
                and distance(hero, self.bear) < INTERACT_DISTANCE):
            if not self.eye_taken:
                hints.append('the bear lost its eye...')
            elif self.bear.state != 'patrol':
                hints.append('the bear is furious - stay clear!')
            elif not self.behind_bear(hero):
                hints.append("don't step in front of the bear!")
            else:
                hints.append('stand close behind the bear...')
        if abs(hero.x - DOOR.centerx) < 90:
            if not self.bear.repaired:
                hints.append('the exit is locked - repair the bear')
            elif not self.both_at_door():
                if hero is self.mother:
                    hints.append('bring the child to the exit!')
                else:
                    hints.append('bring the mother to the exit!')
        return '   |   '.join(hints)

    def switch_character(self):
        if self.carrying:
            self.flash('Put the child down first (E).')
        elif self.active is self.mother and not self.child.on_ground:
            self.flash('Wait for the child to land.')
        else:
            self.active = self.child if self.active is self.mother else self.mother

    def toggle_carry(self):
        if self.carrying:
            spot = self.find_drop_spot()
            if spot is None:
                self.flash('No safe spot to put the child down here!')
            else:
                self.carrying = False
                self.active = self.child
                self.child.actor.x = spot
                self.child.actor.y = self.mother.actor.y
                self.child.velocity_y = 0.0
                self.child.on_ground = True
                self.mother.show_carrying(False)
                self.mother.flash_frame('mom_topick_just_dropped')
                self.child.flash_frame('baby_just_dropped_picked')
                play_sound()
        elif (self.child.on_ground
                and distance(self.mother, self.child) < CARRY_DISTANCE):
            self.carrying = True
            self.active = self.mother
            self.mother.show_carrying(True)
            self.mother.flash_frame('mom_baby_todrop_just_picked')
            play_sound()
        else:
            self.flash('Stand next to the child to pick it up.')

    def find_drop_spot(self):
        """Find a spot right beside the mother to put the child down.

        Tries the side the mother is facing first, then the other
        side. The boxes end up touching with a tiny gap.
        """
        child_width = self.child.box_width
        for side in (self.mother.facing, -self.mother.facing):
            spot = (self.mother.actor.x
                    + side * (self.mother.box_width / 2
                              + child_width / 2 + 2))
            test = Rect(
                (spot - child_width / 2,
                 self.mother.actor.y - self.child.box_height),
                (child_width, self.child.box_height))
            # The baby falls through the tunnel block, so also make sure
            # the spot cannot drop into it from above.
            fall_path = Rect((spot - child_width / 2, self.mother.actor.y),
                             (child_width,
                              FLOOR.top - self.mother.actor.y))
            if test.left >= 0 and test.right <= WIDTH:
                if not any(test.colliderect(s) for s in SOLIDS):
                    if not fall_path.colliderect(TUNNEL):
                        return spot
        return None


game = Game()


# --- UI layout -----------------------------------------------------------

START_RECT = Rect((500, 300), (300, 62))
MENU_AUDIO_RECT = Rect((500, 382), (300, 62))
MENU_EXIT_RECT = Rect((500, 464), (300, 62))
RESUME_RECT = Rect((500, 280), (300, 62))
PAUSE_AUDIO_RECT = Rect((500, 362), (300, 62))
PAUSE_MENU_RECT = Rect((500, 444), (300, 62))
AGAIN_RECT = Rect((500, 340), (300, 62))
END_MENU_RECT = Rect((500, 422), (300, 62))


def toggle_audio():
    game.audio_on = not game.audio_on
    music.set_volume(1.0 if game.audio_on else 0.0)


def draw_background():
    """Draw the background once.

    An oversized background is anchored so that the BOTTOM of the art
    lines up with the bottom of the window - any floor artwork stays
    under the characters' feet. A background sized exactly 1300x708
    draws at (0, 0) with nothing cropped.
    """
    background = images.background
    x = (WIDTH - background.get_width()) // 2
    y = min(0, HEIGHT - background.get_height())
    screen.blit('background', (x, y))


def draw_button(rect, label):
    screen.draw.filled_rect(rect, BUTTON_FILL)
    screen.draw.rect(rect, INK)
    screen.draw.text(label, center=(rect.centerx, rect.centery), fontsize=26,
                     color=INK)


def audio_button_label(prefix):
    return prefix + 'Music & Sounds: ' + ('ON' if game.audio_on else 'OFF')


def draw_menu():
    draw_background()
    screen.draw.text('LOST IN TOYLAND', center=(WIDTH / 2, 120), fontsize=64,
                     color=GOLD)
    screen.draw.text(
        'Mother and child are lost in an abandoned Toyland.',
        center=(WIDTH / 2, 185), fontsize=22, color=INK)
    screen.draw.text(
        'Survive the wind-up robot, find the bear eye in the tunnel,',
        center=(WIDTH / 2, 212), fontsize=22, color=INK)
    screen.draw.text(
        'repair the bear and escape together!',
        center=(WIDTH / 2, 239), fontsize=22, color=INK)
    draw_button(START_RECT, 'Start Game')
    draw_button(MENU_AUDIO_RECT, audio_button_label(''))
    draw_button(MENU_EXIT_RECT, 'Exit')


def draw_pause_overlay():
    screen.draw.filled_rect(Rect((0, 0), (WIDTH, HEIGHT)), OVERLAY_COLOR)
    screen.draw.text('PAUSED', center=(WIDTH / 2, 200), fontsize=54,
                     color=GOLD)
    draw_button(RESUME_RECT, 'Resume')
    draw_button(PAUSE_AUDIO_RECT, audio_button_label(''))
    draw_button(PAUSE_MENU_RECT, 'Main Menu')


def draw_end_overlay(won):
    screen.draw.filled_rect(Rect((0, 0), (WIDTH, HEIGHT)), OVERLAY_COLOR)
    if won:
        screen.draw.text('TOYLAND SAVED!', center=(WIDTH / 2, 180),
                         fontsize=54, color=FRIENDLY_GREEN)
        screen.draw.text(
            'You saved the bear! Mother and child escape Toyland together.',
            center=(WIDTH / 2, 240), fontsize=24, color=INK)
    else:
        screen.draw.text('GAME OVER', center=(WIDTH / 2, 180), fontsize=54,
                         color=(255, 90, 90))
        if game.killer == 'robot':
            subtitle = 'A robot got you! Time your jump over its charge.'
        else:
            subtitle = 'A toy got you! Try to be sneakier.'
        screen.draw.text(subtitle, center=(WIDTH / 2, 240), fontsize=24,
                         color=INK)
    draw_button(AGAIN_RECT, 'Play Again' if won else 'Restart')
    draw_button(END_MENU_RECT, 'Main Menu')


def draw_level():
    draw_background()
    for platform in PLATFORMS:
        image = 'platform_long' if platform.width >= 130 else 'platform_short'
        screen.blit(image, platform.topleft)

    # The eye and the crawling baby are drawn first, then the
    # semi-transparent tunnel block is drawn over them, so you can see
    # both through the block.
    if not game.eye_taken:
        screen.draw.filled_circle(EYE_POS, 8, INK)
        screen.draw.filled_circle(EYE_POS, 3, (30, 30, 40))
    if not game.carrying:
        game.child.actor.draw()

    images.tunnel.set_alpha(TUNNEL_ALPHA)
    screen.blit('tunnel', TUNNEL.topleft)
    screen.draw.text('TUNNEL - child only', center=(TUNNEL.centerx,
                                                    TUNNEL.top - 14),
                     fontsize=18, color=INK)

    door_color = DOOR_OPEN if game.bear.repaired else DOOR_LOCKED
    screen.draw.filled_rect(DOOR, door_color)
    screen.draw.rect(DOOR, INK)
    screen.draw.filled_circle((DOOR.right - 10, DOOR.centery), 4, INK)
    screen.draw.text('EXIT', center=(DOOR.centerx, DOOR.top - 14), fontsize=18,
                     color=INK)

    game.robot.draw()
    game.bear.draw()

    game.mother.actor.draw()

    hero = game.active
    marker_x = hero.actor.x
    marker_y = hero.rect.top - 20
    screen.draw.line((marker_x - 7, marker_y - 8), (marker_x, marker_y),
                     (255, 230, 80))
    screen.draw.line((marker_x + 7, marker_y - 8), (marker_x, marker_y),
                     (255, 230, 80))


def draw_hud():
    active_name = 'Mother' if game.active is game.mother else 'Child'
    screen.draw.text('Active: ' + active_name, (12, 10), fontsize=22,
                     color=INK)
    eye_text = 'eye: found' if game.eye_taken else 'eye: missing'
    bear_text = 'bear: saved' if game.bear.repaired else 'bear: angry'
    exit_text = 'exit: open' if game.bear.repaired else 'exit: locked'
    screen.draw.text('{}  |  {}  |  {}'.format(eye_text, bear_text,
                                               exit_text),
                     (12, 38), fontsize=18, color=INK)
    if game.intro_timer > 0:
        screen.draw.text('SAVE THE TOYS', center=(WIDTH / 2, 62),
                         fontsize=44, color=GOLD)
        screen.draw.text(
            'Arrows/A D move   Up/W jump (mother)   E carry child   '
            'SPACE/TAB switch   ESC pause',
            center=(WIDTH / 2, 108), fontsize=20, color=INK)
    if game.message_timer > 0:
        screen.draw.text(game.message, center=(WIDTH / 2, 140), fontsize=26,
                         color=GOLD)
    if game.mommy_timer > 0:
        screen.draw.text('Mommy!!', center=(WIDTH / 2, 190), fontsize=54,
                         color=PINK)
    if game.prompt:
        screen.draw.text(game.prompt, center=(WIDTH / 2, HEIGHT - 26),
                         fontsize=22, color=INK)


def draw():
    if game.state == MENU:
        draw_menu()
        return
    draw_level()
    draw_hud()
    if game.state == PAUSED:
        draw_pause_overlay()
    elif game.state == WIN:
        draw_end_overlay(won=True)
    elif game.state == LOSE:
        draw_end_overlay(won=False)


def update(dt):
    if game.state == PLAYING:
        game.update_playing(dt)


def on_key_down(key):
    if key == keys.ESCAPE:
        if game.state == PLAYING:
            game.state = PAUSED
        elif game.state == PAUSED:
            game.state = PLAYING
        return
    if game.state != PLAYING:
        return
    if key == keys.TAB or key == keys.SPACE:
        game.switch_character()
    elif key == keys.E:
        game.toggle_carry()


def on_mouse_down(pos, button):
    if button != mouse.LEFT:
        return
    if game.state == MENU:
        if START_RECT.collidepoint(pos):
            game.start()
        elif MENU_AUDIO_RECT.collidepoint(pos):
            toggle_audio()
        elif MENU_EXIT_RECT.collidepoint(pos):
            exit()
    elif game.state == PAUSED:
        if RESUME_RECT.collidepoint(pos):
            game.state = PLAYING
        elif PAUSE_AUDIO_RECT.collidepoint(pos):
            toggle_audio()
        elif PAUSE_MENU_RECT.collidepoint(pos):
            game.state = MENU
    elif game.state == WIN or game.state == LOSE:
        if AGAIN_RECT.collidepoint(pos):
            game.start()
        elif END_MENU_RECT.collidepoint(pos):
            game.state = MENU


music.play('background_music')
