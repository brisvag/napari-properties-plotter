from enum import Enum, auto


class Symbol(Enum):
    dot = 'o'
    triangle_down = 't'
    triangle_up = 't1'
    triangle_right = 't2'
    triangle_left = 't3'
    square = 's'
    pentagon = 'p'
    hexagon = 'h'
    star = 'star'
    plus = '+'
    prism = 'd'
    cross = 'x'


# n+1 colors compared to symbols, so we get many combinations easily
distinct_colors = (
    (230,  25,  75),
    ( 60, 180,  75),
    (255, 225,  25),
    (  0, 130, 200),
    (245, 130,  48),
    (145,  30, 180),
    ( 70, 240, 240),
    (240,  50, 230),
    (210, 245,  60),
    (250, 190, 212),
    (  0, 128, 128),
    (220, 190, 255),
) # noqa


class XStyle(Enum):
    continuous = auto()
    categorical = auto()


class YStyle(Enum):
    line = auto()
    scatter = auto()
    bar = auto()
    off = auto()


ystyle_map = {
    float: (YStyle.scatter, YStyle.line),
    int: (YStyle.scatter, YStyle.line),
    object: (YStyle.bar,),
}

xstyle_map = {
    float: XStyle.continuous,
    int: XStyle.continuous,
    object: XStyle.categorical,
}


def get_xstyle(series):
    dtype = object
    if series is None:
        return dtype
    for dt, styles in xstyle_map.items():
        if dt == series.dtype:
            dtype = dt
    return xstyle_map[dtype]
