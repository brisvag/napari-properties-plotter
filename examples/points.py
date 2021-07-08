#!/usr/bin/env python3

import pandas as pd
import numpy as np
import napari

from napari_properties_plotter import PropertyPlotter


points1 = np.random.rand(100, 2) * 200
properties1 = pd.DataFrame({
    'a': np.random.rand(100) * 20,
    'b': np.sin(np.linspace(0, 10, 100)) * 10,
    'c': np.random.choice(['red', 'green', 'blue'], 100),
    'd': np.nan,
})

points2 = np.random.rand(50, 2) * 200
properties2 = pd.DataFrame({
    'a': np.random.rand(50) * 20,
    'b': np.cos(np.linspace(0, 10, 50)) * 10,
    'c': np.random.choice(['red', 'green', 'blue'], 50),
    'd': np.nan,
})

v = napari.Viewer()
l1 = v.add_points(points1, properties=properties1)
l1 = v.add_points(points2, properties=properties2)

pp = PropertyPlotter(v)
v.window.add_dock_widget(pp, area='bottom')

napari.run()
