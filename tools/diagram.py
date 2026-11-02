#!/usr/bin/env python3
# =============================================================================
# diagram.py - block, flow and state diagrams that obey the paper's rules
# -----------------------------------------------------------------------------
# Purpose : Draws the hand-made diagrams of the paper and
#           checks the drawing rules on the geometry before saving:
#             1. black and white only;
#             2. every connection is made of straight horizontal and vertical
#                segments (orthogonal routing);
#             3. no two connections cross, touch or run closer than GAP_LINE;
#                branches of one connection meet at a dot (T junction);
#             4. no connection passes through a block;
#             5. no text touches a line, a block outline or other text: every
#                label keeps CLEAR points of white space around it.
#           A figure that breaks a rule is not saved; the error names the
#           element. The check uses the real rendered text extents.
# Units   : points (1/72 in), origin at the bottom-left corner.
# Clearance: CLEAR is measured from the outer edge of a drawn line (its
#           centre line plus half the line width).
# Usage   : d = Diagram(width_pt, height_pt); d.box(...); d.wire(...);
#           d.text(...); d.save(path_without_extension)
# =============================================================================
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402



def _pick_font():
    """Times New Roman on Windows; Liberation Serif (same metrics) on Linux."""
    from matplotlib import font_manager
    for name in ("Times New Roman", "Liberation Serif", "DejaVu Serif"):
        try:
            font_manager.findfont(font_manager.FontProperties(family=name), fallback_to_default=False)
            return name
        except ValueError:
            continue
    return "serif"


FONT = _pick_font()
SIZE = 8.0          # IEEE template: 8 pt figure labels
CLEAR = 1.5         # pt of white space around every label
GAP_LINE = 3.0      # pt between parallel segments of different connections
LW = 0.8
HEAD_L, HEAD_W = 4.0, 2.6
EPS = 1e-6


class RuleError(Exception):
    pass


def _seg_dist(a, b):
    """Distance between two axis-parallel segments ((x1,y1),(x2,y2))."""
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    axl, axh, ayl, ayh = min(ax1, ax2), max(ax1, ax2), min(ay1, ay2), max(ay1, ay2)
    bxl, bxh, byl, byh = min(bx1, bx2), max(bx1, bx2), min(by1, by2), max(by1, by2)
    dx = max(0.0, bxl - axh, axl - bxh)
    dy = max(0.0, byl - ayh, ayl - byh)
    return math.hypot(dx, dy)


def _seg_rect_dist(s, r):
    """Distance from an axis-parallel segment to a rectangle (x0,y0,x1,y1); 0 if they meet."""
    (x1, y1), (x2, y2) = s
    xl, xh, yl, yh = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    dx = max(0.0, r[0] - xh, xl - r[2])
    dy = max(0.0, r[1] - yh, yl - r[3])
    return math.hypot(dx, dy)


def _rect_overlap(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


class Diagram(object):
    def __init__(self, w, h, size=SIZE):
        self.w, self.h, self.size = float(w), float(h), size
        self.blocks = []     # dict(name, kind, x, y, w, h, lines, ...)
        self.wires = []      # dict(net, pts, style, head)
        self.texts = []      # dict(x, y, s, ha, va, size, style, owner)

    # ------------------------------------------------------------ elements
    def box(self, name, x, y, w, h, text="", style="-", round_=False, bold=False, size=None, lw=LW, hatch=None):
        b = dict(name=name, kind="rect", x=x, y=y, w=w, h=h, style=style, round_=round_, lw=lw, hatch=hatch)
        self.blocks.append(b)
        if text:
            self.texts.append(dict(x=x + w / 2.0, y=y + h / 2.0, s=text, ha="center", va="center",
                                   size=size or self.size, bold=bold, italic=False, owner=name))
        return b

    def circle(self, name, cx, cy, r, text="", bold=False, size=None, lw=LW):
        b = dict(name=name, kind="circle", x=cx - r, y=cy - r, w=2 * r, h=2 * r, r=r, cx=cx, cy=cy,
                 style="-", lw=lw)
        self.blocks.append(b)
        if text:
            self.texts.append(dict(x=cx, y=cy, s=text, ha="center", va="center", size=size or self.size,
                                   bold=bold, italic=False, owner=name))
        return b

    def bar(self, name, x, y, w, h):
        """A pipeline register: a narrow hatched block."""
        return self.box(name, x, y, w, h, hatch="//////", lw=LW)

    def wire(self, net, pts, style="-", head=True):
        pts = [(float(a), float(b)) for a, b in pts]
        self.wires.append(dict(net=net, pts=pts, style=style, head=head))

    def text(self, x, y, s, ha="center", va="center", size=None, italic=False, bold=False):
        self.texts.append(dict(x=x, y=y, s=s, ha=ha, va=va, size=size or self.size, bold=bold,
                               italic=italic, owner=None))

    # ------------------------------------------------------------ geometry
    def segments(self):
        out = []
        for i, wr in enumerate(self.wires):
            for a, b in zip(wr["pts"][:-1], wr["pts"][1:]):
                out.append((i, wr["net"], (a, b)))
        return out

    def block_rect(self, b):
        return (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])

    def junctions(self):
        """Points where an end of one wire lands inside a segment of another wire of the same net."""
        dots = []
        segs = self.segments()
        for i, wr in enumerate(self.wires):
            for p in (wr["pts"][0], wr["pts"][-1]):
                for j, net, (a, b) in segs:
                    if j == i or net != wr["net"]:
                        continue
                    on = _seg_dist((p, p), (a, b)) < EPS
                    is_end = (abs(p[0] - a[0]) < EPS and abs(p[1] - a[1]) < EPS) or \
                             (abs(p[0] - b[0]) < EPS and abs(p[1] - b[1]) < EPS)
                    if on and not is_end and p not in dots:
                        dots.append(p)
        return dots

    # ------------------------------------------------------------ drawing
    def _render(self):
        fig = plt.figure(figsize=(self.w / 72.0, self.h / 72.0))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.h)
        ax.axis("off")
        dash = {"-": "-", "--": (0, (3.0, 2.0)), ":": (0, (0.8, 1.6))}
        for b in self.blocks:
            ls = dash[b["style"]]
            if b["kind"] == "circle":
                ax.add_patch(Circle((b["cx"], b["cy"]), b["r"], fc="white", ec="black", lw=b["lw"], ls=ls))
            elif b.get("round_"):
                ax.add_patch(FancyBboxPatch((b["x"], b["y"]), b["w"], b["h"],
                                            boxstyle="round,pad=0,rounding_size=4", fc="white", ec="black",
                                            lw=b["lw"], ls=ls))
            else:
                ax.add_patch(Rectangle((b["x"], b["y"]), b["w"], b["h"], fc="white", ec="black", lw=b["lw"],
                                       ls=ls, hatch=b.get("hatch")))
        for wr in self.wires:
            xs = [p[0] for p in wr["pts"]]
            ys = [p[1] for p in wr["pts"]]
            if wr["head"]:
                # stop the shaft at the base of the head so a dashed shaft does not poke through it
                (x1, y1), (x2, y2) = wr["pts"][-2], wr["pts"][-1]
                d = math.hypot(x2 - x1, y2 - y1)
                ux, uy = (x2 - x1) / d, (y2 - y1) / d
                xs[-1], ys[-1] = x2 - ux * HEAD_L * 0.9, y2 - uy * HEAD_L * 0.9
                bx, by = x2 - ux * HEAD_L, y2 - uy * HEAD_L
                ax.add_patch(Polygon([(x2, y2), (bx - uy * HEAD_W / 2, by + ux * HEAD_W / 2),
                                      (bx + uy * HEAD_W / 2, by - ux * HEAD_W / 2)], closed=True,
                                     fc="black", ec="black", lw=0.3))
            ax.plot(xs, ys, color="black", lw=LW, ls=dash[wr["style"]], solid_capstyle="butt",
                    dash_capstyle="butt", solid_joinstyle="miter")
        for p in self.junctions():
            ax.add_patch(Circle(p, 1.4, fc="black", ec="black", lw=0))
        arts = []
        for t in self.texts:
            a = ax.text(t["x"], t["y"], t["s"], ha=t["ha"], va=t["va"], fontsize=t["size"],
                        family=FONT, fontweight="bold" if t["bold"] else "normal",
                        style="italic" if t["italic"] else "normal", linespacing=1.1)
            arts.append(a)
        return fig, ax, arts

    def _text_rects(self, fig, ax, arts):
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        inv = ax.transData.inverted()
        out = []
        for a in arts:
            bb = a.get_window_extent(renderer=r)
            (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
            out.append((x0, y0, x1, y1))
        return out

    # ------------------------------------------------------------ rules
    def check(self, rects):
        errs = []
        segs = self.segments()
        # 2. orthogonal
        for i, net, (a, b) in segs:
            if abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS:
                errs.append("wire %s: diagonal segment %s-%s" % (net, a, b))
            if abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS:
                errs.append("wire %s: zero-length segment at %s" % (net, a))
        # 3. different nets never meet or run close
        for k in range(len(segs)):
            for m in range(k + 1, len(segs)):
                i, n1, s1 = segs[k]
                j, n2, s2 = segs[m]
                if n1 == n2:
                    continue
                d = _seg_dist(s1, s2)
                if d < EPS:
                    errs.append("wires %s and %s cross or touch near %s" % (n1, n2, s1[0]))
                elif d < GAP_LINE:
                    errs.append("wires %s and %s only %.1f pt apart near %s" % (n1, n2, d, s1[0]))
        # 4. wires do not pass through blocks (ends may sit on the outline)
        for i, net, (a, b) in segs:
            for bl in self.blocks:
                x0, y0, x1, y1 = self.block_rect(bl)
                inner = (x0 + 0.05, y0 + 0.05, x1 - 0.05, y1 - 0.05)
                if bl["kind"] == "circle":
                    # sample the segment
                    n = 40
                    for t in range(1, n):
                        px = a[0] + (b[0] - a[0]) * t / n
                        py = a[1] + (b[1] - a[1]) * t / n
                        if math.hypot(px - bl["cx"], py - bl["cy"]) < bl["r"] - 0.05:
                            errs.append("wire %s passes through %s" % (net, bl["name"]))
                            break
                elif _seg_rect_dist((a, b), inner) < EPS:
                    errs.append("wire %s passes through %s" % (net, bl["name"]))
        # wire ends must sit on a block outline, on another wire of the same net, or be marked free
        # 5. text clearance
        for t, r in zip(self.texts, rects):
            c = CLEAR + LW / 2.0          # white space measured from the edge of the drawn line
            pad = (r[0] - c, r[1] - c, r[2] + c, r[3] + c)
            label = t["s"].replace("\n", " ")[:30]
            if pad[0] < 0 or pad[1] < 0 or pad[2] > self.w or pad[3] > self.h:
                errs.append("text '%s' leaves the canvas" % label)
            for i, net, s in segs:
                if _seg_rect_dist(s, pad) < EPS:
                    errs.append("text '%s' touches wire %s" % (label, net))
            for bl in self.blocks:
                x0, y0, x1, y1 = self.block_rect(bl)
                if t["owner"] == bl["name"]:
                    if bl["kind"] == "circle":
                        for cx, cy in ((pad[0], pad[1]), (pad[0], pad[3]), (pad[2], pad[1]), (pad[2], pad[3])):
                            if math.hypot(cx - bl["cx"], cy - bl["cy"]) > bl["r"]:
                                errs.append("text '%s' touches the outline of %s" % (label, bl["name"]))
                                break
                    elif not (pad[0] > x0 and pad[1] > y0 and pad[2] < x1 and pad[3] < y1):
                        errs.append("text '%s' touches the outline of %s" % (label, bl["name"]))
                elif _rect_overlap(pad, (x0, y0, x1, y1)):
                    # text inside a larger block (e.g. a group frame) is allowed if it clears the outline
                    inside = pad[0] > x0 and pad[1] > y0 and pad[2] < x1 and pad[3] < y1
                    if not inside or bl.get("hatch"):
                        errs.append("text '%s' touches block %s" % (label, bl["name"]))
        for k in range(len(rects)):
            for m in range(k + 1, len(rects)):
                if _rect_overlap(rects[k], rects[m], CLEAR):
                    errs.append("texts '%s' and '%s' overlap" % (self.texts[k]["s"][:20], self.texts[m]["s"][:20]))
        # blocks may not overlap each other unless one contains the other (group frames)
        for k in range(len(self.blocks)):
            for m in range(k + 1, len(self.blocks)):
                a, b = self.block_rect(self.blocks[k]), self.block_rect(self.blocks[m])
                if _rect_overlap(a, b):
                    cont = (a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]) or \
                           (b[0] <= a[0] and b[1] <= a[1] and b[2] >= a[2] and b[3] >= a[3])
                    if not cont:
                        errs.append("blocks %s and %s overlap" % (self.blocks[k]["name"], self.blocks[m]["name"]))
        return errs

    def save(self, path, dpi=600):
        fig, ax, arts = self._render()
        errs = self.check(self._text_rects(fig, ax, arts))
        if errs:
            plt.close(fig)
            raise RuleError("%s breaks the drawing rules:\n  " % os.path.basename(path) + "\n  ".join(errs))
        fig.savefig(path + ".png", dpi=dpi)
        fig.savefig(path + ".svg")
        plt.close(fig)
        return os.path.basename(path)


def selftest():
    """Each broken drawing must be rejected; the clean one must pass."""
    bad = []
    d = Diagram(100, 60)
    d.box("a", 10, 10, 20, 20)
    d.wire("n", [(30, 20), (70, 40)])                       # diagonal
    bad.append(("diagonal", d))
    d = Diagram(100, 60)
    d.wire("n1", [(10, 30), (90, 30)])
    d.wire("n2", [(50, 10), (50, 50)])                      # crossing
    bad.append(("crossing", d))
    d = Diagram(100, 60)
    d.box("a", 40, 20, 20, 20)
    d.wire("n", [(10, 30), (90, 30)])                       # through a block
    bad.append(("through block", d))
    d = Diagram(100, 60)
    d.wire("n", [(10, 30), (90, 30)])
    d.text(50, 32, "label")                                 # text touches line
    bad.append(("text on line", d))
    d = Diagram(100, 60)
    d.box("a", 30, 20, 30, 14, "a long label")              # text touches outline
    bad.append(("text on outline", d))
    d = Diagram(100, 60)
    d.wire("n1", [(10, 30), (90, 30)])
    d.wire("n2", [(10, 31.5), (90, 31.5)])                  # too close
    bad.append(("too close", d))
    ok = True
    for name, dd in bad:
        fig, ax, arts = dd._render()
        e = dd.check(dd._text_rects(fig, ax, arts))
        plt.close(fig)
        print("diagram selftest %-16s %s" % (name, "caught" if e else "NOT caught"))
        ok &= bool(e)
    d = Diagram(120, 60)
    d.box("a", 10, 20, 30, 20, "A")
    d.box("b", 80, 20, 30, 20, "B")
    d.wire("n", [(40, 30), (80, 30)])
    d.text(60, 38, "data")
    fig, ax, arts = d._render()
    e = d.check(d._text_rects(fig, ax, arts))
    plt.close(fig)
    print("diagram selftest %-16s %s" % ("clean", "clean" if not e else "false alarm: %s" % e))
    return ok and not e


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
