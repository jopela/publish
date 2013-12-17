#!/usr/bin/env python3

# this is a weird python/shell script hybrid!

import argparse
import os
import cityinfo
import cityres
import json
import urlinfer

from time import sleep
from progressbar import ProgressBar, AnimatedMarker, Percentage, ETA

def main():

    parser = argparse.ArgumentParser(description="generate the editorial"\
            " content for all mtrip guides found under the given working dir")

    parser.add_argument(
            'path',
            help='root directory that contain all the guides'
            )

    parser.add_argument(
            '-d',
            '--display',
            help='dump the filenames of the guide found under path',
            action = 'store_true'
            )

    parser.add_argument(
            '-g',
            '--guide-name',
            help='the filename of the guides for which content is to be'\
                    ' published. It defaults to the naming convention for'\
                    ' guide filenames which is result.json',
            type = str,
            default='result.json'
            )

    default_endpoint = 'http://192.168.1.202:8890/sparql'
    parser.add_argument(
            '-e',
            '--endpoint',
            help='location of the SPARQL endpoint used for the publishing'\
                    ' content gathering. Will default to the local mtrip'\
                    ' virtuoso data store SPARQL endpoint.'\
                    ' ({0}).'.format(default_endpoint),
            default=default_endpoint)

    args = parser.parse_args()

    if args.display:
        guides = list_guide(args.path,args.guide_name)
        for name in guides:
            print(name)

        exit(0)

    searches = publish(args.path, args.guide_name, args.endpoint)
    for key in searches:
        print(key,":",searches[key])

    return

def publish(path, guide_name, endpoint):
    """
    Runs the publishing operation on the given directory path.
    """

    guides = list_guide(path,guide_name)
    # load the guide and invoke city info on all of them.
    searches= {}
    widgets = ['extracting city name and geoloc info from the guide: ',
               AnimatedMarker(markers='◐◓◑◒'),
               Percentage(),
               ETA()]
    pbar = ProgressBar(widgets=widgets,maxval=len(guides)).start()
    for i, guide in enumerate(guides):
        with open(guide,'r') as g:
            jsonguide = json.load(g)
            searches[guide] = cityinfo.cityinfo(jsonguide)

        pbar.update(i+1)

    print("")

    # for each of these searches string, get the uri associated
    widgets[0] = "extracting resources from SPARQL endpoint:"
    pbar = ProgressBar(widgets=widgets, maxval=len(searches)).start()
    i = 0
    uris = {}
    for k,v in searches.items():
        uris[k] = cityres.cityres(v,endpoint)
        pbar.update(i+1)
        i += 1

    print("")

    def unquote(uri):
        """
        remove the " at each end of a string if present.
        """
        if len(uri) < 2:
            return uri

        if uri[0] == '"' and uri[-1] == '"':
            return uri[1:-1]

    # for each of these resources, get the wikipedia and the wikivoyage urls
    widgets[0] = "infering the wikipedia and wikivoyage urls from resources"
    pbar = ProgressBar(widgets=widgets, maxval=len(uris)).start()
    i = 0
    urls = {}
    for k,v in uris.items():
        # urlinferdef expects unquoted uri
        urls[k] = urlinfer.urlinferdef([unquote(v)])
        sleep(0.5)
        pbar.update(i+1)
        i += 1

    # for each of the guide in the url, generate the editorial content

    return urls

def list_guide(path, guide_name):
    """
    returns a list of all the mtrip guide files that can be found under

    EXAMPLE
    =======

    >>> list_guide('./test')

    ['']
    """

    # list all directories in the path.
    directories = [os.path.join(path,d) for d in os.listdir(path) if
            os.path.isdir(os.path.join(path,d))]

    # get the result filename from the dir
    guides = [guide_file(d,guide_name) for d in directories if guide_file(d,guide_name)]

    return guides

def guide_file(path,guide_name):
    """ Return the json filename guide found in path. None if it cannot be
    found. """

    dir_content = [os.path.join(path,content) for content in os.listdir(path)
            if guide_name in os.path.join(path,content)]

    if len(dir_content) > 0:
        return dir_content[0]
    else:
        return None

if __name__ == '__main__':
    main()

