import datetime
import ephem
import math
import navpy
import numpy as np

# find our custom built opencv first
import sys
sys.path.insert(0, "/usr/local/lib/python2.7/site-packages/")
import cv2

sys.path.append('../lib')
import transformations

# helpful constants
d2r = math.pi / 180.0
r2d = 180.0 / math.pi
mps2kt = 1.94384
kt2mps = 1 / mps2kt
ft2m = 0.3048
m2ft = 1 / ft2m

# color definitions
green2 = (0, 238, 0)
medium_orchid = (186, 85, 211)
yellow = (50, 255, 255)

class HUD:
    def __init__(self, K):
        self.K = K
        self.PROJ = None
        self.line_width = 1
        self.color = green2
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_size = 0.6
        self.render_w = 0
        self.render_h = 0
        self.lla = [0.0, 0.0, 0.0]
        self.unixtime = 0
        self.ned = [0.0, 0.0, 0.0]
        self.ref = [0.0, 0.0, 0.0]
        self.vn = 0.0
        self.ve = 0.0
        self.vd = 0.0
        self.vel_filt = [0.0, 0.0, 0.0]
        self.phi_rad = 0
        self.the_rad = 0
        self.psi_rad = 0
        self.frame = None
        self.airspeed_units = 'kt'
        self.altitude_units = 'ft'
        self.airspeed_kt = 0
        self.altitude_m = 0
        self.flight_mode = 'none'
        self.ap_roll = 0
        self.ap_pitch = 0
        self.ap_hdg = 0
        self.ap_speed = 0
        self.ap_altitude = 0

    def set_render_size(self, w, h):
        self.render_w = w
        self.render_h = h
        
    def set_line_width(self, line_width):
        self.line_width = line_width
        if self.line_width < 1:
            self.line_width = 1

    def set_color(self, color):
        self.color = color
        
    def set_font_size(self, font_size):
        self.font_size = font_size
        if self.font_size < 0.4:
            self.font_size = 0.4

    def set_units(self, airspeed_units, altitude_units):
        self.airspeed_units = airspeed_units
        self.altitude_units = altitude_units
        
    def set_ned_ref(self, lat, lon):
        self.ref = [ lat, lon, 0.0]

    def update_frame(self, frame):
        self.frame = frame

    def update_lla(self, lla):
        self.lla = lla

    def update_unixtime(self, unixtime):
        self.unixtime = unixtime
        
    def update_ned(self, ned):
        self.ned = ned[:]

    def update_proj(self, PROJ):
        self.PROJ = PROJ

    def update_vel(self, vn, ve, vd):
        self.vn = vn
        self.ve = ve
        self.vd = vd
        
    def update_att_rad(self, phi_rad, the_rad, psi_rad):
        self.phi_rad = phi_rad
        self.the_rad = the_rad
        self.psi_rad = psi_rad

    def update_airdata(self, airspeed_kt, altitude_m):
        self.airspeed_kt = airspeed_kt
        self.altitude_m = altitude_m

    def update_ap(self, flight_mode, ap_roll, ap_pitch, ap_hdg,
                  ap_speed, ap_altitude):
        self.flight_mode = flight_mode
        self.ap_roll = ap_roll
        self.ap_pitch = ap_pitch
        self.ap_hdg = ap_hdg
        self.ap_speed = ap_speed
        self.ap_altitude = ap_altitude
        
    def compute_sun_moon_ned(self, lon_deg, lat_deg, alt_m, timestamp):
        d = datetime.datetime.utcfromtimestamp(timestamp)
        #d = datetime.datetime.utcnow()
        ed = ephem.Date(d)
        #print 'ephem time utc:', ed
        #print 'localtime:', ephem.localtime(ed)

        ownship = ephem.Observer()
        ownship.lon = '%.8f' % lon_deg
        ownship.lat = '%.8f' % lat_deg
        ownship.elevation = alt_m
        ownship.date = ed

        sun = ephem.Sun(ownship)
        moon = ephem.Moon(ownship)

        sun_ned = [ math.cos(sun.az), math.sin(sun.az), -math.sin(sun.alt) ]
        moon_ned = [ math.cos(moon.az), math.sin(moon.az), -math.sin(moon.alt) ]

        return sun_ned, moon_ned

    def project_point(self, ned):
        uvh = self.K.dot( self.PROJ.dot( [ned[0], ned[1], ned[2], 1.0] ).T )
        if uvh[2] > 0.1:
            uvh /= uvh[2]
            uv = ( int(np.squeeze(uvh[0,0])), int(np.squeeze(uvh[1,0])) )
            return uv
        else:
            return None

    def draw_horizon(self):
        divs = 10
        pts = []
        for i in range(divs + 1):
            a = (float(i) * 360/float(divs)) * d2r
            n = math.cos(a)
            e = math.sin(a)
            d = 0.0
            pts.append( [n, e, d] )

        for i in range(divs):
            p1 = pts[i]
            p2 = pts[i+1]
            uv1 = self.project_point( [self.ned[0] + p1[0],
                                       self.ned[1] + p1[1],
                                       self.ned[2] + p1[2]] )
            uv2 = self.project_point( [self.ned[0] + p2[0],
                                       self.ned[1] + p2[1],
                                       self.ned[2] + p2[2]] )
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)

    def ladder_helper(self, q0, a0, a1):
        q1 = transformations.quaternion_from_euler(-a1*d2r, -a0*d2r, 0.0,
                                                   'rzyx')
        q = transformations.quaternion_multiply(q1, q0)
        v = transformations.quaternion_transform(q, [1.0, 0.0, 0.0])
        uv = self.project_point( [self.ned[0] + v[0],
                                  self.ned[1] + v[1],
                                  self.ned[2] + v[2]] )
        return uv

    def draw_pitch_ladder(self, beta_rad=0.0):
        a1 = 2.0
        a2 = 8.0
        #slide_rad = self.psi_rad - beta_rad
        slide_rad = self.psi_rad
        q0 = transformations.quaternion_about_axis(slide_rad, [0.0, 0.0, -1.0])
        for a0 in range(5,35,5):
            # above horizon

            # right horizontal
            uv1 = self.ladder_helper(q0, a0, a1)
            uv2 = self.ladder_helper(q0, a0, a2)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)
                du = uv2[0] - uv1[0]
                dv = uv2[1] - uv1[1]
                uv = ( uv1[0] + int(1.25*du), uv1[1] + int(1.25*dv) )
                self.draw_label("%d" % a0, uv, self.font_size, self.line_width)
            # right tick
            uv1 = self.ladder_helper(q0, a0-0.5, a1)
            uv2 = self.ladder_helper(q0, a0, a1)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)
            # left horizontal
            uv1 = self.ladder_helper(q0, a0, -a1)
            uv2 = self.ladder_helper(q0, a0, -a2)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)
                du = uv2[0] - uv1[0]
                dv = uv2[1] - uv1[1]
                uv = ( uv1[0] + int(1.25*du), uv1[1] + int(1.25*dv) )
                self.draw_label("%d" % a0, uv, self.font_size, self.line_width)
            # left tick
            uv1 = self.ladder_helper(q0, a0-0.5, -a1)
            uv2 = self.ladder_helper(q0, a0, -a1)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)

            # below horizon

            # right horizontal
            uv1 = self.ladder_helper(q0, -a0, a1)
            uv2 = self.ladder_helper(q0, -a0-0.5, a2)
            if uv1 != None and uv2 != None:
                du = uv2[0] - uv1[0]
                dv = uv2[1] - uv1[1]
                for i in range(0,3):
                    tmp1 = (uv1[0] + int(0.375*i*du), uv1[1] + int(0.375*i*dv))
                    tmp2 = (tmp1[0] + int(0.25*du), tmp1[1] + int(0.25*dv))
                    cv2.line(self.frame, tmp1, tmp2, self.color,
                             self.line_width, cv2.CV_AA)
                uv = ( uv1[0] + int(1.25*du), uv1[1] + int(1.25*dv) )
                self.draw_label("%d" % a0, uv, self.font_size, self.line_width)

            # right tick
            uv1 = self.ladder_helper(q0, -a0+0.5, a1)
            uv2 = self.ladder_helper(q0, -a0, a1)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)
            # left horizontal
            uv1 = self.ladder_helper(q0, -a0, -a1)
            uv2 = self.ladder_helper(q0, -a0-0.5, -a2)
            if uv1 != None and uv2 != None:
                du = uv2[0] - uv1[0]
                dv = uv2[1] - uv1[1]
                for i in range(0,3):
                    tmp1 = (uv1[0] + int(0.375*i*du), uv1[1] + int(0.375*i*dv))
                    tmp2 = (tmp1[0] + int(0.25*du), tmp1[1] + int(0.25*dv))
                    cv2.line(self.frame, tmp1, tmp2, self.color,
                             self.line_width, cv2.CV_AA)
                uv = ( uv1[0] + int(1.25*du), uv1[1] + int(1.25*dv) )
                self.draw_label("%d" % a0, uv, self.font_size, self.line_width)
            # left tick
            uv1 = self.ladder_helper(q0, -a0+0.5, -a1)
            uv2 = self.ladder_helper(q0, -a0, -a1)
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)

    def draw_flight_path_marker(self, alpha_rad, beta_rad):
        q0 = transformations.quaternion_about_axis(self.psi_rad + beta_rad,
                                                   [0.0, 0.0, -1.0])
        a0 = (self.the_rad - alpha_rad) * r2d
        uv = self.ladder_helper(q0, a0, 0)
        if uv != None:
            r1 = int(round(self.render_h / 60))
            r2 = int(round(self.render_h / 30))
            uv1 = (uv[0]+r1, uv[1])
            uv2 = (uv[0]+r2, uv[1])
            uv3 = (uv[0]-r1, uv[1])
            uv4 = (uv[0]-r2, uv[1])
            uv5 = (uv[0], uv[1]-r1)
            uv6 = (uv[0], uv[1]-r2)
            cv2.circle(self.frame, uv, r1, self.color, self.line_width,
                       cv2.CV_AA)
            cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                     cv2.CV_AA)
            cv2.line(self.frame, uv3, uv4, self.color, self.line_width,
                     cv2.CV_AA)
            cv2.line(self.frame, uv5, uv6, self.color, self.line_width,
                     cv2.CV_AA)

    def rotate_pt(self, p, center, a):
        x = math.cos(a) * (p[0]-center[0]) - math.sin(a) * (p[1]-center[1]) + center[0]

        y = math.sin(a) * (p[0]-center[0]) + math.cos(a) * (p[1]-center[1]) + center[1]
        return (int(x), int(y))

    def draw_vbars(self):
        color = medium_orchid
        size = self.line_width
        a1 = 10.0
        a2 = 1.5
        a3 = 3.0
        q0 = transformations.quaternion_about_axis(self.psi_rad,
                                                   [0.0, 0.0, -1.0])
        a0 = self.ap_pitch

        # rotation point (about nose)
        rot = self.ladder_helper(q0, self.the_rad*r2d, 0.0)

        # center point
        tmp1 = self.ladder_helper(q0, a0, 0.0)
        center = rotate_pt(tmp1, rot, self.ap_roll*d2r)

        # right vbar
        tmp1 = self.ladder_helper(q0, a0-a3, a1)
        tmp2 = self.ladder_helper(q0, a0-a3, a1+a3)
        tmp3 = self.ladder_helper(q0, a0-a2, a1+a3)
        uv1 = rotate_pt(tmp1, rot, self.ap_roll*d2r)
        uv2 = rotate_pt(tmp2, rot, self.ap_roll*d2r)
        uv3 = rotate_pt(tmp3, rot, self.ap_roll*d2r)
        if uv1 != None and uv2 != None and uv3 != None:
            cv2.line(self.frame, center, uv1, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, center, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)
        # left vbar
        tmp1 = self.ladder_helper(q0, a0-a3, -a1)
        tmp2 = self.ladder_helper(q0, a0-a3, -a1-a3)
        tmp3 = self.ladder_helper(q0, a0-a2, -a1-a3)
        uv1 = rotate_pt(tmp1, rot, self.ap_roll*d2r)
        uv2 = rotate_pt(tmp2, rot, self.ap_roll*d2r)
        uv3 = rotate_pt(tmp3, rot, self.ap_roll*d2r)
        if uv1 != None and uv2 != None and uv3 != None:
            cv2.line(self.frame, center, uv1, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, center, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)

    def draw_heading_bug(self):
        color = medium_orchid
        size = 2
        a = math.atan2(self.ve, self.vn)
        q0 = transformations.quaternion_about_axis(self.ap_hdg*d2r,
                                                   [0.0, 0.0, -1.0])
        center = self.ladder_helper(q0, 0, 0)
        pts = []
        pts.append( self.ladder_helper(q0, 0, 2.0) )
        pts.append( self.ladder_helper(q0, 0.0, -2.0) )
        pts.append( self.ladder_helper(q0, 1.5, -2.0) )
        pts.append( self.ladder_helper(q0, 1.5, -1.0) )
        pts.append( center )
        pts.append( self.ladder_helper(q0, 1.5, 1.0) )
        pts.append( self.ladder_helper(q0, 1.5, 2.0) )
        for i, p in enumerate(pts):
            if p == None or center == None:
                return
            #else:
            #    pts[i] = rotate_pt(pts[i], center, -cam_roll*d2r)
        cv2.line(self.frame, pts[0], pts[1], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[1], pts[2], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[2], pts[3], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[3], pts[4], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[4], pts[5], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[5], pts[6], color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, pts[6], pts[0], color, self.line_width, cv2.CV_AA)
        #pts = np.array( pts, np.int32 )
        #pts = pts.reshape((-1,1,2))
        #cv2.polylines(self.frame, pts, True, color, self.line_width, cv2.CV_AA)

    def draw_bird(self):
        color = yellow
        size = 2
        a1 = 10.0
        a2 = 3.0
        a2 = 3.0
        q0 = transformations.quaternion_about_axis(self.psi_rad, [0.0, 0.0, -1.0])
        a0 = self.the_rad*r2d

        # center point
        center = self.ladder_helper(q0, self.the_rad*r2d, 0.0)

        # right vbar
        tmp1 = self.ladder_helper(q0, a0-a2, a1)
        tmp2 = self.ladder_helper(q0, a0-a2, a1-a2)
        uv1 = rotate_pt(tmp1, center, self.phi_rad)
        uv2 = rotate_pt(tmp2, center, self.phi_rad)
        if uv1 != None and uv2 != None:
            cv2.line(self.frame, center, uv1, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, center, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        # left vbar
        tmp1 = self.ladder_helper(q0, a0-a2, -a1)
        tmp2 = self.ladder_helper(q0, a0-a2, -a1+a2)
        uv1 = rotate_pt(tmp1, center, self.phi_rad)
        uv2 = rotate_pt(tmp2, center, self.phi_rad)
        if uv1 != None and uv2 != None:
            cv2.line(self.frame, center, uv1, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, center, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)

    filter_vn = 0.0
    filter_ve = 0.0
    tf_vel = 0.5
    def draw_course(self):
        global filter_vn
        global filter_ve
        color = yellow
        size = 2
        filter_vn = (1.0 - tf_vel) * filter_vn + tf_vel * self.vn
        filter_ve = (1.0 - tf_vel) * filter_ve + tf_vel * self.ve
        a = math.atan2(filter_ve, filter_vn)
        q0 = transformations.quaternion_about_axis(a, [0.0, 0.0, -1.0])
        tmp1 = self.ladder_helper(q0, 0, 0)
        tmp2 = self.ladder_helper(q0, 1.5, 1.0)
        tmp3 = self.ladder_helper(q0, 1.5, -1.0)
        if tmp1 != None and tmp2 != None and tmp3 != None :
            uv2 = rotate_pt(tmp2, tmp1, -cam_roll*d2r)
            uv3 = rotate_pt(tmp3, tmp1, -cam_roll*d2r)
            cv2.line(self.frame, tmp1, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, tmp1, uv3, color, self.line_width, cv2.CV_AA)

    def draw_label(self, label, uv, font_scale, thickness,
                   horiz='center', vert='center'):
            size = cv2.getTextSize(label, self.font, font_scale, thickness)
            if horiz == 'center':
                u = uv[0] - (size[0][0] / 2)
            else:
                u = uv[0]
            if vert == 'above':
                v = uv[1]
            elif vert == 'below':
                v = uv[1] + size[0][1]
            elif vert == 'center':
                v = uv[1] + (size[0][1] / 2)
            uv = (u, v)
            cv2.putText(self.frame, label, uv, self.font, font_scale,
                        self.color, thickness, cv2.CV_AA)

    def draw_labeled_point(self, ned, label, scale=1, vert='above'):
        uv = self.project_point([ned[0], ned[1], ned[2]])
        if uv != None:
            cv2.circle(self.frame, uv, 4+self.line_width, self.color,
                       self.line_width, cv2.CV_AA)
        if vert == 'above':
            uv = self.project_point([ned[0], ned[1], ned[2] - 0.02])
        else:
            uv = self.project_point([ned[0], ned[1], ned[2] + 0.02])
        if uv != None:
            self.draw_label(label, uv, scale, self.line_width, vert=vert)

    def draw_lla_point(self, lla, label):
        pt_ned = navpy.lla2ned( lla[0], lla[1], lla[2],
                                self.ref[0], self.ref[1], self.ref[2] )
        rel_ned = [ pt_ned[0] - self.ned[0],
                    pt_ned[1] - self.ned[1],
                    pt_ned[2] - self.ned[2] ]
        dist = math.sqrt(rel_ned[0]*rel_ned[0] + rel_ned[1]*rel_ned[1]
                         + rel_ned[2]*rel_ned[2])
        m2sm = 0.000621371
        dist_sm = dist * m2sm
        if dist_sm <= 15.0:
            scale = 1.0 - dist_sm / 25.0
            if dist_sm <= 7.5:
                label += " (%.1f)" % dist_sm
            # normalize, and draw relative to aircraft ned so that label
            # separation works better
            rel_ned[0] /= dist
            rel_ned[1] /= dist
            rel_ned[2] /= dist
            self.draw_labeled_point([self.ned[0] + rel_ned[0],
                                     self.ned[1] + rel_ned[1],
                                     self.ned[2] + rel_ned[2]],
                                    label, scale=scale, vert='below')

    def draw_compass_points(self):
        # 30 Ticks
        divs = 12
        pts = []
        for i in range(divs):
            a = (float(i) * 360/float(divs)) * d2r
            n = math.cos(a)
            e = math.sin(a)
            uv1 = self.project_point([self.ned[0] + n,
                                      self.ned[1] + e,
                                      self.ned[2] - 0.0])
            uv2 = self.project_point([self.ned[0] + n,
                                      self.ned[1] + e,
                                      self.ned[2] - 0.02])
            if uv1 != None and uv2 != None:
                cv2.line(self.frame, uv1, uv2, self.color, self.line_width,
                         cv2.CV_AA)

        # North
        uv = self.project_point([self.ned[0] + 1.0, self.ned[1] + 0.0, self.ned[2] - 0.03])
        if uv != None:
            self.draw_label('N', uv, 1, self.line_width, vert='above')
        # South
        uv = self.project_point([self.ned[0] - 1.0, self.ned[1] + 0.0, self.ned[2] - 0.03])
        if uv != None:
            self.draw_label('S', uv, 1, self.line_width, vert='above')
        # East
        uv = self.project_point([self.ned[0] + 0.0, self.ned[1] + 1.0, self.ned[2] - 0.03])
        if uv != None:
            self.draw_label('E', uv, 1, self.line_width, vert='above')
        # West
        uv = self.project_point([self.ned[0] + 0.0, self.ned[1] - 1.0, self.ned[2] - 0.03])
        if uv != None:
            self.draw_label('W', uv, 1, self.line_width, vert='above')

    def draw_astro(self):
        sun_ned, moon_ned = self.compute_sun_moon_ned(self.lla[1],
                                                      self.lla[0],
                                                      self.lla[2],
                                                      self.unixtime)
        if sun_ned == None or moon_ned == None:
            return

        # Sun
        self.draw_labeled_point([self.ned[0] + sun_ned[0],
                                 self.ned[1] + sun_ned[1],
                                 self.ned[2] + sun_ned[2]],
                                'Sun')
        # shadow (if sun above horizon)
        if sun_ned[2] < 0.0:
            self.draw_labeled_point([self.ned[0] - sun_ned[0],
                                     self.ned[1] - sun_ned[1],
                                     self.ned[2] - sun_ned[2]],
                                    'shadow', scale=0.7)
        # Moon
        self.draw_labeled_point([self.ned[0] + moon_ned[0],
                                 self.ned[1] + moon_ned[1],
                                 self.ned[2] + moon_ned[2]],
                                'Moon')

    def draw_airports(self):
        kmsp = [ 44.882000, -93.221802, 256 ]
        self.draw_lla_point(kmsp, 'KMSP')
        ksgs = [ 44.857101, -93.032898, 250 ]
        self.draw_lla_point(ksgs, 'KSGS')
        kstp = [ 44.934502, -93.059998, 215 ]
        self.draw_lla_point(kstp, 'KSTP')
        my52 = [ 44.718601, -93.044098, 281 ]
        self.draw_lla_point(my52, 'MY52')
        kfcm = [ 44.827202, -93.457100, 276 ]
        self.draw_lla_point(kfcm, 'KFCM')
        kane = [ 45.145000, -93.211403, 278 ]
        self.draw_lla_point(kane, 'KANE')
        klvn = [ 44.627899, -93.228104, 293 ]
        self.draw_lla_point(klvn, 'KLVN')
        kmic = [ 45.062000, -93.353897, 265 ]
        self.draw_lla_point(kmic, 'KMIC')
        mn45 = [ 44.566101, -93.132202, 290 ]
        self.draw_lla_point(mn45, 'MN45')
        mn58 = [ 44.697701, -92.864098, 250 ]
        self.draw_lla_point(mn58, 'MN58')
        mn18 = [ 45.187199, -93.130501, 276 ]
        self.draw_lla_point(mn18, 'MN18')

    def draw_nose(self):
        ned2body = transformations.quaternion_from_euler(self.psi_rad,
                                                         self.the_rad,
                                                         self.phi_rad,
                                                         'rzyx')
        body2ned = transformations.quaternion_inverse(ned2body)
        vec = transformations.quaternion_transform(body2ned, [1.0, 0.0, 0.0])
        uv = self.project_point([self.ned[0] + vec[0],
                                 self.ned[1] + vec[1],
                                 self.ned[2]+ vec[2]])
        r1 = int(round(self.render_h / 80))
        r2 = int(round(self.render_h / 40))
        if uv != None:
            cv2.circle(self.frame, uv, r1, self.color, self.line_width, cv2.CV_AA)
            cv2.circle(self.frame, uv, r2, self.color, self.line_width, cv2.CV_AA)

    def draw_velocity_vector(self):
        tf = 0.2
        vel = [self.vn, self.ve, self.vd] # filter coding convenience
        for i in range(3):
            self.vel_filt[i] = (1.0 - tf) * self.vel_filt[i] + tf * vel[i]

        uv = self.project_point([self.ned[0] + self.vel_filt[0],
                                 self.ned[1] + self.vel_filt[1],
                                 self.ned[2] + self.vel_filt[2]])
        if uv != None:
            cv2.circle(self.frame, uv, 4, self.color, 1, cv2.CV_AA)

    def draw_speed_tape(self, airspeed, ap_speed, units_label):
        color = self.color
        size = 1
        pad = 5 + self.line_width*2
        h, w, d = self.frame.shape

        # reference point
        cy = int(h * 0.5)
        cx = int(w * 0.2)
        miny = int(h * 0.2)
        maxy = int(h - miny)

        # current airspeed
        label = "%.0f" % airspeed
        lsize = cv2.getTextSize(label, self.font, self.font_size, self.line_width)
        xsize = lsize[0][0] + pad
        ysize = lsize[0][1] + pad
        uv = ( int(cx + ysize*0.7), cy + lsize[0][1] / 2)
        cv2.putText(self.frame, label, uv, self.font, self.font_size, color, self.line_width, cv2.CV_AA)
        uv1 = (cx, cy)
        uv2 = (cx + int(ysize*0.7),         cy - ysize / 2 )
        uv3 = (cx + int(ysize*0.7) + xsize, cy - ysize / 2 )
        uv4 = (cx + int(ysize*0.7) + xsize, cy + ysize / 2 + 1 )
        uv5 = (cx + int(ysize*0.7),         cy + ysize / 2 + 1)
        cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv3, uv4, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv4, uv5, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv5, uv1, color, self.line_width, cv2.CV_AA)

        # speed tics
        spacing = lsize[0][1]
        y = cy - int((0 - airspeed) * spacing)
        if y < miny: y = miny
        if y > maxy: y = maxy
        uv1 = (cx, y)
        y = cy - int((70 - airspeed) * spacing)
        if y < miny: y = miny
        if y > maxy: y = maxy
        uv2 = (cx, y)
        cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        for i in range(0, 65, 1):
            offset = int((i - airspeed) * spacing)
            if cy - offset >= miny and cy - offset <= maxy:
                uv1 = (cx, cy - offset)
                if i % 5 == 0:
                    uv2 = (cx - 6, cy - offset)
                else:
                    uv2 = (cx - 4, cy - offset)
                cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        for i in range(0, 65, 5):
            offset = int((i - airspeed) * spacing)
            if cy - offset >= miny and cy - offset <= maxy:
                label = "%d" % i
                lsize = cv2.getTextSize(label, self.font, self.font_size, self.line_width)
                uv3 = (cx - 8 - lsize[0][0], cy - offset + lsize[0][1] / 2)
                cv2.putText(self.frame, label, uv3, self.font, self.font_size, color, self.line_width, cv2.CV_AA)

        # units
        lsize = cv2.getTextSize(units_label, self.font, self.font_size, self.line_width)
        uv = (cx - int(lsize[0][1]*0.5), maxy + lsize[0][1] + self.line_width*2)
        cv2.putText(self.frame, units_label, uv, self.font, self.font_size, color, self.line_width, cv2.CV_AA)

        # speed bug
        offset = int((ap_speed - airspeed) * spacing)
        if self.flight_mode == 'auto' and cy - offset >= miny and cy - offset <= maxy:
            uv1 = (cx,                  cy - offset)
            uv2 = (cx + int(ysize*0.7), cy - offset - ysize / 2 )
            uv3 = (cx + int(ysize*0.7), cy - offset - ysize )
            uv4 = (cx,                  cy - offset - ysize )
            uv5 = (cx,                  cy - offset + ysize )
            uv6 = (cx + int(ysize*0.7), cy - offset + ysize )
            uv7 = (cx + int(ysize*0.7), cy - offset + ysize / 2 )
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv3, uv4, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv4, uv5, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv5, uv6, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv6, uv7, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv7, uv1, color, self.line_width, cv2.CV_AA)

    def draw_altitude_tape(self, altitude, ap_alt, units_label):
        color = self.color
        size = 1
        pad = 5 + self.line_width*2
        h, w, d = self.frame.shape

        # reference point
        cy = int(h * 0.5)
        cx = int(w * 0.8)
        miny = int(h * 0.2)
        maxy = int(h - miny)

        minrange = int(altitude/100)*10 - 30
        maxrange = int(altitude/100)*10 + 30

        # current altitude
        label = "%.0f" % (round(altitude/10.0) * 10)
        lsize = cv2.getTextSize(label, self.font, self.font_size, self.line_width)
        xsize = lsize[0][0] + pad
        ysize = lsize[0][1] + pad
        uv = ( int(cx - ysize*0.7 - lsize[0][0]), cy + lsize[0][1] / 2)
        cv2.putText(self.frame, label, uv, self.font, self.font_size, color, self.line_width, cv2.CV_AA)
        uv1 = (cx, cy)
        uv2 = (cx - int(ysize*0.7),         cy - ysize / 2 )
        uv3 = (cx - int(ysize*0.7) - xsize, cy - ysize / 2 )
        uv4 = (cx - int(ysize*0.7) - xsize, cy + ysize / 2 + 1 )
        uv5 = (cx - int(ysize*0.7),         cy + ysize / 2 + 1 )
        cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv3, uv4, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv4, uv5, color, self.line_width, cv2.CV_AA)
        cv2.line(self.frame, uv5, uv1, color, self.line_width, cv2.CV_AA)

        # msl tics
        spacing = lsize[0][1]
        y = cy - int((minrange*10 - altitude)/10 * spacing)
        if y < miny: y = miny
        if y > maxy: y = maxy
        uv1 = (cx, y)
        y = cy - int((maxrange*10 - altitude)/10 * spacing)
        if y < miny: y = miny
        if y > maxy: y = maxy
        uv2 = (cx, y)
        cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        for i in range(minrange, maxrange, 1):
            offset = int((i*10 - altitude)/10 * spacing)
            if cy - offset >= miny and cy - offset <= maxy:
                uv1 = (cx, cy - offset)
                if i % 5 == 0:
                    uv2 = (cx + 6, cy - offset)
                else:
                    uv2 = (cx + 4, cy - offset)
                cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
        for i in range(minrange, maxrange, 5):
            offset = int((i*10 - altitude)/10 * spacing)
            if cy - offset >= miny and cy - offset <= maxy:
                label = "%d" % (i*10)
                lsize = cv2.getTextSize(label, self.font, self.font_size, self.line_width)
                uv3 = (cx + 8 , cy - offset + lsize[0][1] / 2)
                cv2.putText(self.frame, label, uv3, self.font, self.font_size, color, self.line_width, cv2.CV_AA)

        # units
        lsize = cv2.getTextSize(units_label, self.font, self.font_size, self.line_width)
        uv = (cx - int(lsize[0][1]*0.5), maxy + lsize[0][1] + self.line_width*2)
        cv2.putText(self.frame, units_label, uv, self.font, self.font_size, color, self.line_width, cv2.CV_AA)

        # altitude bug
        offset = int((ap_alt - altitude)/10.0 * spacing)
        if self.flight_mode == 'auto' and cy - offset >= miny and cy - offset <= maxy:
            uv1 = (cx,                  cy - offset)
            uv2 = (cx - int(ysize*0.7), cy - offset - ysize / 2 )
            uv3 = (cx - int(ysize*0.7), cy - offset - ysize )
            uv4 = (cx,                  cy - offset - ysize )
            uv5 = (cx,                  cy - offset + ysize )
            uv6 = (cx - int(ysize*0.7), cy - offset + ysize )
            uv7 = (cx - int(ysize*0.7), cy - offset + ysize / 2 )
            cv2.line(self.frame, uv1, uv2, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv2, uv3, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv3, uv4, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv4, uv5, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv5, uv6, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv6, uv7, color, self.line_width, cv2.CV_AA)
            cv2.line(self.frame, uv7, uv1, color, self.line_width, cv2.CV_AA)

    # draw the conformal components of the hud (those that should
    # 'stick' to the real world view.
    def draw_conformal(self):
        self.draw_horizon()
        self.draw_compass_points()
        self.draw_pitch_ladder(beta_rad=0.0)
        #self.draw_flight_path_marker(alpha_rad, beta_rad)
        self.draw_astro()
        self.draw_airports()
        self.draw_velocity_vector()

    # draw the fixed indications (that always stay in the same place
    # on the hud.)  note: also draw speed/alt bugs here
    def draw_fixed(self):
        if self.airspeed_units == 'mps':
            airspeed = self.airspeed_kt * kt2mps
            ap_speed = self.ap_speed * kt2mps
        else:
            airspeed = self.airspeed_kt
            ap_speed = self.ap_speed
        self.draw_speed_tape(airspeed, ap_speed,
                             self.airspeed_units.capitalize())
        if self.altitude_units == 'm':
            altitude = self.altitude_m
            ap_altitude = self.ap_altitude
        else:
            altitude = self.altitude_m * m2ft
            ap_altitude = self.ap_altitude * m2ft
        self.draw_altitude_tape(altitude, ap_altitude,
                                self.altitude_units.capitalize())

    # draw autopilot symbology
    def draw_ap(self):
        if self.flight_mode == 'manual':
            self.draw_nose()
        else:
            self.draw_vbars()
            self.draw_heading_bug()
            self.draw_bird()
            self.draw_course()
        
    def draw(self):
        self.draw_conformal()
        self.draw_fixed()
        self.draw_ap()
        
