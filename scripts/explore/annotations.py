import csv
import json
import os
import random

import navpy

from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, LPoint3, NodePath, Texture, TransparencyAttrib
from direct.gui.DirectGui import *

from tkinter import *

class Annotations():
    def __init__(self, render, surface, project_dir, ned_ref, tk_root):
        self.render = render
        self.surface = surface
        self.project_dir = project_dir
        self.ned_ref = ned_ref
        self.tk_root = tk_root
        random.seed()
        self.icon = loader.loadTexture('explore/marker-icon-2x.png')
        self.view_size = 100
        self.markers = []
        self.nodes = []
        self.load()

    def ned2lla(self, n, e, d):
        lla = navpy.ned2lla( [n, e, d],
                             self.ned_ref[0],
                             self.ned_ref[1],
                             self.ned_ref[2] )
        # print(n, e, d, lla)
        return lla

    def add_marker(self, ned, comment):
        marker = { "ned": ned, "comment": comment }
        self.markers.append(marker)
        
    def add_marker_dict(self, m):
        ned = navpy.lla2ned(m['lat_deg'], m['lon_deg'], m['alt_m'],
                            self.ned_ref[0], self.ned_ref[1], self.ned_ref[2])
        self.add_marker(ned, m['comment'])
        
    def load(self):
        file = os.path.join(self.project_dir, 'annotations.json')
        if os.path.exists(file):
            print('Loading saved annotations:', file)
            f = open(file, 'r')
            lla_list = json.load(f)
            f.close()
            for m in lla_list:
                if type(m) is dict:
                    print("m is dict")
                    self.add_marker_dict( m )
                elif type(m) is list:
                    print("m is list")
                    ned = navpy.lla2ned(m[0], m[1], m[2],
                                        self.ned_ref[0],
                                        self.ned_ref[1],
                                        self.ned_ref[2])
                    # print(m, ned)
                    ned[2] = self.surface.get_elevation(ned[1], ned[0])
                    if len(m) == 3:
                        self.add_marker( ned, "" )
                    else:
                        self.add_marker( ned, m[3] )
        else:
            print('No annotations file found.')

    def save(self):
        filename = os.path.join(self.project_dir, 'annotations.json')
        print('Saving annotations:', filename)
        lla_list = []
        for m in self.markers:
            ned = m['ned']
            lla = self.ned2lla( ned[0], ned[1], ned[2] )
            jm = { 'lat_deg': lla[0],
                   'lon_deg': lla[1],
                   'alt_m': float("%.2f" % (lla[2])),
                   'comment': m['comment'] }
            lla_list.append(jm)
        f = open(filename, 'w')
        json.dump(lla_list, f, indent=4)
        f.close()

        # write simple csv version
        filename = os.path.join(self.project_dir, 'annotations.csv')
        with open(filename, 'w') as f:
            fieldnames = ['lat_deg', 'lon_deg', 'alt_m', 'comment']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for jm in lla_list:
                writer.writerow(jm)

    def edit(self, ned, comment="", exists=False):
        lla = self.ned2lla(ned[0], ned[1], ned[2])
        new = Toplevel(self.tk_root)
        self.edit_result = "cancel"
        e = None
        def on_ok():
            new.quit()
            new.withdraw()
            print('comment:', e.get())
            self.edit_result = "ok"
        def on_del():
            new.quit()
            new.withdraw()
            print('comment:', e.get())
            self.edit_result = "delete"
        def on_cancel():
            print("on cancel")
            new.quit()
            new.withdraw()
        new.protocol("WM_DELETE_WINDOW", on_cancel)
        if not exists:
            new.title("New marker")
        else:
            new.title("Edit marker")
        f = Frame(new)
        f.pack(side=TOP, fill=X)
        w = Label(f, text="Lat: %.8f" % lla[0])
        w.pack(side=LEFT)
        f = Frame(new)
        f.pack(side=TOP, fill=X)
        w = Label(f, text="Lon: %.8f" % lla[1])
        w.pack(side=LEFT)
        f = Frame(new)
        f.pack(side=TOP, fill=X)
        w = Label(f, text="Alt(m): %.1f" % lla[2])
        w.pack(side=LEFT)
        f = Frame(new)
        f.pack(side=TOP)
        l = Label(f, text="Comment:")
        l.pack(side=LEFT)
        e = Entry(f)
        e.insert(0, comment)
        e.pack(side=LEFT)
        e.focus_set()
        f = Frame(new)
        f.pack(fill=X)
        bok = Button(f, text="OK", command=on_ok)
        bok.pack(side=LEFT, fill=X)
        if exists:
            bdel = Button(f, text="Delete", command=on_del)
            bdel.pack(side=LEFT, fill=X)
        bx = Button(f, text="Cancel", command=on_cancel)
        bx.pack(side=LEFT, fill=X)
        new.mainloop()
        print("after main loop:", self.edit_result, e.get())
        return self.edit_result, e.get()

    def toggle(self, cam_pos):
        mw = base.mouseWatcherNode
        if not mw.hasMouse():
            return
        props = base.win.getProperties()
        y = props.getYSize()
        pxm = float(y) / self.view_size
        range = 25 / pxm
        hsize = 12 / pxm
        vsize = 40 / pxm

        mpos = mw.getMouse()
        print('mpos:', mpos)
        x = cam_pos[0] + mpos[0] * self.view_size*0.5 * base.getAspectRatio()
        y = cam_pos[1] + mpos[1] * self.view_size*0.5
        dirty = False
        # check if we clicked on an existing marker
        found = -1
        for i, m in enumerate(self.markers):
            ned = m['ned']
            dx = abs(x - ned[1])
            dy = y - ned[0]
            if dx <= (hsize*0.5)+1 and y >= ned[0]-1 and y <= ned[0]+vsize+1:
                found = i
                # del self.markers[i]
                # break
        if found >= 0:
            print("Found existing marker:", found)
            ned = self.markers[found]['ned']
            comment = self.markers[found]['comment']
            result, comment = self.edit(ned, comment, exists=True)
            if result == 'ok':
                self.markers[found]['comment'] = comment
                dirty = True
            elif result == 'delete':
                del self.markers[found]
                dirty = True
        else:
            z = self.surface.get_elevation(x, y)
            result, comment = self.edit( [y, x, z], exists=False)
            if result == 'ok':
                self.add_marker( [y, x, z], comment )
                dirty = True
        if dirty:
            self.rebuild(self.view_size)
            self.save()
            
    def rebuild(self, view_size):
        self.view_size = view_size
        props = base.win.getProperties()
        y = props.getYSize()
        pxm = float(y) / self.view_size
        hsize = 12 / pxm
        vsize = 40 / pxm
        #print(hsize, vsize)
        cm = CardMaker('card')
        cm.setFrame( LPoint3(-hsize, 0,     0 ),
                     LPoint3( hsize, 0,     0 ),
                     LPoint3( hsize, vsize, 0 ),
                     LPoint3(-hsize, vsize, 0 ) )

        for n in self.nodes:
            n.removeNode()

        self.nodes = []
        for m in self.markers:
            node = NodePath(cm.generate())
            node.setTexture(self.icon, 1)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthTest(False)
            node.setDepthWrite(False)
            node.setBin("unsorted", 1)
            ned = m['ned']
            node.setPos(ned[1], ned[0], 0)
            node.reparentTo(self.render)
            self.nodes.append(node)
