#!/usr/bin/env python3
import argparse
import os
import cityinfo
import cityres
import json
import urlinfer
import requests
import subprocess
import logging
import sys
import jsonsert
import zipclean

from progressbar import ProgressBar, AnimatedMarker, Percentage, ETA
from time import sleep
from urllib.parse import urlparse

def main():

    parser = argparse.ArgumentParser(description="generate the editorial"\
            " content for all mtrip guides found under the given working dir")

    parser.add_argument(
            'path',
            help='root directory that contain all the guides',
            nargs='?'
            )

    parser.add_argument(
            '-d',
            '--dump',
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

    default_editorial_jar = '/root/dev/editorial/target/editorial-0.1.1-standalone.jar'
    parser.add_argument(
            '-c',
            '--content-generator',
            help='the path to the .jar for the editorial content generator'\
                    ' Defaults to {0}'.format(default_editorial_jar),
            default = default_editorial_jar
            )

    default_wikison_jar = '/root/dev/wikison/target/wikison-0.1.1-standalone.jar'
    parser.add_argument(
            '-D',
            '--description-gen',
            help='the path to the .jar for the description content generator'\
                    ' Defaults to {0}'.format(default_wikison_jar),
            default=default_wikison_jar
            )

    default_classpath = 'editorial.core'
    parser.add_argument(
            '-f',
            '--function-class',
            help='the classpath name that contains the main method that will'\
                    ' be invoked by nailgun when generating ed contant (e.g: myapp.core). Defaults to'\
                    ' {0}.'.format(default_classpath),
            default=default_classpath
            )

    default_description_classpath = 'wikison.core'
    parser.add_argument(
            '-F',
            '--function-description-class',
            help='the classpath name that contains the main method that will'\
                    ' be invoked by nailgun when generating description'\
                    ' contant (e.g: myapp.core). Defaults to'\
                    ' {0}.'.format(default_description_classpath),
            default=default_description_classpath
            )

    default_log_file = '/var/log/publish.py.log'
    parser.add_argument(
            '-l',
            '--log-file',
            help='path to the event log file. Defaults to {0}'.format(
                default_log_file),
            default = default_log_file
            )

    current_version = "0.1.1"
    parser.add_argument(
            '-v',
            '--version',
            help='prints the current version and quit',
            action='store_true'
            )

    parser.add_argument(
            '-m',
            '--message-debug',
            help='enable debug message to log file. Defaults to false',
            action='store_true'
            )

    default_user_agent = 'publish v0.1.1 (jonathan.pelletier1@gmail.com)'
    parser.add_argument(
            '-u',
            '--user-agent',
            help='user agent string used for online content gathering.'\
                    ' Defaults to {0}'.format(default_user_agent),
            default = default_user_agent
            )

    parser.add_argument(
            '-t',
            '--test',
            help='run the doctest suite and exit.',
            action = 'store_true'
            )

    publish_choices = ('description','editorial','zipcode-remove')
    parser.add_argument(
            '-p',
            '--publish-functions',
            help='the set of publish operation to perform. '\
                    'Defaults to {0}'.format(publish_choices),
            nargs='+',
            default=publish_choices
            )

    args = parser.parse_args()

    if args.test:
        import doctest
        doctest.testmod()
        exit(0)

    if args.dump:
        guides = list_guide(args.path,args.guide_name)
        for name in guides:
            print(name)
        exit(0)

    if args.version:
        print(current_version)
        exit(0)

    config_logger(args.log_file, args.message_debug)

    publish(args.path,
            args.guide_name,
            args.endpoint,
            args.function_class,
            args.function_description_class,
            args.user_agent,
            args.publish_functions,
            args.log_file,
            args.nailgun_bin,
            args.content_generator,
            args.description_gen)

    return

def config_logger(filename, debug):
    """ apply the relevent logger configuration passed as command line
    argument by user."""

    logging_level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
            format='%(asctime)s %(module)s %(levelname)s %(message)s',
            level=logging_level,
            filename=filename
            )

    # requests library is noisy so we disable it's logger.
    requests_log = logging.getLogger("requests")
    requests_log.setLevel(logging.WARNING)

    return

def publish(path,
            guide_name,
            endpoint,
            function_class,
            function_description_class,
            user_agent,
            publish_functions,
            log_file,
            nailgun_bin,
            content_generator,
            description_gen):
    """
    Runs the publishing operation on the given directory path.
    """

    guides = list_guide(path,guide_name)

    error = False
    if 'editorial' in publish_functions:
        logging.info('starting editorial content generation')
        error |= editorial_publish(guides,
                                   endpoint,
                                   function_class,
                                   user_agent,
                                   nailgun_bin,
                                   content_generator)

    if 'description' in publish_functions:
        logging.info('starting description content generation')
        error |= description_publish(guides,
                                     user_agent,
                                     function_description_class,
                                     nailgun_bin,
                                     description_gen)

    if 'zipcode-remove' in publish_functions:
        logging.info('starting zipcode cleanup')
        error |= zipclean.zipclean(path, guide_name)



    print('publishing operation completed.')
    if error:
        print('the software encountered errors during guide publication.'\
                ' please see the log file ({0}) for more details'.format(
                    log_file))

    nailgunstop()
    return

def description_publish(guides,
                        user_agent,
                        function_class,
                        nailgun_bin,
                        description_gen):
    """
    Publish the description content for the guides.
    """

    # start the nailgun thing for usage with decription_generation.
    nailguninit(nailgun_bin, description_gen)
    sources_domain = {'wikipedia','wikivoyage'}
    error = False
    for g in guides:
        jsonguide = None
        with open(g,'r') as guide:
            jsonguide = json.load(guide)

        if not jsonguide:
            logging.error('could not load json from {0}'.format(g))
            error = True
            continue

        # TODO: for the moment, there is ALWAYS only one city inside a guide.
        # should we modify this code so that operations can be performed
        # when we have many cities? dont know yet.

        pois = jsonguide['Cities'][0]['pois']
        widgets = ['extracting description for the poi(s) in'\
                ' {0}:'.format(g),
                   AnimatedMarker(markers='◢◣◤◥'),
                   Percentage(),
                   ETA()]

        pbar = ProgressBar(widgets=widgets,maxval=len(pois)).start()
        for i,p in enumerate(pois):
            desc = p['descriptions']
            for k, v in desc.items():
                try:
                    url = v['source'].get('url')
                except:
                    logging.error("source did not contain a dictionary"\
                            " for {0}".format(p['name']['name']))
                    continue
                hostname = urlparse(url).hostname
                if hostname:
                    tldn = hostname.split('.')[-2]
                else:
                    continue
                if tldn in sources_domain:
                    content_raw = description_content(
                            [url],
                            function_class,
                            user_agent)
                    c_list = json.loads(content_raw)
                    content = c_list[0] if len(c_list) > 0 else None
                    if not content:
                        poi_name = p['name']['name']
                        logging.error(
                                'failed to generate descriptive content'\
                                ' for {0} using url {1}'.format(poi_name,
                                    url))
                        error = True
                    else:
                        v['text'] = content

            pbar.update(i+1)

        # redump the guide into the file
        pbar.finish()
        with open(g,'w') as guide:
            json.dump(jsonguide, guide)

    logging.info('description content succesfully inserted in all guides')
    return error

def description_content(urls,class_path, user_agent):
    """
    generate the description content from a url.
    """
    quoted_urls = quote_urls(urls)
    urls_args = " ".join(quoted_urls)
    ed_gen_template = 'ng {0} -u "{1}" -m  {2}'
    ed_gen_instance = ed_gen_template.format(class_path, user_agent, urls_args)

    content = subprocess.check_output(ed_gen_instance, shell=True,
            universal_newlines=True)

    return content

def editorial_publish(guides,
                      endpoint,
                      function_class,
                      user_agent,
                      nailgun_bin,
                      content_generator):
    """
    takes care of publishing the editorial content for the guides.
    """

    # init the nailgun thing for ed content generation.
    nailguninit(nailgun_bin,content_generator)

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

    pbar = ProgressBar(widgets=widgets,maxval=len(guides)).start()

    error = False
    for i, guide in enumerate(guides):
        jsonguide = None
        with open(guide,'r') as g:
            jsonguide = json.load(g)

        if not jsonguide:
            logging.error('could not load json from {0}'.format())
            error = True
            continue
        search = cityinfo.cityinfo(jsonguide)
        uri = cityres.cityres(search,endpoint)
        if not uri:
            logging.error(
                    'no dbpedia resource was found for {0}'.format(guide))
            error = True
            continue
        urls = urlinfer.urlinferdef([unquote(uri)])
        if len(urls) < 1:
            logging.error('no wikipedia/wikivoyage urls found/inferred'\
                   ' for resource {0}'.format(uri))
            error = True
            continue
        content = editorial_content(urls,function_class,user_agent)
        if not content:
            logging.error('no editorial content could be'\
                    ' generated for {0}'.format(guide))
            error = True
            continue

        #insert the content into the guide
        jsonsert.jsonsert(content, guide)

        logging.info('editorial content for {0} sucessfully'\
                ' inserted.'.format(guide))
        pbar.update(i+1)

    return error


def editorial_content(urls, class_path, user_agent):
    """
    from a collection of given url, generate some editorial content.
    """
    quoted_urls = quote_urls(urls)
    urls_args = " ".join(quoted_urls)
    ed_gen_template = 'ng {0} -u "{1}" {2}'
    ed_gen_instance = ed_gen_template.format(class_path, user_agent, urls_args)

    content = subprocess.check_output(ed_gen_instance, shell=True,
            universal_newlines=True)

    return content

def quote_urls(urls):
    """
    takes a list of url string and quote them, if need be, for usage inside
    a shell invocation string"


    EXAMPLE
    =======

    # non quoted urls are quoted
    >>> quote_urls(['http://en.wikipedia.org', 'http://ru.wiki.ru/stuff'])
    ['"http://en.wikipedia.org"', '"http://ru.wiki.ru/stuff"']

    # already quoted urls are left untouched.
    >>> quote_urls(['"http://exp.com"', 'http://google.com'])
    ['"http://exp.com"', '"http://google.com"']

    # aplication on empty list is idempotent
    >>> quote_urls([])
    []

    """
    def is_quoted(url):
        """ return true if a url is quoted, false otherwise."""
        return len(url) > 1 and url[0] == '"' and url[-1] == '"'

    def wrap(s,sym):
        """ returns a string wrapped with sym """
        return '{0}{1}{0}'.format(sym,s)

    return [u if is_quoted(u) else wrap(u,'"') for u in urls]

def nailguninit(path, jar):
    """
    takes care of starting the nailgun thing if not already started.
    The function will set the correct nailgun class path to use the
    editorial content jar specified by the user.
    This is included for portability but nailgun should usually be started on
    the mtrip datastore machine (192.168.1.202).
    """

    print("starting nailgun ...")
    subprocess.call("ng ng-stop &> /dev/null", shell=True)

    sleep(2)
    ng_shell_template = "java -jar {0} &> /dev/null &"
    ng_shell_instance = ng_shell_template.format(path)
    res = subprocess.call(ng_shell_instance, shell=True)
    if not res == 0:
        logging.critical('could not start nailgun'\
                'with {0} as the specified location. Is the'\
                ' given path spelled correctly?')
        die('critical:could not init nailgun. See log file for detail')

    # to make sure that nailgun is properly started before adding the
    # classpath
    print("adding classpath to nailgun")
    sleep(2)

    ng_cp_template = "ng ng-cp {0} &> /dev/null"
    ng_cp_instance = ng_cp_template.format(jar )
    res = subprocess.call(ng_cp_instance, shell=True)
    if not res == 0:
        logging.critical(
                'could not add {0} to the nailgun classpath. Is the '\
                'path to the .jar correct?.'.format(jar))
        die('critical:could not configure nailgun. See log file for'\
        'detail')

    logging.info('successfully started and configured nailgun')
    sleep(1)
    return

def nailgunstop():
    """
    shutdown nailgun .
    """

    subprocess.call("ng ng-stop &> /dev/null", shell=True)
    return

def die(msg, error_code=-1):
    """ print an error message on stderr and exit the program with a
    non 0 error code. Default error code is -1"""

    sys.stderr.write("{0}\n".format(msg))
    exit(error_code)

def list_guide(path, guide_name):
    """
    returns a list of all the mtrip guide files that can be found under
    path.
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

