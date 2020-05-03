"""
Adapted from https://raw.githubusercontent.com/openai/gym/master/gym/envs/box2d/lunar_lander.py

The landing pad is always at coordinates (0,0). The coordinates are the first two numbers in the state vector.
Reward for moving from the top of the screen to the landing pad and zero speed is about 100..140 points.
If the copter moves away from the landing pad it loses reward. The episode finishes if the copter crashes or
comes to rest, receiving an additional -100 or +100 points.  Firing the main
engine is -0.3 points each frame. Firing the side engine is -0.03 points each
frame.  Solved is 200 points.

Landing outside the landing pad is possible. Fuel is infinite, so an agent can learn to fly and then land
on its first attempt. Please see the source code for details.

To see a heuristic landing, run:

python gym_copter/envs/lander.py
"""

import numpy as np

import Box2D
from Box2D.b2 import edgeShape, fixtureDef, polygonShape, contactListener

import gym
from gym import spaces
from gym.utils import seeding

from gym_copter.dynamics.djiphantom import DJIPhantomDynamics

START_X = 10
START_Y = 13

MAX_LANDING_SPEED = 0.05

GROUND_COUNT_MAX = 15

FPS = 50
SCALE = 30.0   # affects how fast-paced the game is, forces should be adjusted as well

LEG_X  = 12
LEG_Y  = -7
LEG_W  = 3
LEG_H  = 20

MOTOR_X  = 25
MOTOR_Y  = 7
MOTOR_W  = 4
MOTOR_H  = 5

BLADE_X = 25
BLADE_Y = 8
BLADE_W = 20
BLADE_H = 2

BLADE1L_POLY = [
        (BLADE_X,BLADE_Y),
        (BLADE_X-BLADE_W/2,BLADE_Y+BLADE_H),
        (BLADE_X-BLADE_W,BLADE_Y),
        (BLADE_X-BLADE_W/2,BLADE_Y+-BLADE_H),
        ]

BLADE1R_POLY = [
        (BLADE_X,BLADE_Y),
        (BLADE_X+BLADE_W/2,BLADE_Y+BLADE_H),
        (BLADE_X+BLADE_W,BLADE_Y),
        (BLADE_X+BLADE_W/2,BLADE_Y+-BLADE_H),
        ]

BLADE2L_POLY = [
        (-BLADE_X,BLADE_Y),
        (-(BLADE_X+BLADE_W/2),BLADE_Y+BLADE_H),
        (-(BLADE_X+BLADE_W),BLADE_Y),
        (-(BLADE_X+BLADE_W/2),BLADE_Y+-BLADE_H),
        ]

BLADE2R_POLY = [
        (-BLADE_X,BLADE_Y),
        (-BLADE_X+BLADE_W/2,BLADE_Y+BLADE_H),
        (-BLADE_X+BLADE_W,BLADE_Y),
        (-BLADE_X+BLADE_W/2,BLADE_Y+-BLADE_H),
        ]

HULL_POLY =[
        (-30, 0),
        (-4, +4),
        (+4, +4),
        (+30,  0),
        (+4, -14),
        (-4, -14),
    ]

LEG1_POLY = [
        (-LEG_X,LEG_Y),
        (-LEG_X+LEG_W,LEG_Y),
        (-LEG_X+LEG_W,LEG_Y-LEG_H),
        (-LEG_X,LEG_Y-LEG_H)
    ]

LEG2_POLY = [
        (+LEG_X,LEG_Y),
        (+LEG_X+LEG_W,LEG_Y),
        (+LEG_X+LEG_W,LEG_Y-LEG_H),
        (+LEG_X,LEG_Y-LEG_H)
    ]

MOTOR1_POLY = [
        (+MOTOR_X,MOTOR_Y),
        (+MOTOR_X+MOTOR_W,MOTOR_Y),
        (+MOTOR_X+MOTOR_W,MOTOR_Y-MOTOR_H),
        (+MOTOR_X,MOTOR_Y-MOTOR_H)
    ]

MOTOR2_POLY = [
        (-MOTOR_X,MOTOR_Y),
        (-MOTOR_X+MOTOR_W,MOTOR_Y),
        (-MOTOR_X+MOTOR_W,MOTOR_Y-MOTOR_H),
        (-MOTOR_X,MOTOR_Y-MOTOR_H)
    ]


VIEWPORT_W = 600
VIEWPORT_H = 400

SKY_COLOR     = 0.5, 0.8, 1.0
GROUND_COLOR  = 0.5, 0.7, 0.3
FLAG_COLOR    = 0.8, 0.0, 0.0
VEHICLE_COLOR = 1.0, 1.0, 1.0
MOTOR_COLOR   = 0.5, 0.5, 0.5
PROP_COLOR    = 0.0, 0.0, 0.0
OUTLINE_COLOR = 0.0, 0.0, 0.0

class ContactDetector(contactListener):
    def __init__(self, env):
        contactListener.__init__(self)
        self.env = env

    def BeginContact(self, contact):
        if self.env.lander == contact.fixtureA.body or self.env.lander == contact.fixtureB.body:
            self.env.landed = True

class CopterLander1D(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : FPS
    }

    def __init__(self):
        self.seed()
        self.viewer = None

        self.world = Box2D.b2World()
        self.ground = None
        self.lander = None

        self.prev_reward = None

        # useful range is -1 .. +1, but spikes can be higher
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(6,), dtype=np.float32)

        # Action is two floats [throttle_demand, roll_demand]
        self.action_space = spaces.Box(-1, +1, (1,), dtype=np.float32)

        self.reset()

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def _destroy(self):
        if not self.ground: return
        self.world.contactListener = None
        self.world.DestroyBody(self.ground)
        self.ground = None
        self.world.DestroyBody(self.lander)
        self.lander = None

    def reset(self, yoff=0):
        self._destroy()
        self.world.contactListener_keepref = ContactDetector(self)
        self.world.contactListener = self.world.contactListener_keepref
        self.landed = False
        self.prev_shaping = None
        self.rendering = False

        W = VIEWPORT_W/SCALE
        H = VIEWPORT_H/SCALE

        # Turn off gravity so we can run our own dynamics
        self.world.gravity = 0,0

        # terrain
        CHUNKS = 11
        height = self.np_random.uniform(0, H/2, size=(CHUNKS+1,))
        chunk_x = [W/(CHUNKS-1)*i for i in range(CHUNKS)]
        self.helipad_x1 = chunk_x[CHUNKS//2-1]
        self.helipad_x2 = chunk_x[CHUNKS//2+1]
        self.helipad_y = H/4
        height[CHUNKS//2-2] = self.helipad_y
        height[CHUNKS//2-1] = self.helipad_y
        height[CHUNKS//2+0] = self.helipad_y
        height[CHUNKS//2+1] = self.helipad_y
        height[CHUNKS//2+2] = self.helipad_y
        smooth_y = [0.33*(height[i-1] + height[i+0] + height[i+1]) for i in range(CHUNKS)]

        self.ground = self.world.CreateStaticBody(shapes=edgeShape(vertices=[(0, 0), (W, 0)]))
        self.sky_polys = []
        for i in range(CHUNKS-1):
            p1 = (chunk_x[i], smooth_y[i])
            p2 = (chunk_x[i+1], smooth_y[i+1])
            self.ground.CreateEdgeFixture(
                vertices=[p1,p2],
                density=0,
                friction=0.1)
            self.sky_polys.append([p1, p2, (p2[0], H), (p1[0], H)])

        initial_y = VIEWPORT_H/SCALE

        self.lander = self.world.CreateDynamicBody(
                position=(VIEWPORT_W/SCALE/2, initial_y),
                angle=0.0,

                fixtures = [
                    fixtureDef(shape=polygonShape(vertices=[(x/SCALE, y/SCALE) for x, y in poly]), density=1.0)
                    for poly in [HULL_POLY, LEG1_POLY, LEG2_POLY, MOTOR1_POLY, MOTOR2_POLY,
                        BLADE1L_POLY, BLADE1R_POLY, BLADE2L_POLY, BLADE2R_POLY]
                    ]
               ) 

        self.dynamics = DJIPhantomDynamics()

        # Start at top center, plus optional offset
        state = np.zeros(12)
        state[self.dynamics.STATE_Y] =  START_X
        state[self.dynamics.STATE_Z] = -(START_Y + yoff)  # 3D copter Z comes from 2D copter Y

        self.dynamics.setState(state)

        # By showing props periodically, we can emulate prop rotation
        self.show_props = 0

        # Support showing vehicle while on ground
        self.ground_count = 0

        return self.step(np.array([0, 0]))[0]

    def step(self, action):
        '''
        action[0] = throttle demand
        '''

        # Rescale [-1,+1] => [0,1]
        action[0] = (action[0] + 1) / 2 

        # A simple mixer
        motors = [action[0]]*4

        # Set motors and compute dynamics
        self.dynamics.setMotors(motors)
        self.dynamics.update(1.0/FPS)
        state = self.dynamics.getState()

        # Run one tick of Box2D simulator
        self.world.Step(1.0/FPS, 6*30, 2*30)

        # Copy dynamics kinematics out to lander, negating Z for NED => ENU
        dyn = self.dynamics
        self.lander.position        =  state[dyn.STATE_Y], -state[dyn.STATE_Z]
        self.lander.angle           = -state[dyn.STATE_PHI]
        self.lander.angularVelocity = -state[dyn.STATE_PHI_DOT]
        self.lander.linearVelocity  = (state[dyn.STATE_Y_DOT], -state[dyn.STATE_Z_DOT])

        pos = self.lander.position
        vel = self.lander.linearVelocity

        state = [
                (pos.x - VIEWPORT_W/SCALE/2) / (VIEWPORT_W/SCALE/2),
                (pos.y- (self.helipad_y+LEG_H/SCALE)) / (VIEWPORT_H/SCALE/2),
                vel.x*(VIEWPORT_W/SCALE/2)/FPS,
                vel.y*(VIEWPORT_H/SCALE/2)/FPS,
                self.lander.angle,
                20*self.lander.angularVelocity/FPS
                ]

        reward = 0

        shaping = - 100*np.sqrt(state[1]**2) - 100*np.sqrt(state[3]**2) 

        if self.prev_shaping is not None:
            reward = shaping - self.prev_shaping
        self.prev_shaping = shaping

        done = False

        # If we've landed, we're done, with extra reward for a soft landing
        if self.landed:
            if self.ground_count == 0:
                reward += 100 * (abs(state[3]) < MAX_LANDING_SPEED)
            else:
                if not self.rendering or self.ground_count == GROUND_COUNT_MAX:
                    done = True
            self.ground_count += 1

        return np.array(state, dtype=np.float32), reward, done, {}

    def render(self, mode='human'):

        from gym.envs.classic_control import rendering

        # Helps with a little extra time at the end
        self.rendering = True

        if self.viewer is None:
            self.viewer = rendering.Viewer(VIEWPORT_W, VIEWPORT_H)
            self.viewer.set_bounds(0, VIEWPORT_W/SCALE, 0, VIEWPORT_H/SCALE)

        self.viewer.draw_polygon([(0,0), (VIEWPORT_W,0), (VIEWPORT_W,VIEWPORT_H), (0,VIEWPORT_H)], color=GROUND_COLOR)

        for p in self.sky_polys:
            self.viewer.draw_polygon(p, color=SKY_COLOR)

        self._show_fixture(1, VEHICLE_COLOR)
        self._show_fixture(2, VEHICLE_COLOR)
        self._show_fixture(0, VEHICLE_COLOR)
        self._show_fixture(3, MOTOR_COLOR)
        self._show_fixture(4, MOTOR_COLOR)

        # Simulate spinning props by alernating
        if self.landed or self.show_props:
            for k in range(5,9):
                self._show_fixture(k, PROP_COLOR)

        for x in [self.helipad_x1, self.helipad_x2]:
            flagy1 = self.helipad_y
            flagy2 = flagy1 + 50/SCALE
            self.viewer.draw_polyline([(x, flagy1), (x, flagy2)], color=(1, 1, 1))
            self.viewer.draw_polygon([(x, flagy2), (x, flagy2-10/SCALE), (x + 25/SCALE, flagy2 - 5/SCALE)],
                                     color=FLAG_COLOR)

        self.show_props = (self.show_props + 1) % 3

        return self.viewer.render(return_rgb_array=mode == 'rgb_array')

    def close(self):
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None

    def _show_fixture(self, index, color):
        fixture = self.lander.fixtures[index]
        trans = fixture.body.transform
        path = [trans*v for v in fixture.shape.vertices]
        self.viewer.draw_polygon(path, color=color)
        path.append(path[0])
        self.viewer.draw_polyline(path, color=OUTLINE_COLOR, linewidth=1)
