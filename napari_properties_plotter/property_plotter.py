#!/usr/bin/env python3

import napari
import pyqtgraph as pg
import numpy as np
import pandas as pd
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QComboBox, QLabel, QCheckBox, QPushButton
from qtpy.QtCore import Qt, Signal

from .utils import distinct_colors, pqtg_symbols


class LayerSelector(QComboBox):
    """
    combobox for selecting a napari layer
    """
    changed = Signal(object)

    def __init__(self, layerlist, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layerlist = layerlist

        self.addItems(layer.name for layer in self.layerlist
                      if hasattr(layer, 'properties'))

        self.layerlist.events.inserted.connect(self.on_add_layer)
        self.layerlist.events.removed.connect(self.on_remove_layer)
        self.currentTextChanged.connect(self.on_layer_selection)

    @property
    def layer(self):
        layer_name = self.currentText()
        if not layer_name:
            return None
        return self.layerlist[layer_name]

    def on_add_layer(self, event):
        layer = event.value
        if hasattr(layer, 'properties'):
            self.addItem(layer.name)

    def on_remove_layer(self, event):
        layer = event.value

        index = self.findText(layer.name, Qt.MatchExactly)
        if index != -1:
            self.removeItem(index)

    def on_layer_selection(self, layer_name):
        self.changed.emit(self.layer)


class DataFramePicker(QWidget):
    """
    Exposes the columns of a dataframe allowing to pick x and y variables
    as well as drawing styles, to be passed to a plotter widget
    """
    style_map = {
        float: ('scatter', 'line'),
        int: ('scatter', 'line'),
    }
    activated = Signal(object, object, str, int)
    deactivated = Signal(str)
    reset = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.df = None
        self.rows = {}

        self.setLayout(QVBoxLayout())
        # remove annoying padding
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.grid = QGridLayout()
        self.layout().addLayout(self.grid)
        self.layout().addStretch()

        self.grid.addWidget(QLabel('X axis:'), 0, 0)
        self.x_picker = QComboBox(self)
        self.grid.addWidget(self.x_picker, 1, 0)
        self.x_picker.currentTextChanged.connect(self._reset)

        self.grid.addWidget(QLabel('Y axis:'), 2, 0)

    def set_dataframe(self, dataframe):
        """
        set a new dataframe and update contents accordingly
        """
        self.df = pd.DataFrame(dataframe)
        self.df.insert(0, 'index', self.df.index)  # easier if index is a column
        # clean up (x later, otherwise it triggers a reset and breaks)
        for prop in list(self.rows):
            self.remove_row(prop)
        self.rows.clear()
        self.x_picker.clear()

        for colname, col in self.df.items():
            if any(col.dtype == dt for dt in self.style_map):
                self.x_picker.addItem(colname)

        for col in self.df.columns:
            self.add_row(col)

    def add_row(self, prop_name):
        """
        helper method to add a row to the widget from a dataframe column
        """
        available_styles = []
        for dt, styles in self.style_map.items():
            if dt == self.df[prop_name].dtype:
                available_styles.extend(styles)
        if not available_styles:
            return

        active = QCheckBox(prop_name, self)
        style = QComboBox(self)
        style.addItems(styles)

        idx = len(self.rows)
        qt_row = idx + 3
        self.grid.addWidget(active, qt_row, 0)
        self.grid.addWidget(style, qt_row, 1)
        self.rows[prop_name] = (active, style, idx)

        active.clicked.connect(lambda: self._changed(prop_name))
        style.currentTextChanged.connect(lambda: self._changed(prop_name))

    def remove_row(self, prop_name):
        """
        remove a widget row and delete its widgets
        """
        active, style, idx = self.rows.pop(prop_name)
        active.deleteLater()
        style.deleteLater()

    @property
    def x(self):
        """
        return current x data
        """
        return self.df[self.x_picker.currentText()]

    def _changed(self, prop_name):
        """
        triggered when something regaring the property prop_name changed
        """
        active, style, idx = self.rows[prop_name]
        if active.isChecked():
            self.activated.emit(self.x, self.df[prop_name], style.currentText(), idx)
        else:
            self.deactivated.emit(prop_name)

    def _reset(self):
        """
        triggered when the x value changed, requiring redrawing of all the properties
        """
        self.reset.emit()
        for prop_name in self.rows:
            self._changed(prop_name)


class PyQtGraphWrapper(pg.GraphicsLayoutWidget):
    """
    wrapper of GraphicsLayoutWidget with convenience methods for plotting
    based on signals fired by DataFramePicker
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot = pg.PlotItem()
        self.plot.addLegend()
        self.addItem(self.plot)

    def update(self, x, y, style, idx):
        self.remove(y.name)
        color, symbol = self.get_line_style(idx)

        if style == 'scatter':
            self.make_scatter(x, y, color, symbol)
        elif style == 'line':
            self.make_line(x, y, color)

        self.plot.autoRange()

    def make_scatter(self, x, y, color, symbol):
        self.plot.plot(x, y, name=y.name, symbol=symbol, symbolBrush=color, pen=None)

    def make_line(self, x, y, color):
        self.plot.plot(x, y, name=y.name, pen=color)

    def get_line_style(self, idx):
        color = distinct_colors[idx % len(distinct_colors)]
        symbol = pqtg_symbols[idx % len(pqtg_symbols)]
        return color, symbol

    def remove(self, name):
        for item in self.plot.items:
            if hasattr(item, 'name') and item.name() == name:
                self.plot.removeItem(item)
                self.plot.autoRange()

    def reset(self):
        self.plot.clear()


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

        self.picker = DataFramePicker(self)
        self.left.addWidget(self.picker)

        # plot
        self.plot = PyQtGraphWrapper(self)
        self.layout().addWidget(self.plot)

        self.data_selector = DataSelector(self.plot.plot, self)
        self.left.addWidget(self.data_selector)

        # events
        self.layer_selector.changed.connect(self.on_layer_changed)

        self.picker.activated.connect(self.plot.update)
        self.picker.deactivated.connect(self.plot.remove)
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
