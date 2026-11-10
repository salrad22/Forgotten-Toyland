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
MOTHER_JUMP = -750

# Gameplay tuning
CHILD_RADIUS = 260          # max distance the child may stray from mother
CARRY_DISTANCE = 120        # how close mother must be to pick the child up
INTERACT_DISTANCE = 150     # range for repair / exit hints
INTRO_TIME = 6.0            # seconds the control banner stays visible
MOMMY_TIME = 1.4            # seconds the "Mommy!" call stays on screen
WALK_FRAME_TIME = 0.12      # seconds per walk-animation frame
CHARGE_FRAME_TIME = 0.06     # robot walk cycle while charging (fast)
POSE_TIME = 0.5             # seconds a one-off pose (pickup/drop) shows
THANKS_TIME = 2.0           # seconds the saved bear waves thanks
STEP_TIME = 0.25             # seconds between footstep sounds
TUNNEL_ALPHA = 160          # tunnel transparency: 0 = invisible, 255 = solid

# Level geometry
FLOOR = Rect((0, 660), (WIDTH, 48))
PLATFORMS = [
    # Raised above the 150px-tall robot's head so it walks under cleanly
    # (bottom at 500 vs robot head at 510) - the mother's bigger jump
    # (187px rise) still lands on the 180px climb.
    Rect((180, 480), (130, 20)),
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
INSTRUCTIONS = 'instructions'
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


def play_sound(name='eep'):
    """Play a sound effect if audio is enabled."""
    if game.audio_on:
        getattr(sounds, name).play()


SOUND_NAMES = ['eep', 'jump', 'steps', 'robot_noise', 'robot_attack',
               'bear_fixed', 'complete_level', 'when_losing']


def stop_all_sounds():
    """Stop any sound effect still playing.

    Long stingers (the defeat sting runs ~7 seconds) would otherwise
    keep playing over the menu music after leaving the end screens.
    """
    for name in SOUND_NAMES:
        getattr(sounds, name).stop()


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
        self.step_timer = 0.0
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
        self.step_timer = 0.0
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
        play_sound('jump')

    def _overlaps(self, solid):
        """Float-precise overlap test between the fixed box and `solid`."""
        left = self.actor.x - self.box_width / 2
        top = self.actor.y - self.box_height
        return (left < solid.right
                and left + self.box_width > solid.left
                and top < solid.bottom
                and top + self.box_height > solid.top)

    def update(self, dt, move_direction, solids):
        """Apply input, gravity and collisions with solids.

        The physics runs in fixed slices of at most 1/60 s: on a real
        machine a single slow frame (image loading, window hiccups)
        makes dt spike, which can move a falling character hundreds of
        pixels in one step - straight through the floor. Slicing keeps
        every collision step small.
        """
        elapsed = dt
        while dt > 0:
            step_time = min(dt, 1 / 60)
            dt -= step_time
            self._move_step(step_time, move_direction, solids)
        self.animate(elapsed, move_direction)

    def _move_step(self, dt, move_direction, solids):
        """One physics slice: input, gravity, collisions."""
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

    def animate(self, dt, move_direction):
        """Choose and apply the sprite frame for the current state."""
        if self.transition_timer > 0:
            self.transition_timer -= dt
            frame = self.transition_image
        elif not self.on_ground:
            frame = self.jump_image
        elif move_direction and self.on_ground:
            self.walk_animation.update(dt)
            frame = self.walk_animation.frame
            self.step_timer -= dt
            if self.step_timer <= 0:
                self.step_timer = STEP_TIME
                play_sound('steps')
        else:
            self.walk_animation.reset()
            self.step_timer = 0.0
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
            ['baby_carwl_1', 'baby_carwl_2', 'baby_carwl_3',
             'baby_carwl_4'],
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
    alert_sound = 'eep'       # played when the enemy spots a target
    attack_sound = None      # played when it starts charging

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
                    play_sound(self.alert_sound)
                    break
        elif self.state == 'alert':
            self.alert_timer -= dt
            if self.alert_timer <= 0:
                self.state = 'charge'
                if self.attack_sound:
                    play_sound(self.attack_sound)
        else:
            if self.advance(self.charge_direction * self.charge_speed * dt):
                self.state = 'patrol'


class Robot(Enemy):
    """The wind-up robot guarding the corridor before the tunnel."""

    killer_label = 'robot'
    alert_sound = 'robot_noise'
    attack_sound = 'robot_attack'
    BOX_WIDTH = 56
    BOX_HEIGHT = 72
    WALK_FRAMES = ['robot_walk_1', 'robot_walk_2',
                   'robot_walk_3', 'robot_walk_4']
    DANGER_IMAGE = 'robot_danger'
    IDLE_IMAGE = 'robot_idle'

    def __init__(self):
        super().__init__(33, 470, speed=40, charge_speed=300,
                         alert_time=0.9, detect_range=170)
        self.actor = Actor(self.IDLE_IMAGE, (360, FLOOR.top))
        self.walk_animation = Animation(self.WALK_FRAMES, WALK_FRAME_TIME)
        self.charge_animation = Animation(self.WALK_FRAMES,
                                          CHARGE_FRAME_TIME)
        self.reset()

    def set_image(self, image_name):
        """Swap sprite frames while keeping the robot's feet planted."""
        center_x = self.actor.x
        feet = self.actor.y
        self.actor.image = image_name
        self.actor.anchor = (self.actor.width / 2, self.actor.height)
        self.actor.x = center_x
        self.actor.y = feet

    def reset(self):
        super().reset()
        self.set_image(self.IDLE_IMAGE)
        self.actor.x = 360
        self.actor.y = FLOOR.top
        self.walk_animation.reset()
        self.charge_animation.reset()

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
        return FLOOR.top

    @property
    def box(self):
        return Rect((self.x - self.BOX_WIDTH / 2,
                     self.bottom - self.BOX_HEIGHT),
                    (self.BOX_WIDTH, self.BOX_HEIGHT))

    def update(self, dt, targets):
        self.update_brain(dt, targets)
        self.animate(dt)

    def animate(self, dt):
        """Pick the sprite frame for the current state.

        - patrol: walk cycle at normal pace
        - alert (mom spotted): danger pose
        - charge: the same walk cycle, twice as fast
        """
        if self.state == 'alert':
            self.walk_animation.reset()
            self.charge_animation.reset()
            frame = self.DANGER_IMAGE
        elif self.state == 'charge':
            self.charge_animation.update(dt)
            frame = self.charge_animation.frame
        else:
            self.walk_animation.update(dt)
            frame = self.walk_animation.frame
        if frame != self.actor.image:
            self.set_image(frame)

    def draw(self):
        if self.state == 'charge':
            facing = self.charge_direction
        else:
            facing = self.direction
        draw_sprite_feet_down(self.actor, flip=facing < 0)
        if self.state == 'alert':
            screen.draw.text('!',
                              center=(self.actor.x,
                                      self.actor.y - self.actor.height
                                      - 22),
                              fontsize=40, color=(255, 80, 80))


class Bear(Enemy):
    """The broken bear: attacks what it sees until it is saved."""

    killer_label = 'toy'
    BASE_IMAGE = 'angry_bear_idle'
    WALK_FRAMES = ['angry_bear_walk_1', 'angry_bear_walk_2',
                   'angry_bear_walk_3']
    DANGER_IMAGE = 'angry_bear_danger'
    HAPPY_IMAGE = 'bear_fixed'
    WAVE_IMAGE = 'bear_wave_thanks'
    BOX_WIDTH = 66
    BOX_HEIGHT = 99

    def __init__(self):
        super().__init__(1090, 1240, speed=50, charge_speed=230,
                         alert_time=0.7, detect_range=240)
        self.actor = Actor(self.BASE_IMAGE, (1150, FLOOR.top))
        self.walk_animation = Animation(self.WALK_FRAMES, WALK_FRAME_TIME)
        self.charge_animation = Animation(self.WALK_FRAMES,
                                          CHARGE_FRAME_TIME)
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
        self.thanks_timer = 0.0
        self.set_image(self.BASE_IMAGE)
        self.actor.x = 1150
        self.actor.y = FLOOR.top
        self.walk_animation.reset()
        self.charge_animation.reset()

    def show_saved(self):
        """Swap to the fixed sprite and briefly wave thanks.

        Until the saved-bear artwork exists, the bear keeps its angry
        sprite and a green heart is drawn above it instead.
        """
        try:
            self.set_image(self.HAPPY_IMAGE)
            self.happy_sprite = True
        except KeyError:
            # A failed load still leaves the image NAME set on the
            # actor, so point it back at the base sprite.
            self.set_image(self.BASE_IMAGE)
            self.happy_sprite = False
            return
        try:
            self.set_image(self.WAVE_IMAGE)
            self.thanks_timer = THANKS_TIME
        except KeyError:
            self.thanks_timer = 0.0

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
            # The saved bear stops walking and stands still, waving
            # thanks for a moment before settling into its fixed pose.
            if self.thanks_timer > 0:
                self.thanks_timer -= dt
                if self.thanks_timer <= 0:
                    self.set_image(self.HAPPY_IMAGE)
            return
        self.update_brain(dt, targets)
        self.animate(dt)

    def animate(self, dt):
        """Pick the sprite frame for the current state.

        - patrol: walk cycle at normal pace
        - alert (player spotted): danger pose
        - charge: the same walk cycle, twice as fast
        """
        if self.state == 'alert':
            self.walk_animation.reset()
            self.charge_animation.reset()
            frame = self.DANGER_IMAGE
        elif self.state == 'charge':
            self.charge_animation.update(dt)
            frame = self.charge_animation.frame
        else:
            self.walk_animation.update(dt)
            frame = self.walk_animation.frame
        if frame != self.actor.image:
            self.set_image(frame)

    def draw(self):
        if self.state == 'charge':
            facing = self.charge_direction
        else:
            facing = self.direction
        draw_sprite_feet_down(self.actor, flip=facing < 0)
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
        stop_all_sounds()
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
                    play_sound('when_losing')
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
                play_sound('bear_fixed')
                self.flash('You saved the bear! The exit is open!')
                if character is self.mother and self.mother.carrying:
                    self.mother.flash_frame('mom_baby_victory', THANKS_TIME)
                return

    def try_use_exit(self):
        """The escape happens automatically once both reach the open door."""
        hero = self.active
        if abs(hero.x - DOOR.centerx) < 90 and self.both_at_door():
            self.state = WIN
            play_sound('complete_level')

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

START_RECT = Rect((500, 270), (300, 62))
INSTRUCTIONS_RECT = Rect((500, 352), (300, 62))
MENU_AUDIO_RECT = Rect((500, 434), (300, 62))
MENU_EXIT_RECT = Rect((500, 516), (300, 62))
BACK_RECT = Rect((500, 600), (300, 62))
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


_MIRRORED = {}


def mirrored(surface):
    """A horizontally flipped copy of a sprite (cached per surface).

    pgzero 1.2.1 has no sprite-flipping API, so the mirror is built by
    blitting 1-pixel vertical strips right-to-left - once per image.
    The canvas is cleared to fully transparent first: blitting the
    strips onto a copy of the original artwork would leave the
    original showing through every transparent gap, producing a
    doubled 'ghost' sprite.
    """
    key = id(surface)
    if key not in _MIRRORED:
        width = surface.get_width()
        height = surface.get_height()
        canvas = surface.copy()
        canvas.fill((0, 0, 0, 0))
        for column in range(width):
            strip = surface.subsurface((width - 1 - column, 0, 1, height))
            canvas.blit(strip, (column, 0))
        _MIRRORED[key] = canvas
    return _MIRRORED[key]


def draw_sprite_feet_down(actor, flip=False):
    """Draw a character sprite with its feet at actor.y, centred on
    actor.x, using explicit coordinates.

    Actor.draw()/anchor semantics differ between pgzero versions, so
    characters are positioned manually - this works everywhere.
    Draws the actor's already-loaded surface (not the image name, which
    could point at an image that failed to load). Set flip=True to
    mirror the sprite horizontally (e.g. to face left).
    """
    surface = getattr(actor, '_surf', None)
    if surface is None:
        surface = actor.image
    if flip:
        surface = mirrored(surface)
    screen.blit(surface, (actor.x - actor.width / 2,
                          actor.y - actor.height))


def draw_button(rect, label):
    screen.draw.filled_rect(rect, BUTTON_FILL)
    screen.draw.rect(rect, INK)
    screen.draw.text(label, center=(rect.centerx, rect.centery), fontsize=26,
                     color=INK)


def audio_button_label(prefix):
    return prefix + 'Music & Sounds: ' + ('ON' if game.audio_on else 'OFF')


def draw_menu():
    draw_background()
    screen.draw.text('LOST IN TOYLAND', center=(WIDTH / 2, 160), fontsize=64,
                     color=GOLD)
    screen.draw.text(
        'Even the angriest toys might just need a little help...',
        center=(WIDTH / 2, 210), fontsize=24, color=INK)
    draw_button(START_RECT, 'Start Game')
    draw_button(INSTRUCTIONS_RECT, 'Instructions')
    draw_button(MENU_AUDIO_RECT, audio_button_label(''))
    draw_button(MENU_EXIT_RECT, 'Exit')


def draw_instructions():
    """The instructions screen - written as a mysterious note, with
    hints rather than spoilers."""
    draw_background()
    screen.draw.text('AN OLD NOTE, FOUND IN TOYLAND',
                     center=(WIDTH / 2, 85), fontsize=40, color=GOLD)

    left = 250
    y = 155
    for line in [
        'The toys of Toyland look angry...',
        '...but angry things are sometimes just',
        'things that need help.',
        '',
        'Be careful of the metal guards - when',
        'one winds up, get out of its way.',
        '',
        'Something small was lost in the dark.',
        'Only the littlest traveler can crawl',
        'where the big cannot... but do not let',
        'it stray too far from its mother.',
        '',
        'The broken one cannot see behind',
        'itself. Approach with kindness.',
        '',
        'And the great door? It opens only for',
        'two who leave together.',
    ]:
        screen.draw.text(line, (left, y), fontsize=20, color=INK)
        y += 25

    right = 800
    screen.draw.text('CONTROLS', (right, 155), fontsize=26, color=GOLD)
    y = 195
    for keys_text, action in [
        ('Left / Right or A / D', 'move'),
        ('Up or W', 'jump (mother only)'),
        ('E', 'pick up / put down child'),
        ('SPACE or TAB', 'switch character'),
        ('ESC', 'pause'),
        ('Mouse', 'all menu buttons'),
    ]:
        screen.draw.text(keys_text, (right, y), fontsize=20, color=INK)
        screen.draw.text(action, (right + 175, y), fontsize=20, color=GOLD)
        y += 34

    draw_button(BACK_RECT, 'Back')


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
        draw_sprite_feet_down(game.child.actor)

    images.tunnel.set_alpha(TUNNEL_ALPHA)
    screen.blit('tunnel', TUNNEL.topleft)

    door_color = DOOR_OPEN if game.bear.repaired else DOOR_LOCKED
    screen.draw.filled_rect(DOOR, door_color)
    screen.draw.rect(DOOR, INK)
    screen.draw.filled_circle((DOOR.right - 10, DOOR.centery), 4, INK)
    screen.draw.text('EXIT', center=(DOOR.centerx, DOOR.top - 14), fontsize=18,
                     color=INK)

    game.robot.draw()
    game.bear.draw()

    draw_sprite_feet_down(game.mother.actor)

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
    if game.state == INSTRUCTIONS:
        draw_instructions()
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
    # Clamp huge frames (first-frames image loading, dragging the
    # window, machine hiccups): without this a dt spike teleports
    # falling characters through the floor in a single step.
    dt = min(dt, 0.1)
    if game.state == PLAYING:
        game.update_playing(dt)


def on_key_down(key):
    if key == keys.ESCAPE:
        if game.state == PLAYING:
            game.state = PAUSED
        elif game.state == PAUSED:
            game.state = PLAYING
        elif game.state == INSTRUCTIONS:
            game.state = MENU
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
        elif INSTRUCTIONS_RECT.collidepoint(pos):
            game.state = INSTRUCTIONS
        elif MENU_AUDIO_RECT.collidepoint(pos):
            toggle_audio()
        elif MENU_EXIT_RECT.collidepoint(pos):
            exit()
    elif game.state == INSTRUCTIONS:
        if BACK_RECT.collidepoint(pos):
            game.state = MENU
    elif game.state == PAUSED:
        if RESUME_RECT.collidepoint(pos):
            game.state = PLAYING
        elif PAUSE_AUDIO_RECT.collidepoint(pos):
            toggle_audio()
        elif PAUSE_MENU_RECT.collidepoint(pos):
            stop_all_sounds()
            game.state = MENU
    elif game.state == WIN or game.state == LOSE:
        if AGAIN_RECT.collidepoint(pos):
            game.start()
        elif END_MENU_RECT.collidepoint(pos):
            stop_all_sounds()
            game.state = MENU


# The main theme loops on the dedicated music channel; the menu's
# Music & Sounds button controls its volume (music.set_volume), so the
# toggle always governs this track no matter where it's clicked.
music.play('menu_and_game_music')
music.set_volume(1.0)
