'''
Copyright (C) 2019 Simon D. Levy

MIT License
'''

import gym
from gym import spaces
import numpy as np

import pyglet

from gym_copter.dynamics.phantom import DJIPhantomDynamics

from sys import stdout

class CopterEnv(gym.Env):

    metadata = {'render.modes': ['human']}

    def __init__(self, dt=.001):

        self.action_space = spaces.Box(np.array([0,0,0,0]), np.array([1,1,1,1]))  # motors
        self.dt = dt
        self.dynamics = DJIPhantomDynamics()
        self.viewer = None
        self.heading_widgets = []

    def step(self, action):

        self.dynamics.setMotors(action)
        self.dynamics.update(self.dt)

        # an environment-specific object representing your observation of the environment
        obs = self.dynamics.getState()

        reward       = 0.0   # floating-point reward value from previous action
        episode_over = False # whether it's time to reset the environment again (e.g., circle tipped over)
        info         = {}    # diagnostic info for debugging

        self.dynamics.update(self.dt)

        return obs, reward, episode_over, info

    def reset(self):
        pass

    def render(self, mode='human'):

        # Arbitrary constants
        W                       = 800 # window width
        H                       = 600 # window height
        SKY_COLOR               = 0.5, 0.8, 1.0
        GROUND_COLOR            = 0.5, 0.7, 0.3
        LINE_COLOR              = 1.0, 1.0, 1.0
        HIGHLIGHT_COLOR         = 0.5, 0.5, 0.5
        POINTER_COLOR           = 1.0, 0.0, 0.0
        HEADING_TICK_SPACING    = 80
        HEADING_TICK_COUNT      = 24
        HEADING_LABEL_Y_OFFSET  = 17
        HEADING_LINE_Y_OFFSET   = 35
        HEADING_BOX_WIDTH       = 20
        FONT_SIZE               = 18
        FONT_COLOR              = 255,255,255
        PITCH_LINE_SPACING      = 40
        PITCH_LINE_WIDTH        = 30
        PITCH_LABEL_X_OFFSET    = 40
        PITCH_LABEL_Y_OFFSET    = 0
        VERTICAL_BOX_HEIGHT     = 300
        VERTICAL_BOX_WIDTH      = 90
        VERTICAL_LABEL_OFFSET   = 30
        VERTICAL_POINTER_HEIGHT = 15
        VERTICAL_STEP_METERS    = 5
        VERTICAL_STEP_PIXELS    = 8
        ROLL_RETICLE_RADIUS     = 300
        ROLL_RETICLE_LIM        = 45
        ROLL_RETICLE_PTS        = 100
        ROLL_RETICLE_YOFF       = 200
        ROLL_RETICLE_STRIDE     = 10
        ROLL_RETICLE_TICKLEN    = 5
        ROLL_RETICLE_TICK_YOFF  = 25
        ROLL_RETICLE_TICKVALS   = [10, 20, 30, 45, 60]
        ROLL_POINTER_SIZE       = 10
 
        from gym.envs.classic_control import rendering
        from pyglet.gl import glTranslatef, glLoadIdentity, glRotatef

        # https://stackoverflow.com/questions/56744840/pyglet-label-not-showing-on-screen-on-draw-with-openai-gym-render

        class _DrawText:
            def __init__(self, label:pyglet.text.Label):
                self.label=label
            def render(self):
                self.label.draw()

        class _DrawTextRotated:
            def __init__(self, label:pyglet.text.Label, x, y, phi, xoff=0):
                self.label=label
                self.x = x
                self.y = y
                self.phi = phi
                self.xoff = xoff
            def render(self):
                glTranslatef(self.x, self.y, 0)
                glRotatef(np.degrees(self.phi), 0.0, 0.0, 1.0)
                glTranslatef(self.xoff, 0, 0)
                self.label.draw()
                glLoadIdentity() # Restores ordinary drawing

        def _rotate(x, y, phi):
            return np.cos(phi)*x - np.sin(phi)*y, np.sin(phi)*x + np.cos(phi)*y

        def _tickval2index(tickval):
            return int((ROLL_RETICLE_PTS-1) * (tickval-tickvals[0]) / (tickvals[-1]-tickvals[0]))

        def _vertical_display(viewer, leftx, stripx, value):

            dy = VERTICAL_POINTER_HEIGHT

            # Display a tapered strip in the middle for highlighting current value
            stripw = VERTICAL_BOX_WIDTH + dy
            x1,y1 = stripx,0+H/2
            x2,y2 = stripx+dy,dy+H/2
            x3,y3 = stripx+stripw-dy, dy+H/2
            x4,y4 = stripx+stripw, 0+H/2
            x5,y5 = stripx+stripw-dy, -dy+H/2
            x6,y6 = stripx+dy,-dy+H/2
            viewer.draw_polygon([(x1,y1),(x2,y2),(x3,y3),(x4,y4),(x5,y5),(x6,y6)], color=HIGHLIGHT_COLOR)

            # Display a box for the gauge
            l = leftx
            r = l + VERTICAL_BOX_WIDTH
            b = H/2 - VERTICAL_BOX_HEIGHT/2
            t = H/2 + VERTICAL_BOX_HEIGHT/2
            viewer.draw_polygon([(l,t),(r,t),(r,b),(l,b)], color=LINE_COLOR, linewidth=2, filled=False)

            # Display the current values in the box
            closest = value // VERTICAL_STEP_METERS * VERTICAL_STEP_METERS
            for k in range(-3,4):
                tickval = closest+k*VERTICAL_STEP_METERS
                diff = tickval - value
                dy = diff*VERTICAL_STEP_PIXELS

                # Use a linear fade-in/out for numbers at top, bottom
                alpha = int(255 * (4  - abs(k)) / 4.)
                
                # Avoid putting tick label below bottom of box
                if dy > -VERTICAL_BOX_HEIGHT/2+20:
                    label = pyglet.text.Label(('%3d'%tickval).center(3), x=l+VERTICAL_LABEL_OFFSET, y=H/2+dy,
                            font_size=FONT_SIZE, color=(*FONT_COLOR,alpha), anchor_x='center', anchor_y='center') 
                    viewer.add_onetime(_DrawText(label))

        if self.viewer is None:

            self.viewer = rendering.Viewer(W, H)

            # Add sky as backround
            sky = rendering.FilledPolygon([(0,H), (0,0), (W,0), (W,H)])
            sky.set_color(*SKY_COLOR)
            self.viewer.add_geom(sky)

            # Create labels for heading
            self.heading_labels = [pyglet.text.Label(('%d'%(c*360//HEADING_TICK_COUNT)).center(3), font_size=FONT_SIZE, 
                y=H-HEADING_LABEL_Y_OFFSET, color=(*FONT_COLOR,255), 
                anchor_x='center', anchor_y='center') for c in range(HEADING_TICK_COUNT)]

        # Detect window close
        if not self.viewer.isopen: return None

        # Get vehicle state
        state = self.dynamics.getState()
        pose = state.pose
        location = pose.location
        rotation = pose.rotation
        altitude = -location[2]
        heading  = np.degrees(rotation[2])

        # Get center coordinates
        cx,cy = W/2, H/2

        # Center vertical of ground depends on pitch
        gcy = H/2 * (1 + np.sin(rotation[1]))

        # Use standard symbol for roll
        phi = rotation[0]

        # Left and right top of ground quadrilateral depend on roll
        dx,dy = _rotate(W, 0, phi)
        x1 = cx - dx
        y1 = gcy - dy
        x2 = cx + dx
        y2 = gcy + dy

        # Draw new ground quadrilateral         
        self.viewer.draw_polygon([(x1,y1), (x2,y2), (x2,y2-2*H), (x1,y1-2*H)], color=GROUND_COLOR)

        # Add a reticle for pitch, rotated by roll to match horizon
        for i in range(-3,4):

            x1 = 0
            y1 = i * PITCH_LINE_SPACING

            x2 = x1 + PITCH_LINE_WIDTH + (1-(i%2))*PITCH_LINE_WIDTH/2 # alternate line length
            y2 = y1

            x1r,y1r = _rotate(x1, y1, phi)
            x2r,y2r = _rotate(x2, y2, phi)

            # Draw two sets of lines for thickness
            self.viewer.draw_line((cx+x1r,cy+y1r),   (cx+x2r,cy+y2r), color=LINE_COLOR)
            self.viewer.draw_line((cx+x1r,cy+y1r+1), (cx+x2r,cy+y2r+1), color=LINE_COLOR)
            self.viewer.draw_line((cx-x1r,cy-y1r),   (cx-x2r,cy-y2r), color=LINE_COLOR)
            self.viewer.draw_line((cx-x1r,cy-y1r+1), (cx-x2r,cy-y2r+1), color=LINE_COLOR)

            # Add a label on the left of every other tick
            if i%2 == 0:
                pitch_label = pyglet.text.Label(('%+3d'%(-i*10)).center(3), 
                        font_size=FONT_SIZE, color=(*FONT_COLOR,255), 
                        anchor_x='center', anchor_y='center') 
                label_x = cx-x2r-PITCH_LABEL_X_OFFSET 
                label_y = cy-y2r-PITCH_LABEL_Y_OFFSET
                self.viewer.add_onetime(_DrawTextRotated(pitch_label, label_x, label_y, phi))

        # Add a horizontal line and center box at the top for the heading display
        y = H-HEADING_LINE_Y_OFFSET
        self.viewer.draw_line((0,y), (W,y), color=LINE_COLOR)
        self.viewer.draw_polygon([
            (W/2-HEADING_BOX_WIDTH,y),(W/2+HEADING_BOX_WIDTH,y),(W/2+HEADING_BOX_WIDTH,H),(W/2-HEADING_BOX_WIDTH,H)], 
            color=HIGHLIGHT_COLOR)

        # Display heading
        for i,heading_label in enumerate(self.heading_labels):
            d = HEADING_TICK_SPACING * HEADING_TICK_COUNT
            x = (W/2 - heading*d/360 + HEADING_TICK_SPACING*i) % d
            self.viewer.add_onetime(_DrawText(heading_label))
            heading_label.x = x

        # Display altitude
        _vertical_display(self.viewer, W-VERTICAL_BOX_WIDTH, W-VERTICAL_BOX_WIDTH+1, altitude)

        # Display ground speed
        _vertical_display(self.viewer, 0, -VERTICAL_POINTER_HEIGHT, altitude)

        # Add a reticle at the top for roll
        angles = np.linspace(np.radians(180-ROLL_RETICLE_LIM), np.radians(ROLL_RETICLE_LIM), ROLL_RETICLE_PTS)
        points = [(np.cos(a)*ROLL_RETICLE_RADIUS+W/2, np.sin(a)*ROLL_RETICLE_RADIUS+ROLL_RETICLE_YOFF) for a in angles]
        self.viewer.draw_polyline(points, color=LINE_COLOR, linewidth=2)
        tickvals = np.append(-np.array(ROLL_RETICLE_TICKVALS[::-1]), [0] + ROLL_RETICLE_TICKVALS)
        for tickval in tickvals: 
            k = _tickval2index(tickval)
            x1,y1 = points[k]
            x2,y2 = x1,y1+ROLL_RETICLE_TICKLEN
            rangle = np.radians(-ROLL_RETICLE_TICKVALS[-1]/ROLL_RETICLE_LIM*tickval)
            xr,yr = _rotate(0, ROLL_RETICLE_TICKLEN, rangle)
            self.viewer.draw_line((x1,y1),  (x2+xr, y2+yr), color=LINE_COLOR)
            self.viewer.draw_line((x1+1,y1),  (x2+xr+1, y2+yr), color=LINE_COLOR) # add another tick line for thickness
            roll_label = pyglet.text.Label(('%2d'%abs(tickval)).center(3), 
                    font_size=FONT_SIZE, color=(*FONT_COLOR,255), anchor_x='center', anchor_y='center') 
            label_x = x2
            label_y = y2 + ROLL_RETICLE_TICK_YOFF
            self.viewer.add_onetime(_DrawTextRotated(roll_label, label_x, label_y, rangle/2, -(6 if rangle==0 else rangle*15)))

        # Add a rotated pointer below the current angle in the roll reticle
        x,y = points[_tickval2index(np.degrees(phi))]
        x1,y1 = _rotate(-ROLL_POINTER_SIZE, 0, -phi)
        x2,y2 = _rotate(ROLL_POINTER_SIZE, 0, -phi)
        x3,y3 = _rotate(0, ROLL_POINTER_SIZE, -phi)
        y -= ROLL_POINTER_SIZE
        self.viewer.draw_polygon([(x+x1, y+y1), (x+x2,y+y2), (x+x3,y+y3)], color=POINTER_COLOR)

        return self.viewer.render(return_rgb_array = mode=='rgb_array')

    def close(self):
        pass

