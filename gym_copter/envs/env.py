'''
gym-copter Environment superclass

Copyright (C) 2019 Simon D. Levy

MIT License
'''

from gym import Env
import numpy as np
from time import time

from gym_copter.dynamics.djiphantom import DJIPhantomDynamics

class CopterEnv(Env):

    metadata = {
        'render.modes' : ['human', 'rgb_array'],
        'video.frames_per_second' : 30
    }

    def __init__(self, dt=0.001, disp='hud'):

        self.num_envs = 1
        self.display = None

        # We handle time differently if we're rendering
        self.dt = dt

        # Default to HUD display
        self.disp = disp

        self._init()

    def _update(self, action):

        # Update dynamics and get kinematic state
        self.dynamics.setMotors(action)
        self.dynamics.update(self.dt)
        self.state = self.dynamics.getState()

        # Accumulate time
        self.t += self.dt

    def reset(self):

        self._init()
        return self.state

    def render(self, mode='human'):

        # Track time
        tcurr = time()
        self.dt = (tcurr - self.tprev) if self.tprev > 0 else self.dt
        self.tprev = tcurr

        # Support different display types
        return self._render_tpv(mode) if self.disp == 'tpv' else self._render_hud(mode)

    def close(self):

        Env.close(self)        

    def time(self):

        return self.t

    def _init(self):
        
        self.state = np.zeros(12)
        self.dynamics = DJIPhantomDynamics()
        self.tprev = 0
        self.t = 0

    def _render_hud(self, mode):
        
        from gym_copter.envs.rendering.hud import HUD

        if self.display is None:
            self.display = HUD()
 
        # Detect window close
        if not self.display.isOpen(): return None

        return self.display.display(mode, self.state)

    def _render_tpv(self, mode):
        
        from gym_copter.envs.rendering.tpv import TPV

        if self.display is None:
            self.display = TPV()
 
        # Detect window close
        if not self.display.isOpen(): return None

        return self.display.display(mode, self.state)
