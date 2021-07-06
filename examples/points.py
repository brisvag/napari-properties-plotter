#!/usr/bin/env python3

import pandas as pd
import numpy as np
import napari

from napari_properties_plotter import PropertyPlotter


points = np.random.rand(100, 2) * 200
properties = pd.DataFrame({
    'a': np.random.rand(100) * 20,
    'b': np.sin(np.linspace(0, 10, 100)),
    'c': np.random.choice(['red', 'green', 'blue'], 100),
})

v = napari.Viewer()
v.add_points(points, properties=properties)
plotter = PropertyPlotter(v)
v.window.add_dock_widget(plotter, area='bottom')

napari.run()
