#!/usr/bin/env python

import os
import time
import fnmatch
from os.path import basename
from os.path import splitext
import colorsys
import rrdtool as rrd
from optparse import OptionParser
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import rgb2hex


def listfiles(d, pattern):
    """return list of files in directory"""
    return [os.path.join(d, o) for o in os.listdir(d)
            if os.path.isfile(os.path.join(d, o)) and
            fnmatch.fnmatch(o, pattern)]


def get_colors(num_colors):
    """
    genernate unique colors
    """

    # cmap = plt.get_cmap('prism')
    cmap = plt.get_cmap('nipy_spectral')
    return [rgb2hex(cmap(v)) for v in range(0, 255, 255/num_colors)]

    """
    http://stackoverflow.com/a/17684501/3584189
    """
    # hsv_tuples = [(x*1.0/num_colors, 0.5, 0.5) for x in range(num_colors)]
    # hex_out = []
    # for rgb in hsv_tuples:
    #     rgb = map(lambda x: int(x*255), colorsys.hsv_to_rgb(*rgb))
    #     hex_out.append("".join(map(lambda x: chr(x).encode('hex'), rgb)))
    # return hex_out


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def create_single_graph(path, imagename, first, last, arch, title, file_chunk, width):
    names = [splitext(basename(f))[0] for f in file_chunk]
    defs = []
    linestyles = []
    caption_length = len(max(names, key=len))
    colors = get_colors(len(file_chunk))
    for idx in range(0, len(file_chunk)):
        defs.append('DEF:D%s=%s:%s' % (idx, file_chunk[idx], arch))
        defs.append('CDEF:CD%s=D%s,0.0166667,*' % (idx, idx))
        linestyles.append('LINE2:CD%s%s:%s' %
                          (idx, colors[idx],
                           names[idx].ljust(caption_length)))

    rrd.graph(path,
              '--imgformat', 'PNG',
              '--width', str(width),
              '--height', '600',
              '--start', str(first),
              '--end', str(last),
              '--vertical-label', 'minutes',
              '--title', title,
              # '--lower-limit', '0',
              'TEXTALIGN:left',
              '--font', 'LEGEND:7:monospace',
              '--x-grid', 'MINUTE:15:HOUR:1:HOUR:2:0:%a %H:%M %Z',
              '--y-grid', '0.166667:6',
              '--legend-direction', 'topdown',
              '--dynamic-labels',
              defs,
              linestyles)
    print "created %s" % path


def create_graphs(imagedir, rrddir, last_hours, maxitems):
    os.environ['TZ'] = 'UTC'
    time.tzset()
    files = listfiles(rrddir, '*.rrd')

    lasts = [rrd.last(f) for f in files]
    last = max(lasts)

    first = last - (last_hours * 60 * 60)

    # sort file file according to the last value in rrd file
    last_min = min(lasts)
    step = max([rrd.info(f)['step'] for f in files])
    # retrieve last 3 datapoints
    # seems that fetch delivers one datapoint before and after required
    # start/end, so using "--start e-step*2 --end last-step" instead of
    # "--start e-step*3 --end last"
    data = [rrd.fetch(f, 'MAX',
                      '--resolution', str(step),
                      '--start', 'e-'+str(step*2),
                      '--end', str(last_min-step))[2][0] for f in files]
    data = zip([a for (a, _) in data], files)
    files = [f for (_, f) in sorted(data)]
    width = (last_hours // 24 + 1) * 1000
    cfs = [('rrdgraph_epi2product',
            'epi2product:MAX',
            'EPI file -> product'),
           ('rrdgraph_timeslot2product',
            'timeslot2product:MAX',
            'HRIT timeslot -> product')]
    for imagename, arch, title in cfs:
        path = os.path.join(imagedir, "%s_all.png" % (imagename,))
        create_single_graph(path, imagename, first, last,
                            arch, title, files, width)

        for n, file_chunk in enumerate(chunks(files, maxitems)):
            path = os.path.join(imagedir, "%s_%02d.png" % (imagename, n))
            create_single_graph(path, imagename, first, last,
                                arch, title, file_chunk, width)


def main():
    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description
    OptionParser.format_epilog = \
        lambda self, formatter: self.epilog

    description = """\
This script can be used to generate graphs via rrdtool.
"""

    epilog = '''\

Results:


'''

    parser = OptionParser(description=description, epilog=epilog)
    parser.add_option("-d", "--rrd-directory",
                      action="store",
                      type="string",
                      dest="rrddir",
                      metavar="FILE",
                      help="path to rrd files")
    parser.add_option("-o", "--output-directory",
                      action="store",
                      type="string",
                      dest="outdir",
                      metavar="FILE",
                      help="path to output")
    parser.add_option("-l", "--last-n-hours",
                      action="store",
                      type="int",
                      default=3,
                      dest="lasthours",
                      help="plot data of last N hours")
    parser.add_option("-m", "--max-items-per-file",
                      action="store",
                      type="int",
                      default=10,
                      dest="maxitems",
                      help="plot maximum of N products to one file")

    (options, _) = parser.parse_args()

    create_graphs(options.outdir, options.rrddir,
                  options.lasthours, options.maxitems)


if __name__ == "__main__":
    main()
