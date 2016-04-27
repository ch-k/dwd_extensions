'''
Created on 07.04.2016

@author: Christian Kliche
'''
import mpop.imageo.geo_image as geo_image
from mpop.projector import get_area_def
from dwd_extensions.tools.image_io import read_image
from urlparse import urlparse
import logging


LOGGER = logging.getLogger(__name__)


def create_world_composite(msg):
    """
    """
    LOGGER.info('do it')

    img = None
    for d in msg.data['dataset']:
        print d
        p = urlparse(d['uri'])
        if p.netloc != '':
            LOGGER.error('uri not supported: {0}'.format(msg.data['uri']))
            return None

        # load image
        area = get_area_def(msg.data['area']['name'])
        next_img = read_image(p.path, area, msg.data['time_eos'])
        # next_img.convert("RGBA")
        if img is None:
            img = next_img
        else:
            img.merge(next_img)
            # img.blend(next_img)

    return img
