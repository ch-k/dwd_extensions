'''
Created on 07.04.2016

@author: Christian Kliche
'''
import mpop.imageo.geo_image as geo_image
import numpy as np
import logging

LOGGER = logging.getLogger("postprocessor")


def read_tiff_with_gdal(filename):
    """ read (geo)tiff via gdal
        unfortunatly it does not work after ninjotiff module was loaded
    """
    # saver = __
    # import__('mpop.imageo.formats.ninjotiff', globals(), locals(), ['save'])
    from osgeo import gdal
    logger = LOGGER

    dst = gdal.Open(filename, gdal.GA_ReadOnly)

    #
    # Dataset information
    #
    geotransform = dst.GetGeoTransform()
    projection = dst.GetProjection()
    metadata = dst.GetMetadata()

    logger.debug('description: %s' % dst.GetDescription())
    logger.debug('driver: %s / %s' % (dst.GetDriver().ShortName,
                                      dst.GetDriver().LongName))
    logger.debug('size: %d x %d x %d' % (dst.RasterXSize, dst.RasterYSize,
                                         dst.RasterCount))
    logger.debug('geo transform: %s' % str(geotransform))
    logger.debug('origin: %.3f, %.3f' % (geotransform[0], geotransform[3]))
    logger.debug('pixel size: %.3f, %.3f' % (geotransform[1], geotransform[5]))
    logger.debug('projection: %s' % projection)
    logger.debug('metadata: %s', metadata)

    #
    # Fetching raster data
    #
    channels = []
    for i in xrange(1, dst.RasterCount + 1):
        band = dst.GetRasterBand(i)
        logger.info(
            'Band(%d) type: %s, size %d x %d' %
            (i, gdal.GetDataTypeName(band.DataType),
             dst.RasterXSize, dst.RasterYSize))
        shape = (dst.RasterYSize, dst.RasterXSize)
        if band.GetOverviewCount() > 0:
            logger.debug('overview count: %d' % band.GetOverviewCount())
        if not band.GetRasterColorTable() is None:
            logger.debug('colortable size: %d' %
                         band.GetRasterColorTable().GetCount())

        data = band.ReadAsArray(0, 0, shape[1], shape[0])
        logger.info('fetched array: %s %s %s [%d -> %.2f -> %d]' %
                    (type(data), str(data.shape), data.dtype,
                     data.min(), data.mean(), data.max()))

        arr = np.array(data)  # @UndefinedVariable
        # @UndefinedVariable
        if band.DataType == gdal.GDT_UInt32:
            dtype = np.uint32  # @UndefinedVariable
        elif band.DataType == gdal.GDT_UInt16:
            dtype = np.uint16  # @UndefinedVariable
        else:
            dtype = np.uint8  # @UndefinedVariable
        b = np.iinfo(dtype).max  # @UndefinedVariable

        mask = None
        nodata_val = band.GetNoDataValue()
        if nodata_val is not None:
            mask = arr == nodata_val

        channels.append(
            np.ma.array(arr[:, :] / float(b), mask=mask))  # @UndefinedVariable

    return channels


def read_tiff_with_pil(filename):
    """ read tiff via PIL
        workaround function to replace 'read_tiff_with_gdal' until
        issues with ninjotiff module have been resolved
    """
    # import mpop.imageo.formats.ninjotiff as ninjotiff
    # for inf in ninjotiff.info(filename):
    #    print inf, '\n'

    from PIL import Image
    im = Image.open(filename)
    arr = np.array(im)  # @UndefinedVariable
    channels = []
    if len(arr.shape) == 2:
        channels.append(np.ma.array(arr[:, :] / 255.0))  # @UndefinedVariable
    else:
        for i in range(0, arr.shape[2]):
            channels.append(
                np.ma.array(arr[:, :, i] / 255.0))  # @UndefinedVariable
    return channels


def read_image(filename, area, timeslot):
    channels = read_tiff_with_gdal(filename)
    # channels = read_tiff_with_pil(filename)

    if len(channels) == 1:
        mode = "L"
        fill_value = (0)
    elif len(channels) == 4:
        # channels = channels[:-1]
        # mode = "RGB"
        # fill_value = (0, 0, 0)

        mode = "RGBA"
        fill_value = (0, 0, 0, 0)
    else:
        mode = "RGB"
        fill_value = (0, 0, 0)

    geo_img = geo_image.GeoImage(tuple(channels),
                                 area,
                                 timeslot,
                                 fill_value=fill_value,
                                 mode=mode)
    return geo_img
