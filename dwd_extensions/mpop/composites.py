'''
Created on 05.01.2015

@author: Christian Kliche <chk@ebp.de>
'''

import mpop.imageo.geo_image as geo_image
import logging

# LOG FILE
logger = logging.getLogger('msg_chain')
# level
logger.setLevel(logging.DEBUG)
LOG_FILENAME = 'msg_chain.log'
# LOG_FILENAME = '/data/LOG/msg_chain.log'
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.DEBUG)
PATTERN = '%(asctime)s [%(levelname)-8s]  [%(name)-12s] %(message)s'
formatter = logging.Formatter(PATTERN, "%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
logger.addHandler(fh)


def dwdcomp_HRV(self):
    """Make image composite from Seviri HRV
    channel.
    """
    chn = "HRV"
    logger.info('channel: ' + chn)

    self.check_channels(chn)

    logger.info('apply sun angle correction')
    self[chn].data = self[chn].sunzen_corr(self.time_slot, limit=85.).data

    img = self.channel_image(chn)

    # add simple overlay (layout will be handled differently later)
    # img.add_overlay(color=(0, 0, 0), width=0.5, resolution='i')

    logger.info('channel: ' + chn + ' (done)')

    return img

dwdcomp_HRV.prerequisites = set(["HRV"])


def dwdcomp_VIS006(self):
    """Make image composite from Seviri VIS006
    channel.
    """
    chn = "VIS006"
    logger.info('channel: ' + chn)

    self.check_channels(chn)

    logger.info('apply sun angle correction')
    self[chn].data = self[chn].sunzen_corr(self.time_slot, limit=85.).data

    img = self.channel_image(chn)

    # add simple overlay (layout will be handled differently later)
    # img.add_overlay(color=(0, 0, 0), width=0.5, resolution='i')

    logger.info('channel: ' + chn + ' (done)')

    return img

dwdcomp_VIS006.prerequisites = set(["VIS006"])


def dwdcomp_VIS008(self):
    """Make image composite from Seviri VIS008
    channel.
    """
    chn = "VIS008"
    logger.info('channel: ' + chn)

    logger.info('apply sun angle correction')
    self[chn].data = self[chn].sunzen_corr(self.time_slot, limit=85.).data

    self.check_channels(chn)

    img = self.channel_image(chn)

    # add simple overlay (layout will be handled differently later)
    # img.add_overlay(color=(0, 0, 0), width=0.5, resolution='i')

    logger.info('channel: ' + chn + ' (done)')

    return img

dwdcomp_VIS008.prerequisites = set(["VIS008"])


def dwdcomp_IR_108(self):
    """Make image composite from Seviri IR_108
    channel.
    """
    chn = "IR_108"
    logger.info('channel: ' + chn)

    self.check_channels(chn)

    img = geo_image.GeoImage(self[chn].data,
                             self.area,
                             self.time_slot,
                             fill_value=0,
                             mode="L",
                             crange=(-87.5 + 273.15, 40 + 273.15))
    img.enhance(inverse=True)

    # add simple overlay (layout will be handled differently later)
    # img.add_overlay(color=(0, 0, 0), width=0.5, resolution='i')

    logger.info('channel: ' + chn + ' (done)')

    return img

dwdcomp_IR_108.prerequisites = set(["IR_108"])

seviri = [dwdcomp_HRV, dwdcomp_IR_108, dwdcomp_VIS006, dwdcomp_VIS008]
