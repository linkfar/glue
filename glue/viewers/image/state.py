from __future__ import absolute_import, division, print_function

from glue.core import Data
from glue.config import colormaps
from glue.viewers.matplotlib.state import (MatplotlibDataViewerState,
                                           MatplotlibLayerState,
                                           DeferredDrawCallbackProperty as DDCProperty,
                                           DeferredDrawSelectionCallbackProperty as DDSCProperty)
from glue.core.state_objects import StateAttributeLimitsHelper
from glue.utils import defer_draw
from glue.external.echo import delay_callback
from glue.core.data_combo_helper import ManualDataComboHelper, ComponentIDComboHelper

__all__ = ['ImageViewerState', 'ImageLayerState', 'ImageSubsetLayerState']


class ImageViewerState(MatplotlibDataViewerState):
    """
    A state class that includes all the attributes for an image viewer.
    """

    x_att = DDCProperty(docstring='The component ID giving the pixel component '
                                  'shown on the x axis')
    y_att = DDCProperty(docstring='The component ID giving the pixel component '
                                  'shown on the y axis')
    x_att_world = DDSCProperty(docstring='The component ID giving the world component '
                                         'shown on the x axis', default_index=-1)
    y_att_world = DDSCProperty(docstring='The component ID giving the world component '
                                         'shown on the y axis', default_index=-2)
    aspect = DDCProperty('equal', docstring='Whether to enforce square pixels (``equal``) '
                                            'or fill the axes (``auto``)')
    reference_data = DDSCProperty(docstring='The dataset that is used to define the '
                                            'available pixel/world components, and '
                                            'which defines the coordinate frame in '
                                            'which the images are shown')
    slices = DDCProperty(docstring='The current slice along all dimensions')
    color_mode = DDCProperty('Colormaps', docstring='Whether each layer can have '
                                                    'its own colormap (``Colormaps``) or '
                                                    'whether each layer is assigned '
                                                    'a single color (``One color per layer``)')

    def __init__(self, **kwargs):

        super(ImageViewerState, self).__init__()

        self.limits_cache = {}

        self.x_lim_helper = StateAttributeLimitsHelper(self, attribute='x_att',
                                                       lower='x_min', upper='x_max',
                                                       limits_cache=self.limits_cache)

        self.y_lim_helper = StateAttributeLimitsHelper(self, attribute='y_att',
                                                       lower='y_min', upper='y_max',
                                                       limits_cache=self.limits_cache)

        self.ref_data_helper = ManualDataComboHelper(self, 'reference_data')

        self.xw_att_helper = ComponentIDComboHelper(self, 'x_att_world',
                                                    numeric=False, categorical=False,
                                                    visible=False, world_coord=True)

        self.yw_att_helper = ComponentIDComboHelper(self, 'y_att_world',
                                                    numeric=False, categorical=False,
                                                    visible=False, world_coord=True)

        self.add_callback('reference_data', self._reference_data_changed, priority=1000)
        self.add_callback('layers', self._layers_changed, priority=1000)

        self.add_callback('x_att', self._on_xatt_change, priority=500)
        self.add_callback('y_att', self._on_yatt_change, priority=500)

        self.add_callback('x_att_world', self._update_att, priority=500)
        self.add_callback('y_att_world', self._update_att, priority=500)

        self.add_callback('x_att_world', self._on_xatt_world_change, priority=1000)
        self.add_callback('y_att_world', self._on_yatt_world_change, priority=1000)

        self.update_from_dict(kwargs)

    def _reference_data_changed(self, *args):
        with delay_callback(self, 'x_att_world', 'y_att_world', 'slices'):
            self._update_combo_att()
            self._set_default_slices()

    def _layers_changed(self, *args):
        self._update_combo_ref_data()
        self._set_reference_data()

    def _update_combo_ref_data(self, *args):
        datasets = []
        for layer in self.layers:
            if isinstance(layer.layer, Data):
                if layer.layer not in datasets:
                    datasets.append(layer.layer)
            else:
                if layer.layer.data not in datasets:
                    datasets.append(layer.layer.data)
        self.ref_data_helper.set_multiple_data(datasets)

    def _update_combo_att(self, *args):
        with delay_callback(self, 'x_att_world', 'y_att_world'):
            if self.reference_data is None:
                self.xw_att_helper.set_multiple_data([])
                self.yw_att_helper.set_multiple_data([])
            else:
                self.xw_att_helper.set_multiple_data([self.reference_data])
                self.yw_att_helper.set_multiple_data([self.reference_data])

    def _update_priority(self, name):
        if name == 'layers':
            return 3
        elif name == 'reference_data':
            return 2
        elif name.endswith(('_min', '_max')):
            return 0
        else:
            return 1

    @defer_draw
    def _update_att(self, *args):
        # Need to delay the callbacks here to make sure that we get a chance to
        # update both x_att and y_att otherwise could end up triggering image
        # slicing with two pixel components that are the same.
        with delay_callback(self, 'x_att', 'y_att'):
            if self.x_att_world is not None:
                index = self.reference_data.world_component_ids.index(self.x_att_world)
                self.x_att = self.reference_data.pixel_component_ids[index]
            if self.y_att_world is not None:
                index = self.reference_data.world_component_ids.index(self.y_att_world)
                self.y_att = self.reference_data.pixel_component_ids[index]

    @defer_draw
    def _on_xatt_change(self, *args):
        if self.x_att is not None:
            self.x_att_world = self.reference_data.world_component_ids[self.x_att.axis]

    @defer_draw
    def _on_yatt_change(self, *args):
        if self.y_att is not None:
            self.y_att_world = self.reference_data.world_component_ids[self.y_att.axis]

    @defer_draw
    def _on_xatt_world_change(self, *args):
        if self.x_att_world is not None and self.x_att_world == self.y_att_world:
            world_ids = self.reference_data.world_component_ids
            if self.x_att_world == world_ids[-1]:
                self.y_att_world = world_ids[-2]
            else:
                self.y_att_world = world_ids[-1]

    @defer_draw
    def _on_yatt_world_change(self, *args):
        if self.y_att_world is not None and self.y_att_world == self.x_att_world:
            world_ids = self.reference_data.world_component_ids
            if self.y_att_world == world_ids[-1]:
                self.x_att_world = world_ids[-2]
            else:
                self.x_att_world = world_ids[-1]

    def _set_reference_data(self, *args):
        # TODO: make sure this doesn't get called for changes *in* the layers
        # for list callbacks maybe just have an event for length change in list
        if self.reference_data is None:
            for layer in self.layers:
                if isinstance(layer.layer, Data):
                    self.reference_data = layer.layer
                    return

    def _set_default_slices(self, *args):
        # Need to make sure this gets called immediately when reference_data is changed
        if self.reference_data is None:
            self.slices = ()
        else:
            self.slices = (0,) * self.reference_data.ndim

    @property
    def numpy_slice_and_transpose(self):
        """
        Returns slicing information usable by Numpy.

        This returns two objects: the first is an object that can be used to
        slice Numpy arrays and return a 2D array, and the second object is a
        boolean indicating whether to transpose the result.
        """
        if self.reference_data is None:
            return None
        slices = []
        for i in range(self.reference_data.ndim):
            if i == self.x_att.axis or i == self.y_att.axis:
                slices.append(slice(None))
            else:
                slices.append(self.slices[i])
        transpose = self.y_att.axis > self.x_att.axis
        return slices, transpose

    @property
    def wcsaxes_slice(self):
        """
        Returns slicing information usable by WCSAxes.

        This returns an iterable of slices, and including ``'x'`` and ``'y'``
        for the dimensions along which we are not slicing.
        """
        if self.reference_data is None:
            return None
        slices = []
        for i in range(self.reference_data.ndim):
            if i == self.x_att.axis:
                slices.append('x')
            elif i == self.y_att.axis:
                slices.append('y')
            else:
                slices.append(self.slices[i])
        return slices[::-1]

    def flip_x(self):
        """
        Flip the x_min/x_max limits.
        """
        self.x_lim_helper.flip_limits()

    def flip_y(self):
        """
        Flip the y_min/y_max limits.
        """
        self.y_lim_helper.flip_limits()


class ImageLayerState(MatplotlibLayerState):
    """
    A state class that includes all the attributes for data layers in an image plot.
    """

    attribute = DDCProperty(docstring='The attribute shown in the layer')
    v_min = DDCProperty(docstring='The lower level shown')
    v_max = DDCProperty(docstring='The upper leven shown')
    percentile = DDCProperty(100, docstring='The percentile value used to '
                                            'automatically calculate levels')
    contrast = DDCProperty(1, docstring='The contrast of the layer')
    bias = DDCProperty(0.5, docstring='A constant value that is added to the '
                                      'layer before rendering')
    cmap = DDCProperty(docstring='The colormap used to render the layer')
    stretch = DDCProperty('linear', docstring='The stretch used to render the layer, '
                                              'whcih should be one of ``linear``, '
                                              '``sqrt``, ``log``, or ``arcsinh``')
    global_sync = DDCProperty(False, docstring='Whether the color and transparency '
                                               'should be synced with the global '
                                               'color and transparency for the data')

    def __init__(self, layer=None, **kwargs):

        super(ImageLayerState, self).__init__(layer=layer)

        self.attribute_helper = StateAttributeLimitsHelper(self, attribute='attribute',
                                                           percentile='percentile',
                                                           lower='v_min', upper='v_max')

        self.add_callback('global_sync', self._update_syncing)
        self.add_callback('layer', self._update_attribute)

        self._update_syncing()

        if layer is not None:
            self._update_attribute()

        self.update_from_dict(kwargs)

        if self.cmap is None:
            self.cmap = colormaps.members[0][1]

    def _update_attribute(self, *args):
        if self.layer is not None:
            self.attribute = self.layer.visible_components[0]

    def _update_priority(self, name):
        if name == 'layer':
            return 3
        elif name == 'attribute':
            return 2
        elif name == 'global_sync':
            return 1.5
        elif name.endswith(('_min', '_max')):
            return 0
        else:
            return 1

    def _update_syncing(self, *args):
        if self.global_sync:
            self._sync_color.enable_syncing()
            self._sync_alpha.enable_syncing()
        else:
            self._sync_color.disable_syncing()
            self._sync_alpha.disable_syncing()

    def flip_limits(self):
        """
        Flip the image levels.
        """
        self.attribute_helper.flip_limits()

    def reset_contrast_bias(self):
        with delay_callback(self, 'contrast', 'bias'):
            self.contrast = 1
            self.bias = 0.5


class ImageSubsetLayerState(MatplotlibLayerState):
    """
    A state class that includes all the attributes for subset layers in an image plot.
    """
