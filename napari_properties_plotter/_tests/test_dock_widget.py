from napari_properties_plotter._dock_widget import PropertyPlotter


def test_plotter_widget(make_napari_viewer):
    viewer = make_napari_viewer()
    num_dw = len(viewer.window._dock_widgets)
    widget = viewer.window.add_plugin_dock_widget(
        plugin_name='napari-properties-plotter', widget_name='Property Plotter'
    )
    assert isinstance(widget, PropertyPlotter)
    assert len(viewer.window._dock_widgets == num_dw + 1)
    assert widget.layer_selector.layer is None
    pl = viewer.add_points()
    assert widget.layer_selector.layer is pl
