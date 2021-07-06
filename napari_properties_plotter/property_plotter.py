#!/usr/bin/env python3

import napari
import pyqtgraph as pg
import numpy as np
import pandas as pd
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QLabel, QPushButton
from qtpy.QtCore import Signal

from .components import VariableWidget, LayerSelector
from .utils import Symbol, YStyle, xstyle_map


class VariablePicker(QWidget):
    """
    Exposes the columns of a dataframe allowing to pick x and y variables
    as well as drawing styles, to be passed to a plotter widget
    """
    changed = Signal(int, pd.Series, pd.Series, YStyle, tuple, Symbol)
    removed = Signal(int)
    reset = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.df = None
        self.vars = []

        # set up ui
        ly = QVBoxLayout()
        self.setLayout(ly)
        ly.setContentsMargins(0, 0, 0, 0)  # remove annoying padding
        # grid used for picked_columns
        self.vars_layout = QVBoxLayout()
        ly.addLayout(self.vars_layout)
        # grid setup
        self.vars_layout.addWidget(QLabel('X axis:'))
        self.x_picker = QComboBox(self)
        self.vars_layout.addWidget(self.x_picker)
        self.x_picker.currentTextChanged.connect(self._reset)
        self.vars_layout.addWidget(QLabel('Y axis:'))
        # button to add new row
        self.add_var_button = QPushButton('+')
        ly.addWidget(self.add_var_button)
        ly.addStretch()

        # events
        self.add_var_button.clicked.connect(self.add_var)

    @property
    def x(self):
        """
        return current x data
        """
        return self.df[self.x_picker.currentText()]

    @property
    def xstyle(self):
        dtype = object
        for dt, styles in xstyle_map.items():
            if dt == self.x.dtype:
                dtype = dt
        return xstyle_map[dtype]

    def set_dataframe(self, dataframe):
        """
        set a new dataframe and update contents accordingly
        """
        self.df = pd.DataFrame(dataframe)
        self.df.insert(0, 'index', self.df.index)  # easier if index is a column
        # clean up (x later, otherwise it triggers a reset and breaks)
        for var in list(self.vars):
            var._on_remove()
        self.x_picker.clear()
        self.x_picker.addItems(self.df.columns)

    def add_var(self):
        """
        helper method to add a row to the widget from a dataframe column
        """
        ps = VariableWidget(parent=self)
        self.vars_layout.addWidget(ps)
        self.vars.append(ps)

        ps.changed.connect(self._on_var_changed)
        ps.removed.connect(self._on_var_removed)
        # manually trigger change for initialization
        ps._on_style_change()

    def _on_var_changed(self, var):
        """
        triggered when something regaring the property prop_name changed
        """
        idx = self.vars.index(var)
        self.changed.emit(idx,
                          self.x,
                          self.df[var.prop],
                          var.ystyle,
                          var.color,
                          var.symbol)

    def _on_var_removed(self, var):
        idx = self.vars.index(var)
        self.vars.remove(var)
        self.removed.emit(idx)

    def _reset(self):
        """
        triggered when the x value changed, requiring redrawing of all the properties
        """
        self.reset.emit()
        for ps in self.vars:
            ps._on_style_change()


class PyQtGraphWrapper(pg.GraphicsLayoutWidget):
    """
    wrapper of GraphicsLayoutWidget with convenience methods for plotting
    based on signals fired by VariablePicker
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plotter = pg.PlotItem()
        self.plotter.addLegend()
        self.addItem(self.plotter)
        self.plots = []
        self._x_style = None

    @property
    def x_style(self):
        return self._x_style

    @x_style.setter
    def x_style(self, value):
        self._x_style = value
        self.reset()

    def update(self, idx, x, y, ystyle, color, symbol):
        symbol = symbol.value
        if ystyle is YStyle.scatter:
            plot = self.make_scatter(x, y, color, symbol)
        elif ystyle is YStyle.line:
            plot = self.make_line(x, y, color)
        elif ystyle is YStyle.bar:
            plot = self.make_bars(x, y, color)

        self.replace(idx, plot)

        self.plotter.autoRange()

    def make_scatter(self, x, y, color, symbol):
        return self.plotter.plot(x, y, name=y.name, symbol=symbol, symbolBrush=color, pen=None)

    def make_line(self, x, y, color):
        return self.plotter.plot(x, y, name=y.name, pen=color)

    def make_bars(self, x, y, color):
        pass

    def remove(self, idx):
        try:
            plot = self.plots.pop(idx)
            self.plotter.removeItem(plot)
            self.plotter.autoRange()
        except IndexError:
            # it means we're appending a new plot
            pass

    def replace(self, idx, plot):
        self.remove(idx)
        self.plots.insert(idx, plot)

    def reset(self):
        self.plotter.clear()


class DataSelector(QWidget):
    """
    Simple button to create and hold information about a selection area
    in a pyqtgraph.PlotItem object
    """
    new_selection = Signal(float, float)
    abort_selection = Signal()

    def __init__(self, plotitem, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot = plotitem
        self.sele = None

        self.setLayout(QHBoxLayout())
        # remove annoying padding
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.toggle = QPushButton(self)
        self.toggle.setText('Select Area')
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)

        self.layout().addWidget(self.toggle)

        self.toggle.toggled.connect(self.toggle_selection)

    def toggle_selection(self, activated):
        if activated:
            self.toggle.setText('Stop Selecting')
            sele = pg.LinearRegionItem()
            sele.sigRegionChangeFinished.connect(self.on_selection_changed)
            self.sele = sele
            self.plot.addItem(sele)
        else:
            self.toggle.setText('Select Area')
            self.plot.removeItem(self.sele)
            self.sele = None
            self.on_selection_changed(None)

    def on_selection_changed(self, region_changed):
        if region_changed is None:
            self.abort_selection.emit()
        else:
            left = region_changed._bounds.left()
            right = region_changed._bounds.right()
            self.new_selection.emit(left, right)


class PropertyPlotter(QWidget):
    """
    Napari widget that plots layer properties
    """
    def __init__(self, viewer: 'napari.viewer.Viewer', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = viewer

        # buttons
        self.setLayout(QHBoxLayout())
        self.left = QVBoxLayout()
        self.layout().addLayout(self.left)

        self.left.addWidget(QLabel('Layer:'))
        self.layer_selector = LayerSelector(self.viewer.layers)
        self.left.addWidget(self.layer_selector)

        self.picker = VariablePicker(self)
        self.left.addWidget(self.picker)

        # plot
        self.plot = PyQtGraphWrapper(self)
        self.layout().addWidget(self.plot)

        self.data_selector = DataSelector(self.plot.plotter, self)
        self.left.addWidget(self.data_selector)

        # events
        self.layer_selector.changed.connect(self.on_layer_changed)

        self.picker.changed.connect(self.plot.update)
        self.picker.removed.connect(self.plot.remove)
        self.picker.reset.connect(self.plot.reset)

        self.data_selector.new_selection.connect(self.on_selection_changed)

        # trigger first time
        self.on_layer_changed(self.layer_selector.layer)

    def on_layer_changed(self, layer):
        self.plot.reset()
        properties = getattr(layer, 'properties', {})
        self.picker.set_dataframe(properties)

    def on_selection_changed(self, start=None, end=None):
        layer = self.layer_selector.layer
        if layer is None:
            return
        elif start is None or end is None:
            layer.selected_data.clear()
        else:
            x_prop = self.picker.x
            idx = np.where(np.logical_and(start <= x_prop, x_prop <= end))[0]
            layer.selected_data = idx
