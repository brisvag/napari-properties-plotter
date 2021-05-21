import napari_properties_plotter


def test_plotter_widget(make_napari_viewer, napari_plugin_manager):
    napari_plugin_manager.register(napari_properties_plotter, 'napari-properties-plotter')
    viewer = make_napari_viewer()
    widget = viewer.window.add_plugin_dock_widget(
        plugin_name='napari-properties-plotter', widget_name='Property Plotter'
    )[1]
    assert isinstance(widget, napari_properties_plotter.PropertyPlotter)
    assert widget.layer_selector.layer is None
    pl = viewer.add_points()
    assert widget.layer_selector.layer is pl
