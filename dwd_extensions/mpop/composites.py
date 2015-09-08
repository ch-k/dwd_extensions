'''
Created on 05.01.2015

@author: Christian Kliche <chk@ebp.de>
'''
import numpy as np
import logging

import mpop.imageo.geo_image as geo_image  # @UnresolvedImport
from mpop.channel import Channel  # @UnresolvedImport

try:
    from pyorbital.astronomy import sun_zenith_angle as sza
except ImportError:
    sza = None


class Enum(set):

    def __getattr__(self, attr):
        if attr in self:
            return attr
        raise AttributeError


LOGGER = logging.getLogger(__name__)
# conversion factor K<->C
CONVERSION = 273.15
# sun zenith angle limit for the day (<)
SUN_ZEN_DAY_LIMIT = 85
# sun zenith angle limit for the night (>)
SUN_ZEN_NIGHT_LIMIT = 87

IMAGETYPES = Enum(('DAY_ONLY', 'NIGHT_ONLY', 'DAY_NIGHT'))


def _dwd_create_single_channel_image(self, chn):
    """Creates a calibrated and corrected single channel black/white image.
    Data calibration:
    HRV, VIS channels: albedo 0 - 125 %
    IR channels: temperature -87.5 - +40 C
    Data correction:
    HRV, VIS channels: sun zenith angle correction
    IR channels: atmospheric correction (not implemented yet)
    """
    if not isinstance(chn, basestring):
        return None

    self.check_channels(chn)

    # apply calibrations and corrections on channels
    if not self._dwd_channel_preparation(chn):
        return None

    if self._is_solar_channel(chn):
        return geo_image.GeoImage(self[chn].data,
                                  self.area,
                                  self.time_slot,
                                  fill_value=0,
                                  mode="L",
                                  crange=(0, 125))

    return geo_image.GeoImage(self[chn].data,
                              self.area,
                              self.time_slot,
                              fill_value=0,
                              mode="L",
                              crange=(40, -87.5))


def _dwd_apply_sun_zenith_angle_correction(self, chn):
    """Apply sun zenith angle correction on solar channel data.
    """
    if self._is_solar_channel(chn) and \
            self[chn].info.get("sun_zen_corrected", None) is None:
        if self.area.lons is None or self.area.lats is None:
            self.area.lons, self.area.lats = self.area.get_lonlats()
        sun_zen_chn = self[chn].sunzen_corr(self.time_slot, limit=85.)
        self[chn].data = sun_zen_chn.data.copy()
        del(sun_zen_chn)


def _dwd_apply_view_zenith_angle_correction(self, chn):
    """Apply view zenith angle correction on non solar channel data.
    """
    if not self._is_solar_channel(chn) and \
            self[chn].info.get("view_zen_corrected", None) is None:
        view_zen_chn_data = self[self.area.name + "_VZA"].data
        if view_zen_chn_data is not None:
            view_zen_corr_chn = self[chn].viewzen_corr(view_zen_chn_data)
            self[chn].data = view_zen_corr_chn.data.copy()
            del(view_zen_corr_chn)
        else:
            LOGGER.error("Missing satellite zenith angle data: " +
                         "atmospheric correction not possible.")


def _dwd_kelvin_to_celsius(self, chn):
    """Apply Kelvin to Celsius conversion on infrared channels.
    """
    if not self._is_solar_channel(chn) and \
            (self[chn].info['units'] == 'K' or self[chn].unit == 'K'):
        self[chn].data -= CONVERSION
        self[chn].info['units'] = self[chn].unit = 'C'


def _is_solar_channel(self, chn):
    """Checks whether the wave length of the given channel corresponds
    to solar wave length.
    Returns true if the given channel is a visual one; false otherwise.
    """
    return self[chn].wavelength_range[2] < 4 or chn in[
        'HRV', 'VIS006', 'VIS008', 'IR_016']


def _dwd_channel_preparation(self, *chn):
    """Applies to the given channels DWD specific calibrations and corrections.
    Returns True if the calculations were successful; False otherwise.
    """
    result = True

    for c in chn:
        self._dwd_apply_sun_zenith_angle_correction(c)
        self._dwd_apply_view_zenith_angle_correction(c)
        self._dwd_kelvin_to_celsius(c)
        if self[c].info['units'] != 'C' and self[c].info['units'] != '%':
            result = False
            LOGGER.error(
                "Calibration for channel " + str(c) +
                " failed due to unknown unit " + self[c].info['units'])
    return result


def _dwd_get_sun_zenith_angles_channel(self):
    """Returns the sun zenith angles for the area of interest as a channel.
    """
    LOGGER.info('Retrieve sun zenith angles')
    try:
        self.check_channels("SUN_ZEN_CHN")
        if self["SUN_ZEN_CHN"].data.shape != self.area.shape:
            self._data_holder.channels.remove(self["SUN_ZEN_CHN"])
            raise Exception()
    except:
        if self.area.lons is None or self.area.lats is None:
            self.area.lons, self.area.lats = self.area.get_lonlats()
        sun_zen_chn_data = np.zeros(shape=self.area.lons.shape)
        q = 500
        for start in xrange(0, sun_zen_chn_data.shape[1], q):
            sun_zen_chn_data[
                :, start: start + q] = sza(
                self.time_slot, self.area.lons[:, start: start + q],
                self.area.lats[:, start: start + q])
        sun_zen_chn = Channel(name="SUN_ZEN_CHN",
                              data=sun_zen_chn_data)
        self._data_holder.channels.append(sun_zen_chn)

    return self["SUN_ZEN_CHN"]


def _dwd_get_hrvc_channel(self):
    """Returns the combination of HRV and VIS008 channel data
    if there are gaps in HRV data; otherwise HRV only.
    """
    if np.ma.is_masked(self["HRV"].data):
        try:
            self.check_channels("HRVC")
            if self["HRVC"].data.shape != self.area.shape:
                self._data_holder.channels.remove(self["HRVC"])
                raise Exception()
            hrvc_chn = self["HRVC"]
        except:
            hrv_chn = self["HRV"]
            hrvc_data = np.ma.where(
                hrv_chn.data.mask, self[0.85].data, hrv_chn.data)
            hrvc_chn = Channel(name="HRVC",
                               resolution=hrv_chn.resolution,
                               wavelength_range=hrv_chn.wavelength_range,
                               data=hrvc_data,
                               calibration_unit=hrv_chn.unit)
            self._data_holder.channels.append(hrvc_chn)
    else:
        hrvc_chn = self["HRV"]

    return hrvc_chn


def _dwd_get_alpha_channel(self):
    """Returns the alpha values depending on the sun zenith angles.
    Lower angles result in lower alpha values
    so this data has to be inverted for the day image.
    """
    try:
        self.check_channels("ALPHA")
        if self["ALPHA"].data.shape != self.area.shape:
            self._data_holder.channels.remove(self["ALPHA"])
            raise Exception
    except:
        sun_zen_chn = self._dwd_get_sun_zenith_angles_channel()
        data = sun_zen_chn.data
        alpha = np.ma.zeros(data.shape, dtype=np.int)
        y, x = np.where(
            (data <= SUN_ZEN_NIGHT_LIMIT) & (data >= SUN_ZEN_DAY_LIMIT))
        alpha[y, x] = (((data[y, x] - SUN_ZEN_DAY_LIMIT) /
                       (SUN_ZEN_NIGHT_LIMIT - SUN_ZEN_DAY_LIMIT)) *
                       (254 - 1) + 1)
        alpha[np.where(data > SUN_ZEN_NIGHT_LIMIT)] += 255
        alpha_chn = Channel(name="ALPHA",
                            data=alpha)
        self._data_holder.channels.append(alpha_chn)
    return self["ALPHA"]


def _dwd_get_image_type(self):
    """Returns the image type:
    DAY_ONLY if the max value of sun zenith angles is below the day limit
    NIGHT_ONLY if the min value of sun zenith angles is above the day limit
    DAY_NIGHT if the sun zenith angle values are above and below the day limit
    """
    if self._data_holder.info.get("image_type", None) is None:
        sun_zen_chn = self._dwd_get_sun_zenith_angles_channel()
        data = sun_zen_chn.data
        if np.max(data.astype(int)) > SUN_ZEN_DAY_LIMIT:
            if np.min(data.astype(int)) >= SUN_ZEN_DAY_LIMIT:
                self._data_holder.info["image_type"] = IMAGETYPES.NIGHT_ONLY
            else:
                self._data_holder.info["image_type"] = IMAGETYPES.DAY_NIGHT
        else:
            self._data_holder.info["image_type"] = IMAGETYPES.DAY_ONLY
    return self._data_holder.info["image_type"]


def _dwd_create_RGB_image(self, channels, cranges):
    """Returns an RGB image of the given channel data and color ranges.
    """
    if not isinstance(channels, (list, tuple, set)) and \
            not isinstance(cranges, (tuple, list, set)) and \
            not len(channels) == len(cranges) and \
            not (len(channels) == 3 or len(channels == 4)):
        raise ValueError("Channels and color ranges must be list/tuple/set \
            and they must have the same length of 3 or 4 elements")

    if len(channels) == 3:
        return geo_image.GeoImage(channels,
                                  self.area,
                                  self.time_slot,
                                  fill_value=(0, 0, 0),
                                  mode="RGB",
                                  crange=cranges)
    if len(channels) == 4:
        return geo_image.GeoImage(channels,
                                  self.area,
                                  self.time_slot,
                                  fill_value=(0, 0, 0, 0),
                                  mode="RGBA",
                                  crange=cranges)


def dwd_airmass(self):
    """Make a DWD specific RGB image composite.
    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | WV6.2 - WV7.3      |     -25 to 0 K     | gamma 1            |
    +--------------------+--------------------+--------------------+
    | IR9.7 - IR10.8     |     -40 to 5 K     | gamma 1            |
    +--------------------+--------------------+--------------------+
    | WV6.2              |     243 to 208 K   | gamma 1            |
    +--------------------+--------------------+--------------------+
    """
    self.check_channels(6.7, 7.3, 9.7, 10.8)

    if not self._dwd_channel_preparation(6.7, 7.3, 9.7, 10.8):
        return None

    ch1 = self[6.7].data - self[7.3].data
    ch2 = self[9.7].data - self[10.8].data
    ch3 = self[6.7].data

    img = self._dwd_create_RGB_image((ch1, ch2, ch3),
                                     ((-25, 0),
                                      (-40, 5),
                                      (243 - CONVERSION, 208 - CONVERSION)))
    return img

dwd_airmass.prerequisites = set([6.7, 7.3, 9.7, 10.8])


def dwd_schwere_konvektion_tag(self):
    """Make a DWD specific RGB image composite.
    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | WV6.2 - WV7.3      |     -35 to 5 K     | gamma 1            |
    +--------------------+--------------------+--------------------+
    | IR3.9 - IR10.8     |      -5 to 60 K    | gamma 0.5          |
    +--------------------+--------------------+--------------------+
    | IR1.6 - VIS0.6     |     -75 to 25 %    | gamma 1            |
    +--------------------+--------------------+--------------------+
    """
    self.check_channels(0.635, 1.63, 3.75, 6.7, 7.3, 10.8)

    if not self._dwd_channel_preparation(0.635, 1.63, 3.75, 6.7, 7.3, 10.8):
        return None

    ch1 = self[6.7].data - self[7.3].data
    ch2 = self[3.75].data - self[10.8].data
    ch3 = self[1.63].check_range() - self[0.635].check_range()

    img = self._dwd_create_RGB_image((ch1, ch2, ch3),
                                     ((-35, 5),
                                      (-5, 60),
                                      (-75, 25)))
    img.enhance(gamma=(1.0, 0.5, 1.0))

    return img

dwd_schwere_konvektion_tag.prerequisites = set(
    [0.635, 1.63, 3.75, 6.7, 7.3, 10.8])


def dwd_dust(self):
    """Make a DWD specific RGB image composite.

    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | IR12.0 - IR10.8    |     -4 to 2 K      | gamma 1            |
    +--------------------+--------------------+--------------------+
    | IR10.8 - IR8.7     |     0 to 15 K      | gamma 2.5          |
    +--------------------+--------------------+--------------------+
    | IR10.8             |   261 to 289 K     | gamma 1            |
    +--------------------+--------------------+--------------------+
    """
    self.check_channels(8.7, 10.8, 12.0)

    if not self._dwd_channel_preparation(8.7, 10.8, 12.0):
        return None

    ch1 = self[12.0].data - self[10.8].data
    ch2 = self[10.8].data - self[8.7].data
    ch3 = self[10.8].data
    img = self._dwd_create_RGB_image((ch1, ch2, ch3),
                                     ((-4, 2),
                                      (0, 15),
                                      (261 - CONVERSION, 289 - CONVERSION)))
    img.enhance(gamma=(1.0, 2.5, 1.0))

    return img

dwd_dust.prerequisites = set([8.7, 10.8, 12.0])


def dwd_RGB_12_12_1_N(self):
    """Make a DWD specific composite depending sun zenith angle.
    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | HRVC               |   0.0 to 100.0 %   |        1.3         |
    +--------------------+--------------------+--------------------+
    | HRVC               |   0.0 to 100.0 %   |        1.3         |
    +--------------------+--------------------+--------------------+
    | VIS006             |   0.0 to 100.0 %   |        1.3         |
    +--------------------+--------------------+--------------------+
    Use IR10.8 for the night.
    """
    self.check_channels(0.635, 0.85, "HRV", 10.8)

    if not self._dwd_channel_preparation(0.635, 0.85, "HRV", 10.8):
        return None

    img_type = self._dwd_get_image_type()
    if img_type is None:
        return None

    # get combination of HRV and VIS008 channel data
    hrvc_chn = self._dwd_get_hrvc_channel()

    if img_type == IMAGETYPES.DAY_ONLY:
        img = self._dwd_create_RGB_image(
            (hrvc_chn.data, hrvc_chn.data, self[0.635].data),
            ((0, 100),
             (0, 100),
             (0, 100)))
        img.enhance(gamma=(1.3, 1.3, 1.3))
        return img

    if img_type == IMAGETYPES.NIGHT_ONLY:
        return self._dwd_create_single_channel_image('IR_108')

    if img_type == IMAGETYPES.DAY_NIGHT:
        alpha_data = self._dwd_get_alpha_channel().data
        # create day image
        day_img = self._dwd_create_RGB_image(
            (hrvc_chn.data, hrvc_chn.data, self[0.635].data, alpha_data),
            ((0, 100),
             (0, 100),
             (0, 100),
             (0, 255)))
        day_img.enhance(
            inverse=(False, False, False, True), gamma=(1.3, 1.3, 1.3, 1.0))
        # create night image
        night_img = self._dwd_create_RGB_image(
            (self[10.8].data, self[10.8].data, self[10.8].data, alpha_data),
            ((40, -87.5),
             (40, -87.5),
             (40, -87.5),
             (0, 255)))
        # blend day over night
        night_img.blend(day_img)
        # remove alpha channels
        night_img.convert("RGB")

        return night_img

    return None

dwd_RGB_12_12_1_N.prerequisites = set([0.635, 0.85, "HRV", 10.8])


def dwd_RGB_12_12_9i_N(self):
    """Make a DWD specific composite depending sun zenith angle.
    day:
    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | HRVC               |   0.0 to 100.0 %   |        1.0         |
    +--------------------+--------------------+--------------------+
    | HRVC               |   0.0 to 100.0 %   |        1.0         |
    +--------------------+--------------------+--------------------+
    | IR108              |  323.0 to 203.0 K  |        1.0         |
    +--------------------+--------------------+--------------------+
    night:
    +--------------------+--------------------+--------------------+
    | Channels           | Span               | Gamma              |
    +====================+====================+====================+
    | IR039 (inverted)   |         ---        |        1.0         |
    +--------------------+--------------------+--------------------+
    | IR108 (inverted)   |         ---        |        1.0         |
    +--------------------+--------------------+--------------------+
    | IR120 (inverted)   |         ---        |        1.0         |
    +--------------------+--------------------+--------------------+
    """
    self.check_channels("HRV", 0.85, 10.8, 3.75, 12.0)

    if not self._dwd_channel_preparation("HRV", 0.85, 10.8, 3.75, 12.0):
        return None

    # get combination of HRV and VIS008 channel data
    hrvc_chn = self._dwd_get_hrvc_channel()

    img_type = self._dwd_get_image_type()
    if img_type is None:
        return None

    if img_type == IMAGETYPES.DAY_ONLY:
        return self._dwd_create_RGB_image(
            (hrvc_chn.data, hrvc_chn.data, self[10.8].data),
            ((0, 100),
             (0, 100),
             (323 - CONVERSION, 203 - CONVERSION)))

    if img_type == IMAGETYPES.NIGHT_ONLY:
        img = self._dwd_create_RGB_image(
            (self[3.75].data, self[10.8].data, self[12.0].data),
            ((40, -87.5),
             (40, -87.5),
             (40, -87.5)))
        img.enhance(stretch="histogram")
        return img

    if img_type == IMAGETYPES.DAY_NIGHT:
        alpha_data = self._dwd_get_alpha_channel().data
        # create day image
        day_img = self._dwd_create_RGB_image(
            (hrvc_chn.data, hrvc_chn.data, self[10.8].data, alpha_data),
            ((0, 100),
             (0, 100),
             (323 - CONVERSION, 203 - CONVERSION),
             (0, 255)))
        day_img.enhance(inverse=(False, False, False, True))
        # create night image
        night_img = self._dwd_create_RGB_image(
            (self[3.75].data, self[10.8].data, self[12.0].data, alpha_data),
            ((40, -87.5),
             (40, -87.5),
             (40, -87.5),
             (0, 255)))
        night_img.enhance(stretch="histogram")
        # blend day over night
        night_img.blend(day_img)
        # remove alpha channels before saving
        night_img.convert("RGB")

        return night_img

    return None

dwd_RGB_12_12_9i_N.prerequisites = set(["HRV", 0.85, 10.8, 3.75, 12.0])


def dwd_ninjo_VIS006(self):
    return self._dwd_create_single_channel_image('VIS006')

dwd_ninjo_VIS006.prerequisites = set(['VIS006'])


def dwd_ninjo_VIS008(self):
    return self._dwd_create_single_channel_image('VIS008')

dwd_ninjo_VIS008.prerequisites = set(['VIS008'])


def dwd_ninjo_IR_016(self):
    return self._dwd_create_single_channel_image('IR_016')

dwd_ninjo_IR_016.prerequisites = set(['IR_016'])


def dwd_ninjo_IR_039(self):
    return self._dwd_create_single_channel_image('IR_039')

dwd_ninjo_IR_039.prerequisites = set(['IR_039'])


def dwd_ninjo_WV_062(self):
    return self._dwd_create_single_channel_image('WV_062')

dwd_ninjo_WV_062.prerequisites = set(['WV_062'])


def dwd_ninjo_WV_073(self):
    return self._dwd_create_single_channel_image('WV_073')

dwd_ninjo_WV_073.prerequisites = set(['WV_073'])


def dwd_ninjo_IR_087(self):
    return self._dwd_create_single_channel_image('IR_087')

dwd_ninjo_IR_087.prerequisites = set(['IR_087'])


def dwd_ninjo_IR_097(self):
    return self._dwd_create_single_channel_image('IR_097')

dwd_ninjo_IR_097.prerequisites = set(['IR_097'])


def dwd_ninjo_IR_108(self):
    return self._dwd_create_single_channel_image('IR_108')

dwd_ninjo_IR_108.prerequisites = set(['IR_108'])


def dwd_ninjo_IR_120(self):
    return self._dwd_create_single_channel_image('IR_120')

dwd_ninjo_IR_120.prerequisites = set(['IR_120'])


def dwd_ninjo_IR_134(self):
    return self._dwd_create_single_channel_image('IR_134')

dwd_ninjo_IR_134.prerequisites = set(['IR_134'])


def dwd_ninjo_HRV(self):
    return self._dwd_create_single_channel_image('HRV')

dwd_ninjo_HRV.prerequisites = set(['HRV'])


def blend(ch1, ch2):
    """Alpha blend *other* on top of the current image.
    """
    if ch1.mode != "LA" or ch2.mode != "LA":
        raise ValueError("Images must be in LA")
    src = ch2
    dst = ch1
    outa = src.channels[1] + dst.channels[1] * (1 - src.channels[1])
    dst.channels[0] = (src.channels[0] * src.channels[1] +
                       dst.channels[0] * dst.channels[1] *
                       (1 - src.channels[1])) / outa
    dst.channels[0][outa == 0] = 0
    dst.channels[1] = outa


def dwd_Fernsehbild(self):
    """
    """
# import dwd_extensions.mipp.hdf5.nwcsaf_msg as hdf5_  # @UnresolvedImport
# from mpop.satin import msg_hdf  # @UnresolvedImport
#     self._data_holder.channels_to_load.add("CloudType")
#         ct_area = msg_hdf.get_area_from_file(
#             "/home/ninjo-dev/pytroll-in/NWCSAF/SAFNWC_MSG3_CT___201503240730_EUROPE_B____.h5")
#     coverage = mpop.projector.Projector(ct_area,
#                                         self.area,
#                                         mode='nearest',
#                                         radius=10000,
#                                         nprocs=1)
#
#     hdf5_.load(self._data_holder, area_extent=ct_area.area_extent)
#    ct_chn = self["CloudType"]
#    ct_chn = ct_chn.project(coverage)
    ct_chn = self["CloudType"]
    ct_data = ct_chn.cloudtype
    ct_mask = np.ones(ct_data.shape, dtype=bool)
    ct_mask[((ct_data >= 5) & (ct_data <= 18))] = False
    # mask already masked data
    ct_mask[ct_data.mask] = True

    # smooth mask with gaussian filter with sigma 2
    # import scipy.ndimage as ndi
    # ct_mask =
    #     np.array(ndi.gaussian_filter(ct_mask.astype('float64'), 2) > 0.1)

    self.check_channels("HRV", 0.85, 10.8)

    if not self._dwd_channel_preparation("HRV", 0.85, 10.8):
        return None

    # get combination of HRV and VIS008 channel data
    hrvc_chn = self._dwd_get_hrvc_channel()

    img_type = self._dwd_get_image_type()
    if img_type is None:
        return None

    # extract the clouds for hrvis channel
    hrvc_clouds = hrvc_chn.data.copy()
    hrvc_clouds.mask[ct_mask] = True

    median = np.ma.median(hrvc_clouds)
    mean = np.ma.mean(hrvc_clouds)
    comp = hrvc_clouds.compressed()
    max_value = np.percentile(comp, 97)
    LOGGER.debug("HRVIS median: {0}, mean: {1}, diff: {2}, min: {3}, max: {4}".
                 format(median, mean, abs(median - mean),
                        hrvc_clouds.min(), max_value))

    day_img = geo_image.GeoImage(hist_equalize(hrvc_clouds, 8, 254),
                                 self.area,
                                 self.time_slot,
                                 fill_value=0,
                                 mode="L",
                                 crange=(0, 255))
#    day_img.enhance(stretch="histogram")

    # extract the clouds for infrared channel
    ir_clouds = self[10.8].data.copy()
    ir_clouds.mask[ct_mask] = True

    median = np.ma.median(ir_clouds)
    mean = np.ma.mean(ir_clouds)
    max_value = np.ma.max(ir_clouds)
    LOGGER.debug("IR median: {0}, mean: {1}, diff: {2}, min: {3}, max: {4}".
                 format(median, mean, abs(median - mean),
                        ir_clouds.min(), max_value))

    median = np.ma.median(ir_clouds)
    night_img = geo_image.GeoImage(hist_equalize(ir_clouds, 8, 254),
                                   self.area,
                                   self.time_slot,
                                   fill_value=0,
                                   mode="L",
                                   crange=(255, 0))
#    night_img.enhance(stretch="histogram")

    if img_type == IMAGETYPES.DAY_ONLY:
        img = day_img

    if img_type == IMAGETYPES.NIGHT_ONLY:
        img = night_img

    if img_type == IMAGETYPES.DAY_NIGHT:
        alpha_data =\
            self._dwd_get_alpha_channel().data.astype(np.float64) / 255.0
        # create day image
        day_img.putalpha(alpha_data)
        day_img.enhance(inverse=(False, True))
        # create night image
        night_img.putalpha(alpha_data)
        blend(night_img, day_img)
        img = night_img
        img.convert("L")

    return img

dwd_Fernsehbild.prerequisites = set(["HRV", 0.85, 10.8, "CloudType"])


def _create_fernsehbild_rgba(self, ct_alpha_def,
                             erosion_size=5, gaussion_filter_sigma=3,
                             dark_transparency_factor=3.0,
                             contrast_optimization_expr=None):
    """
    """
    if contrast_optimization_expr is None:
        contrast_optimization_expr = "hist_equalize(inputdata, 8, 254)"

    ct_chn = self["CloudType"]
    ct_data = ct_chn.cloudtype

    ct_alpha = np.ones(ct_data.shape)
    for ct in range(len(ct_alpha_def)):
        if ct_alpha_def[ct] < 1.0:
            ct_alpha[(ct_data == ct)] = ct_alpha_def[ct]

    # mask already masked data
    ct_alpha[ct_data.mask] = 0.0
    # ct_mask = ct_alpha < 0.01

    # shrink alpha mask to ensure that smoothed edges are inside mask
    import scipy.ndimage as ndi
    ct_alpha = ndi.grey_erosion(
        ct_alpha, size=(erosion_size, erosion_size)).astype(
        ct_alpha.dtype)

    self.check_channels("HRV", 0.85, 10.8)

    if not self._dwd_channel_preparation("HRV", 0.85, 10.8):
        return None

    # get combination of HRV and VIS008 channel data
    hrvc_chn = self._dwd_get_hrvc_channel()

    img_type = self._dwd_get_image_type()
    if img_type is None:
        return None

    # extract the clouds for hrvis channel
    hrvc_clouds = hrvc_chn.data.copy()
    # hrvc_clouds.mask[ct_mask] = True

    median = np.ma.median(hrvc_clouds)
    mean = np.ma.mean(hrvc_clouds)
    comp = hrvc_clouds.compressed()
    max_value = np.percentile(comp, 97)
    LOGGER.debug("HRVIS median: {0}, mean: {1}, diff: {2}, min: {3}, max: {4}".
                 format(median, mean, abs(median - mean),
                        hrvc_clouds.min(), max_value))

    # execute contrast optimization function (i.e. histogram equalisation)
    d = eval(contrast_optimization_expr, globals(), {'inputdata': hrvc_clouds})
    d.mask = False

    day_img = geo_image.GeoImage(d,
                                 self.area,
                                 self.time_slot,
                                 fill_value=0,
                                 mode="L",
                                 crange=(0, 255))
#    day_img.enhance(stretch="histogram")

    # extract the clouds for infrared channel
    ir_clouds = self[10.8].data.copy()
    # ir_clouds.mask[ct_mask] = True

    median = np.ma.median(ir_clouds)
    mean = np.ma.mean(ir_clouds)
    max_value = np.ma.max(ir_clouds)
    LOGGER.debug("IR median: {0}, mean: {1}, diff: {2}, min: {3}, max: {4}".
                 format(median, mean, abs(median - mean),
                        ir_clouds.min(), max_value))

    median = np.ma.median(ir_clouds)

    # execute contrast optimization function (i.e. histogram equalisation)
    d = eval(contrast_optimization_expr, globals(), {'inputdata': ir_clouds})
    d.mask = False

    night_img = geo_image.GeoImage(d,
                                   self.area,
                                   self.time_slot,
                                   fill_value=0,
                                   mode="L",
                                   crange=(255, 0))
#    night_img.enhance(stretch="histogram")

    if img_type == IMAGETYPES.DAY_ONLY:
        img = day_img

    if img_type == IMAGETYPES.NIGHT_ONLY:
        img = night_img

    if img_type == IMAGETYPES.DAY_NIGHT:
        alpha_data =\
            self._dwd_get_alpha_channel().data.astype(np.float64) / 255.0
        # create day image
        day_img.putalpha(alpha_data)
        day_img.enhance(inverse=(False, True))
        # create night image
        night_img.putalpha(alpha_data)
        blend(night_img, day_img)
        img = night_img
        img.convert("L")

    if gaussion_filter_sigma is not None:
        # smooth alpha channel
        ct_alpha = ndi.gaussian_filter(ct_alpha, gaussion_filter_sigma)

    if dark_transparency_factor is not None:
        # add transparency to dark image areas
        ct_alpha = np.minimum(ct_alpha, img.channels[0] *
                              dark_transparency_factor)

    img.convert("RGBA")
    img.putalpha(ct_alpha)
    img.fill_value = None


#     img = geo_image.GeoImage(ct_alpha*255.0,
#                                  self.area,
#                                  self.time_slot,
#                                  fill_value=0,
#                                  mode="L",
#                                  crange=(0, 255))

    return img


def dwd_FernsehbildRGBA(self, ct_alpha=None,
                        erosion_size=None,
                        gaussion_filter_sigma=None,
                        dark_transparency_factor=3.0,
                        contrast_optimization_expr=None):
    """
    """
    if ct_alpha is None:
        ct_alpha = np.ones(21, dtype=np.float64)
        ct_alpha[0:4] = 0.0
        ct_alpha[15] = 0.0
        ct_alpha[19] = 0.3
        ct_alpha[20] = 0.0

    return self._create_fernsehbild_rgba(ct_alpha,
                                         erosion_size,
                                         gaussion_filter_sigma,
                                         dark_transparency_factor,
                                         contrast_optimization_expr)

dwd_FernsehbildRGBA.prerequisites = set(["HRV", 0.85, 10.8, "CloudType"])


def hist_equalize(data, val_min, val_max):
    '''histogram equalisation as implemented in NinJo formula layer
    Stats.equalize but with automatic scaling to min and max data values
    '''

    # map data values to range 0..255
    data_min = np.ma.min(data)
    data_max = np.ma.max(data)
    scaled = ((data - data_min) / (data_max - data_min)) * 255
    hist_length = val_max - val_min + 1
    # mask values outside of the range
    scaled = np.ma.masked_outside(scaled, val_min, val_max)
    c_scaled = np.ma.compressed(scaled)
    # create histogram and calculate cumulative distributive function
    hist, _ = np.histogram(c_scaled, hist_length)
    cdf = hist.cumsum()
    # create lookup table
    factor = (val_max - val_min) * 1.0 / (cdf[-1] - cdf[0]) * 1.0
    lut = (cdf - cdf[0]) * factor + val_min + 0.5
    lut = lut.astype('uint8')
    # apply lookup table values
    scaled[~scaled.mask] = lut[scaled[~scaled.mask].astype('uint8') - val_min]
    # set mask to the incoming one
    scaled.mask = data.mask

    return scaled


def hist_equalize_v2(data, new_min, new_max):
    '''histogram equalisation as implemented in NinJo formula layer Stats.equalize
    '''

    hist_length = new_max - new_min + 1
    # mask values outside of the range
    scaled = np.ma.masked_outside(data, new_min, new_max)
    c_scaled = np.ma.compressed(scaled)
    # create histogram and calculate cumulative distributive function
    hist, _ = np.histogram(c_scaled, hist_length, range=(new_min, new_max))
    cdf = hist.cumsum()
    # create lookup table
    factor = (new_max - new_min) * 1.0 / (cdf[-1] - cdf[0]) * 1.0
    lut = (cdf - cdf[0]) * factor + new_min + 0.5
    lut = lut.astype('uint8')
    # apply lookup table values
    scaled[~scaled.mask] = lut[scaled[~scaled.mask].astype('uint8') - new_min]
    # set mask to the incoming one
    scaled.mask = data.mask

    return scaled


def hist_equalize_v3(data):
    '''histogram equalisation as implemented DWD's Fortran code
    '''
    # mask values outside of the range
    data1d = np.ma.compressed(np.ma.masked_outside(data, 0, 255))
    # create histogram and calculate cumulative distributive function
    histo, _ = np.histogram(data1d, 256, range=(0, 255))

    keil = np.ma.arange(256)
    keil = keil.astype('uint8')
    ihistsum = histo.sum()

    if ihistsum == 0:
        LOGGER.error("hist.sum() == 0")
        return

    khistsum = 0
    for ih in range(0, 256):
        khistsum = khistsum + histo[ih]
        keil[ih] = (255 * khistsum) / ihistsum

    # apply lookup table values
    result = np.ma.copy(data)
    result[~data.mask] = keil[data[~data.mask].astype('uint8')]
    return result


def hist_normalize_linear(data, new_min, new_max):
    """normalizes image to new min max
    """
    data_min = np.ma.min(data)
    data_max = np.ma.max(data)
    scaled = (data - data_min) * ((new_max - new_min) / (data_max - data_min))
    scaled.mask = data.mask
    return scaled


seviri = [
    _is_solar_channel, _dwd_kelvin_to_celsius,
    _dwd_apply_sun_zenith_angle_correction, _dwd_channel_preparation,
    _dwd_apply_view_zenith_angle_correction,
    _dwd_create_single_channel_image, _dwd_get_sun_zenith_angles_channel,
    _dwd_get_hrvc_channel, _dwd_get_alpha_channel, _dwd_get_image_type,
    _dwd_create_RGB_image, dwd_ninjo_VIS006, dwd_ninjo_VIS008,
    dwd_ninjo_IR_016, dwd_ninjo_IR_039, dwd_ninjo_WV_062, dwd_ninjo_WV_073,
    dwd_ninjo_IR_087, dwd_ninjo_IR_097, dwd_ninjo_IR_108, dwd_ninjo_IR_120,
    dwd_ninjo_IR_134, dwd_ninjo_HRV, dwd_airmass, dwd_schwere_konvektion_tag,
    dwd_dust, dwd_RGB_12_12_1_N, dwd_RGB_12_12_9i_N, dwd_Fernsehbild,
    dwd_FernsehbildRGBA, _create_fernsehbild_rgba]
