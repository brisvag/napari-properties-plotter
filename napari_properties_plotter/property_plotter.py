from contextlib import contextmanager

import napari
import pyqtgraph as pg
import numpy as np
import pandas as pd
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QComboBox, QLabel, QPushButton, QSpinBox, QCheckBox
from qtpy.QtCore import Signal

from .components import VariableWidget, LayerSelector
from .utils import Symbol, YStyle, XStyle, get_xstyle


class VariablePicker(QWidget):
    """
    Exposes the columns of a dataframe allowing to pick x and y variables
    as well as drawing styles, to be passed to a plotter widget
    """
    changed = Signal(int, pd.Series, YStyle, tuple, Symbol)
    removed = Signal(int)
    x_changed = Signal(pd.Series)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.df = None
        self.vars = []
        self._block_x_changed = False

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
        self.y_label = QLabel('Y axis:')
        self.vars_layout.addWidget(self.y_label)
        # button to add new row
        self.add_var_button = QPushButton('+')
        ly.addWidget(self.add_var_button)
        ly.addStretch()

        # events
        self.x_picker.currentTextChanged.connect(self._on_x_changed)
        self.add_var_button.clicked.connect(self.add_var)

    @property
    def x(self):
        """
        return current x data
        """
        return self.df.get(self.x_picker.currentText(), pd.Series())

    @property
    def xstyle(self):
        return get_xstyle(self.x)

    @contextmanager
    def block_x_changed(self):
        self._block_x_changed = True
        yield
        self._block_x_changed = False

    def set_dataframe(self, dataframe):
        """
        set a new dataframe and update contents accordingly
        """
        self.df = pd.DataFrame(dataframe)
        self.df.insert(0, 'index', self.df.index)  # easier if index is a column

        with self.block_x_changed():
            old_x_items = [self.x_picker.itemText(i) for i in range(self.x_picker.count())]
            current_x = self.x_picker.currentText()
            self.x_picker.clear()
            self.x_picker.addItems(self.df.columns)
            if current_x in old_x_items:
                self.x_picker.setCurrentText(current_x)
        self.x_changed.emit(self.x)

        # clean up what can't stay
        for var in list(self.vars):
            if var.prop not in self.df:
                var._on_remove()
            else:
                var._on_style_change()

    def add_var(self):
        """
        helper method to add a row to the widget from a dataframe column
        """
        var = VariableWidget(parent=self)
        self.vars_layout.addWidget(var)
        self.vars.append(var)

        var.changed.connect(self._on_var_changed)
        var.removed.connect(self._on_var_removed)
        # manually trigger change for initialization
        var._on_style_change()

    def _on_var_changed(self, var):
        """
        triggered when something regaring the property prop_name changed
        """
        idx = self.vars.index(var)
        self.changed.emit(idx,
                          self.df[var.prop],
                          var.ystyle,
                          var.color,
                          var.symbol)

    def _on_var_removed(self, var):
        idx = self.vars.index(var)
        self.vars.remove(var)
        self.removed.emit(idx)

    def _continuous_mode(self, enabled):
        self.add_var_button.setVisible(enabled)
        self.y_label.setVisible(enabled)

    def _on_x_changed(self):
        """
        triggered when the x value changed, requiring redrawing of all the properties
        """
        if self._block_x_changed:
            return
        if self.xstyle is XStyle.continuous:
            for ps in self.vars:
                ps._on_style_change()
            self._continuous_mode(True)
        elif self.xstyle is XStyle.categorical:
            for var in list(self.vars):
                # remove all the variables and grey out the add button
                var._on_remove()
            self._continuous_mode(False)
        self.x_changed.emit(self.x)


class PyQtGraphWrapper(pg.GraphicsLayoutWidget):
    """
    wrapper of GraphicsLayoutWidget with convenience methods for plotting
    based on signals fired by VariablePicker
    """
    continuous = Signal(bool)
    binned = Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plotter = pg.PlotItem()
        self.plotter.addLegend()
        self.addItem(self.plotter)
        self.plots = []
        self._x = None
        self._single_plot = None
        self._bins = 10

    @property
    def x(self):
        return self._x

    @property
    def xstyle(self):
        return get_xstyle(self.x)

    def set_x(self, value):
        previous_style = get_xstyle(self.x)
        if previous_style is XStyle.categorical:
            self.reset()

        self._x = value
        self.plotter.setLabel(axis='bottom', text=value.name)

        if get_xstyle(value) is XStyle.categorical:
            self.plot_categorical()
        else:
            ax = self.plotter.getAxis('bottom')
            ax.setTicks(None)
            if not self.plots:
                self.plot_binned()

    def plot_categorical(self):
        unique, counts = np.unique(self.x, return_counts=True)
        x = np.arange(len(unique))
        plot = pg.BarGraphItem(x=x, height=counts, width=0.5)
        self.set_single(plot)
        self.continuous.emit(False)
        self.binned.emit(False)
        ax = self.plotter.getAxis('bottom')
        ax.setTicks([enumerate(unique)])

    def plot_binned(self):
        if self.x.dtype == float and np.any(np.isnan(self.x)):
            self.reset()
            self.continuous.emit(False)
            return
        y, edges = np.histogram(self.x, bins=self._bins)
        left_edges = edges[:-1]
        right_edges = edges[1:]
        plot = pg.BarGraphItem(x0=left_edges, x1=right_edges, height=y)
        self.set_single(plot)
        # ax = self.plotter.getAxis('bottom')
        # ax.setTicks()
        self.continuous.emit(True)
        self.binned.emit(True)

    def update(self, idx, y, ystyle, color, symbol):
        self.remove_single()
        symbol = symbol.value
        if ystyle is YStyle.scatter:
            plot = self.make_scatter(y, color, symbol)
        elif ystyle is YStyle.line:
            plot = self.make_line(y, color)
        elif ystyle is YStyle.bar:
            plot = self.make_bars(y, color)

        self.replace(idx, plot)

        self.plotter.autoRange()
        self.continuous.emit(True)
        self.binned.emit(False)

    def make_scatter(self, y, color, symbol):
        return self.plotter.plot(self.x, y, name=y.name, symbol=symbol, symbolBrush=color, pen=None)

    def make_line(self, y, color):
        return self.plotter.plot(self.x, y, name=y.name, pen=color)

    def make_bars(self, y, color):
        pass

    def _remove(self, idx):
        try:
            plot = self.plots.pop(idx)
            self.plotter.removeItem(plot)
        except IndexError:
            # it means we're appending a new plot
            pass

    def remove(self, idx):
        self._remove(idx)
        if not self.plots:
            self.plot_binned()
        else:
            self.plotter.autoRange()

    def set_single(self, plot):
        self.reset()
        self._single_plot = plot
        self.plotter.addItem(plot)
        self.plotter.autoRange()

    def set_binning(self, bins):
        self._bins = bins
        if self._single_plot is not None and self.xstyle is XStyle.continuous:
            self.plot_binned()

    def remove_single(self):
        if self._single_plot is not None:
            self.plotter.removeItem(self._single_plot)
            self._single_plot = None

    def replace(self, idx, plot):
        self._remove(idx)
        self.plots.insert(idx, plot)
        self.plotter.autoRange()

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
            if self.sele is not None:
                self.sele.sigRegionChangeFinished.disconnect()
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

    def toggle_enabled(self, enabled):
        self.toggle.setVisible(enabled)
        if not enabled:
            self.toggle_selection(False)


class BinningSpinbox(QWidget):
    def __init__(self, plot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot = plot
        ly = QGridLayout()
        # remove annoying padding
        ly.setContentsMargins(0, 0, 0, 0)
        self.setLayout(ly)

        self.label = QLabel('Binning:')
        ly.addWidget(self.label, 0, 0)

        self.auto = QCheckBox('auto', checked=False)
        ly.addWidget(self.auto, 0, 1)

        self.spinbox = QSpinBox()
        ly.addWidget(self.spinbox, 1, 0, 1, 2)
        self.spinbox.setRange(1, 100000)
        self.spinbox.setValue(10)

        self.spinbox.valueChanged.connect(self._on_binning_change)
        self.auto.clicked.connect(self._on_auto_change)

        self.auto.click()

    def _on_binning_change(self):
        self.plot.set_binning(self.spinbox.value())

    def _on_auto_change(self, checked):
        self.spinbox.setVisible(not checked)
        if checked:
            self.plot.set_binning('auto')
        else:
            self._on_binning_change()


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

        self.binning_spinbox = BinningSpinbox(self.plot, self)
        self.left.addWidget(self.binning_spinbox)

        # events
        self.layer_selector.changed.connect(self.on_layer_changed)

        self.plot.continuous.connect(self.data_selector.toggle_enabled)
        self.plot.binned.connect(self.binning_spinbox.setVisible)

        self.picker.changed.connect(self.plot.update)
        self.picker.removed.connect(self.plot.remove)
        self.picker.x_changed.connect(self.plot.set_x)

        self.data_selector.new_selection.connect(self.on_selection_changed)
        self.data_selector.abort_selection.connect(self.on_selection_changed)

        # trigger first time
        self.on_layer_changed(self.layer_selector.layer)

    def on_layer_changed(self, layer):
        # disable selection
        self.data_selector.toggle.setChecked(False)
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
