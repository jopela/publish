#!/usr/bin/env python3

# this is a weird python/shell script hybrid!

import argparse
import os
import cityinfo
import cityres
import json
import urlinfer
import requests
import subprocess

from time import sleep
from progressbar import ProgressBar, AnimatedMarker, Percentage, ETA
from filecache import filecache

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

    default_nailgun_bin = '/usr/share/java/nailgun.jar'
    parser.add_argument(
            '-n',
            '--nailgun-bin',
            help='the path to the nailgun binary. Defaults to '\
            '{0}'.format(default_nailgun_bin),
            default = default_nailgun_bin
            )

    default_editorial_jar = '/usr/share/java/editorial-0.1.1-standalone.jar'
    parser.add_argument(
            '-c',
            '--content-generator',
            help='the path to the .jar for the editorial content generator'\
                    ' Defaults to {0}'.format(default_editorial_jar),
            default = default_editorial_jar
            )

    args = parser.parse_args()

    if args.display:
        guides = list_guide(args.path,args.guide_name)
        for name in guides:
            print(name)

        exit(0)

    publish(args.path,
            args.guide_name,
            args.endpoint,
            args.nailgun_bin)

    return

def publish(path, guide_name, endpoint, nailgun_bin):
    """
    Runs the publishing operation on the given directory path.
    """

    guides = list_guide(path,guide_name)

    # helper function used during editorial content generation.
    def unquote(uri):
        """
        remove the " at each end of a string if present.
        """
        if len(uri) < 2:
            return uri

        if uri[0] == '"' and uri[-1] == '"':
            return uri[1:-1]

    searches= {}
    widgets = ['extracting editorial content for the guides:',
               AnimatedMarker(markers='◐◓◑◒'),
               Percentage(),
               ETA()]

    # init nailgun since it is needed for editorial content generation.
    nailguninit(nailgun_bin)

    pbar = ProgressBar(widgets=widgets,maxval=len(guides)).start()

    published_guides = 0
    dbpedialess = []
    for i, guide in enumerate(guides):
        # query the wiki's in a polite manner
        sleep(0.1)
        pbar.update(i)
        with open(guide,'r') as g:
            jsonguide = json.load(g)
            # pull the search string.
            search = cityinfo.cityinfo(jsonguide)
            # get the city res
            uri = cityres.cityres(search,endpoint)
            if not uri:
                dbpedialess.append(guide)
                continue
            # get the wiki's addresses
            urls = urlinfer.urlinferdef([unquote(uri)])
            published_guides += 1

    ## for each of these resources, get the wikipedia and the wikivoyage urls
    #widgets[0] = "infering the wikipedia and wikivoyage urls from resources"
    #pbar = ProgressBar(widgets=widgets, maxval=len(uris)).start()
    #i = 0
    #urls = {}
    #for k,v in uris.items():
    #    # urlinferdef expects unquoted uri
    #    urls[k] = urlinfer.urlinferdef([unquote(v)])
    #    sleep(0.5)
    #    pbar.update(i+1)
    #    i += 1

    ## only keep urls that return 200 ok to a get requests.
    #widgets[0] = "selecting valid url for each destination"
    #pbar = ProgressBar(widgets=widgets, maxval=len(urls)).start()
    #i = 0
    #valid_urls = {}
    #for k,v in urls.items():
    #    valid_urls[k] = [url for url in v if url_resolvable(url)]
    #    sleep(0.3)
    #    pbar.update(i+1)
    #    i += 1

    publish_summary_template = """
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~                         publishing summary                              ~
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    number of entry guide:{0}
    guides with dbpedia resources:{1}
    guides with no dbpedia resources:
    {2}
    dbpedia resource hit rate:{3}
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """

    nbr_entry_guide = len(guides)
    nbr_guide_content = published_guides
    no_dbpedia = "\n".join(["-{0}".format(g) for g in dbpedialess]) if len(dbpedialess) > 1 else "none"
    dbpedia_hit_rate = (nbr_entry_guide - len(dbpedialess))/(nbr_entry_guide)*100

    publish_summary_instance = publish_summary_template.format(
            nbr_entry_guide,
            nbr_guide_content,
            no_dbpedia,
            dbpedia_hit_rate)

    print(publish_summary_instance)
    return

def editorial_content(urls):
    """
    from a collection of given url, generate some editorial content.
    """

    # start the nailgun thing if need be
    return

def nailguninit(path):
    """
    takes care of starting the nailgun thing if not already started.
    included for portability but nailgun should usually be started on the
    mtrip datastore machine (192.168.1.202)
    """

    # is nailgun started?
    res = subprocess.call("ng ng-version &> /dev/null", shell=True)

    # start nailgun.
    if not res == 0:
        ng_shell_template = "java -jar {0} &> /dev/null &"
        ng_shell_instance = ng_shell_template.format(path)
        res = subprocess.call(ng_shell_instance, shell=True)
        print("started nailgun server")
    else:
        print("nailgun was already up and running")

    # relying on timing to make sure ng is started before using it.
    # RELAX, it's ok to do this because ng with this, nailgun will be started
    # before ussage with very high probability.
    sleep(0.5)
    print("nailgun ready")
    return

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
    guides = [guide_file(d,guide_name) for d in directories if guide_file(d,
        guide_name)]

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

