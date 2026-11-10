LOST IN TOYLAND
================

A side-view platformer written in Python with Pygame Zero.

Story
-----
A mother carries her child into an abandoned Toyland. To find the way
out they must survive a wind-up robot, crawl through a tiny tunnel to
recover a bear's missing eye, save the angry bear by sneaking up on
its blind side, and reach the exit door together.

Objective
---------
- Survive the wind-up robot that patrols the first corridor.
- Switch to the child and send it into the tunnel (only the child is
  small enough to fit) to take the bear's eye.
- Save the bear by standing right behind it while it is calm - the
  bear attacks anything it can see.
- Lead BOTH the mother and the child to the exit door (carrying the
  child counts) to win.

Libraries used
--------------
- Pygame Zero (the only third-party library)
- Python standard module: math
No other imports are used (no time / os / sys, no pygame import).

Installation & launch
---------------------
1. Install Python 3.8 or newer.
2. Install Pygame Zero:
       pip install pgzero
3. From the project folder run:
       pgzrun game.py

Controls
-------
- Left / Right arrows (or A / D) ... move the active character
- Up arrow or W .................. jump (ONLY the mother can jump)
- E .............................. pick up / put down the child
                                     (mother only, stand close,
                                     child must be on the ground;
                                     when the child is put down,
                                     control passes to it
                                     automatically)
- SPACE or TAB ................... switch between mother and child
                                     (only while the child is grounded)
- ESC ............................ pause / resume
- Mouse .......................... all menu buttons

There is no interact key: everything happens automatically -
- the child picks up the bear's eye by walking into it,
- the bear is saved when someone carrying the eye stands right
  behind it while it is calm,
- mother and child escape as soon as they both reach the open exit.

Game rules
----------
- The child cannot wander further than a short radius from the mother;
  when it hits the limit it stops and calls "Mommy!".
- The tunnel block is solid for the mother - she can jump over it (or
  cross on the platform bridge). The baby cannot jump, so it crawls
  right through the tunnel instead (the block is semi-transparent, so
  you can watch it inside and see the hidden eye).
- The baby cannot be dropped onto the top of the tunnel block.
- The mother can jump. The child cannot - it crawls along the ground
  and through the tunnel.
- Touching the robot, or being caught by the angry bear, means game
  over - use Restart or Main Menu on the game over screen.
- The bear can only be saved with the eye, approached from behind,
  while it is calmly patrolling.
- The exit stays locked until the bear is saved.

Design decision (per checklist): the child does NOT have to be carried
when approaching the bear, but BOTH characters must be at the exit
(being carried counts as being there).

Menu
----
- Start Game - begins a new level
- Music & Sounds: ON/OFF - mutes/unmutes both background music and
  sound effects (the setting is kept between games)
- Exit - closes the game

Assets & attribution
--------------------
- images/mom_*.png, images/baby_*.png (the mother, the child she
  carries, and their animation frames), images/robot_*.png,
  images/platform_*.png and images/tunnel.png are original artwork
  created by the project author for this game.
- images/bear.png, images/background.png, music/background_music.ogg
  and sounds/eep.wav were included with the project starter pack
  (Kodland course assets).
- The wind-up robot, the bear's eye and the exit door are drawn with
  plain colored rectangles as placeholder art; the single "eep" sound
  is reused (rate-limited) as a placeholder for alerts, calls,
  pickups and repairs until final artwork and audio are added.
