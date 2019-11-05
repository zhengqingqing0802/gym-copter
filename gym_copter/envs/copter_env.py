'''
Copyright (C) 2019 Simon D. Levy

MIT License
'''

import gym
from gym import spaces
import numpy as np

from gym_copter.dynamics.quadxap import QuadXAPDynamics
from gym_copter.dynamics import Parameters

class CopterEnv(gym.Env):

    metadata = {'render.modes': ['human']}

    def __init__(self, dt=.001):

        params = Parameters(

        # Estimated
        5.E-06, # b
        2.E-06, # d

        # https:#www.dji.com/phantom-4/info
        1.380,  # m (kg)
        0.350,  # l (meters)

        # Estimated
        2,      # Ix
        2,      # Iy
        3,      # Iz
        38E-04, # Jr
        15000)  # maxrpm

        self.action_space = spaces.Box( np.array([0,0,0,0]), np.array([1,1,1,1]))  # motors

        self.dt = dt

        self.copter = QuadXAPDynamics(params)

        self.viewer = None

    def step(self, action):

        self.copter.setMotors(action)

        self.copter.update(self.dt)

        # an environment-specific object representing your observation of the environment
        obs = self.copter.getState()

        reward       = 0.0   # floating-point reward value from previous action
        episode_over = False # whether it's time to reset the environment again (e.g., pole tipped over)
        info         = {}    # diagnostic info for debugging

        self.copter.update(self.dt)

        return obs, reward, episode_over, info

    def reset(self):
        pass

    def render(self, mode='human'):

        # Adapted from https://raw.githubusercontent.com/openai/gym/master/gym/envs/classic_control/cartpole.py

        screen_width = 600
        screen_height = 400
        cartwidth = 50.0
        cartheight = 30.0

        if self.viewer is None:
            from gym.envs.classic_control import rendering
            self.viewer = rendering.Viewer(screen_width, screen_height)
            l,r,t,b = -cartwidth/2, cartwidth/2, cartheight/2, -cartheight/2
            axleoffset =cartheight/4.0
            cart = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
            self.carttrans = rendering.Transform()
            cart.add_attr(self.carttrans)
            self.viewer.add_geom(cart)

        return self.viewer.render(return_rgb_array = mode=='rgb_array')


    def close(self):
        pass
