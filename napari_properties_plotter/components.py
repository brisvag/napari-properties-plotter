from qtpy.QtWidgets import QWidget, QComboBox, QPushButton, QHBoxLayout
from qtpy.QtCore import Signal, Qt

from .utils import Symbol, distinct_colors, YStyle, ystyle_map


class LayerSelector(QComboBox):
    """
    combobox for selecting a napari layer
    """
    changed = Signal(object)

    def __init__(self, layerlist, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layerlist = layerlist

        self.layerlist.events.inserted.connect(self.on_add_layer)
        self.layerlist.events.removed.connect(self.on_remove_layer)
        self.currentTextChanged.connect(self.on_layer_selection)

        self.addItems(layer.name for layer in self.layerlist
                      if hasattr(layer, 'properties'))

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
        if self.layer is not None:
            self.layer.events.data.connect(self.on_data_change)
            # TODO: disconnect previous layers?
        self.changed.emit(self.layer)

    def on_data_change(self, event):
        self.changed.emit(self.layer)


class VariableWidget(QWidget):
    changed = Signal(object)
    removed = Signal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._init_ui()

        self.prop_box.currentTextChanged.connect(self._on_prop_change)
        self.style_box.currentTextChanged.connect(self._on_style_change)
        self.remove_button.clicked.connect(self._on_remove)

        self._init_props()

    def _init_ui(self):
        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)  # remove annoying padding
        self.setLayout(ly)
        self.remove_button = QPushButton('-', self)
        self.remove_button.setMinimumWidth(25)
        ly.addWidget(self.remove_button)
        self.prop_box = QComboBox(self)
        self.prop_box.setMinimumWidth(70)
        ly.addWidget(self.prop_box)
        self.style_box = QComboBox(self)
        self.style_box.setMinimumWidth(70)
        ly.addWidget(self.style_box)

    def _init_props(self):
        self.prop_box.addItems(self.parent().df.columns)

    @property
    def prop(self):
        return self.prop_box.currentText()

    @property
    def ystyle(self):
        return YStyle[self.style_box.currentText()]

    @property
    def color(self):
        idx = self._get_prop_idx(self.prop)
        color = distinct_colors[idx % len(distinct_colors)]
        return color

    @property
    def symbol(self):
        idx = self._get_prop_idx(self.prop)
        symbols = list(Symbol)
        symbol = Symbol(symbols[idx % len(symbols)])
        return symbol

    def _get_prop_idx(self, prop_name):
        # get unique identifier for this property/column
        return self.parent().df.columns.get_loc(prop_name)

    def _on_prop_change(self, prop_name):
        self.style_box.blockSignals(True)
        self.style_box.clear()
        self.style_box.blockSignals(False)

        available_styles = []
        for dt, styles in ystyle_map.items():
            if dt == self.parent().df[prop_name].dtype:
                available_styles.extend(style.name for style in styles)
        self.style_box.addItems(available_styles)

        if not styles:
            self.style_box.setDisabled(True)

    def _on_style_change(self):
        self.changed.emit(self)

    def _on_remove(self):
        self.removed.emit(self)
        self.deleteLater()
