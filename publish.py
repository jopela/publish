#!/usr/bin/env python3
# -*- coding:utf-8 -*-
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
import collections
import iso3166
import shutil

from zipfile import ZipFile
from progress.bar import Bar
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

    mbroker_username_default = 'guest'
    parser.add_argument(
            '-U',
            '--mbroker-username',
            help='username used to access the message broker for RPC.'\
                    ' Default to {}.'.format(mbroker_username_default),
            default = mbroker_username_default
            )

    mbroker_password_default = 'guest'
    parser.add_argument(
            '-P',
            '--mbroker-password',
            help='password used to access the message broker for RPC.'\
                    'Default to {}.'.format(mbroker_password_default),
            default = mbroker_password_default
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

    default_endpoint = 'http://localhost:8890/sparql'
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

    default_wikison_jar = '/usr/share/java/wikison-0.1.1-standalone.jar'
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

    publish_choices = (
            'description',
            'editorial',
            'zipcode-remove',
            'banner',
            'homepage-remove',
            'categories',
            'iso3166',
            'guesslang',
            'attraction-remove',
            'remove-street-pic'
            #'city-name-translation'
            )

    parser.add_argument(
            '-p',
            '--publish-functions',
            help='the set of publish operation to perform. '\
                    'Defaults to {0}'.format(publish_choices),
            nargs='+',
            default=publish_choices
            )

    default_homepage_domains = ["facebook", "yelp"]
    parser.add_argument(
            '-H',
            '--homepage-domains',
            help='domains of the hompage urls that need to be removed',
            nargs='+',
            default=default_homepage_domains
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
            args.description_gen,
            args.homepage_domains,
            args.mbroker_username,
            args.mbroker_password)

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
            description_gen,
            homepage_domains,
            mbroker_username,
            mbroker_password):
    """
    Runs the publishing operation on the given directory path.
    """

    guides = list_guide(path,guide_name)
    error = False

    if 'description' in publish_functions:
        logging.info('starting description content generation')
        error |= description_publish(guides,
                                     user_agent,
                                     function_description_class,
                                     nailgun_bin,
                                     description_gen)

    if 'attraction-remove' in publish_functions:
        logging.info('starting attraction remove')
        error |= filter_poi(guides, must_remove_attraction)

    if 'remove-street-pic' in publish_functions:
        logging.info('starting removal of street pic remove')
        error |= remove_street_picture(guides)

    if 'banner' in publish_functions:
        logging.info('starting banner fetching for the guides')
        error |= banner(guides,
                        endpoint,
                        function_description_class,
                        user_agent,
                        nailgun_bin,
                        description_gen)

    if 'zipcode-remove' in publish_functions:
        logging.info('starting zipcode cleanup')
        error |= zipclean.zipclean(path, guide_name)

    if 'homepage-remove' in publish_functions:
        logging.info('starting homepage cleanup')
        error |= remove_homepage_from_domains(guides, homepage_domains)

    if 'categories' in publish_functions:
        logging.info('starting guide categories cleanup')
        error |= categories(guides)

    if 'iso3166' in publish_functions:
        logging.info('starting iso3166 alpha2 appending')
        error |= country_code(guides)

    if 'guesslang' in publish_functions:
        logging.info('starting language guessing for poi name')
        error |= guesslang(path, mbroker_username, mbroker_password)

    if 'editorial' in publish_functions:
        logging.info('starting editorial content generation')
        error |= editorial_publish(guides,
                                   endpoint,
                                   function_class,
                                   user_agent,
                                   nailgun_bin,
                                   content_generator)
    if error:
        print('the software encountered errors during guide publication.'\
                ' please see the log file ({0}) for more details'.format(
                    log_file))

    logging.info('publish operation finished')
    nailgunstop()
    return



def guesslang(path,username, password):
    """
    Lang guess script on every file.
    """

    lang_client = "lang_publish.py -u {} -p {} {}".format(
            username,
            password,
            path)

    status = subprocess.call(lang_client, shell=True)
    return False

def city_name_translation(guides):
    return

def filter_poi(guides, f):
    """
    Remove certain POIS based on a filter function. Filter function should
    return True if the poi should be REMOVED.
    """
    nbr_guides = len(guides)

    bar = Bar('filtering the guides poi with a function.',max=nbr_guides)
    Error = False

    bar.start()

    for g in guides:
        cur_content = None
        with open(g,'r') as file_guide:
            cur_content = json.load(
                    file_guide,
                    object_pairs_hook=collections.OrderedDict)

        if not cur_content:
            logging.error('could not load content for:{}. POI not filtered'.format(g))

        else:

            # get the POI.
            guide_pois = None
            try:
                guide_pois = cur_content['Cities'][0]['pois']
            except:
                logging.error('{} did not contain any POI. They will not be filtered'.format(g))
                bar.next()
                continue

            new_pois = [p for p in guide_pois if not f(p)]
            cur_content['Cities'][0]['pois'] = new_pois

            # reserialize the guide content.
            with open(g,'w') as file_guide:
                json.dump(cur_content, file_guide)

        bar.next()


    bar.finish()
    return Error

def must_remove_attraction(poi):
    """
    returns true if we must drop the attraction POI
    """

    category = poi.get('category',None)

    if category != 'attractions':
        return False

    descriptions = poi.get('descriptions',None)

    if not descriptions:
        return True

    urls = descriptions_url(descriptions)

    wikipedias = ['wikipedia.org' in url for url in urls if url]
    has_wikipedia = any(wikipedias)

    wikitravels = ['wikitravel.org' in url for url in urls if url]
    has_wikitravel = any(wikitravels)

    rank_limit = 20
    ranking = poi.get('ranking',rank_limit+1)

    export = has_wikipedia or (has_wikitravel and (ranking < rank_limit))

    return not export

def descriptions_url(descriptions):
    """
    Returns the descriptions urls located in a description dictionary.
    """
    urls = []

    for k,v in descriptions.items():
        try:
            url = v['source']['url']
            urls.append(url)
        except:
            continue
    return urls

def country_code(guides):
    """
    Adds the country code to all the city guides.
    """
    nbr_guides = len(guides)
    error = False

    # prepare the progress bar.
    bar = Bar('adding country codes to city guides', max=nbr_guides)

    for g in guides:
        cur_content = None
        with open(g,'r') as file_guide:
            cur_content = json.load(file_guide,object_pairs_hook=collections.OrderedDict)

        if not cur_content:
            logging.error('could not load content for:{}.This guide will.'\
                    'not contain an ISO3166 alpha2 country code'.format(g))
            bar.next()
            error = True
            continue

        # compute the iso 3166 alpha2 of the country code based on the country
        # attribute of the guide.
        country = None
        try:
            country = cur_content['Cities'][0]['country']
        except:
            logging.error('Could not retrieve country name for:{}. This guide'\
                    ' will not contain an ISO3166 alpha2' \
                    ' country code'.format(g))
            bar.next()
            error = True
            continue

        # handle the special cases here
        if country == 'Congo, The Democratic Republic Of The':
            alpha2 = 'CD'
        else:
            try:
                alpha2 = iso3166.countries[country].alpha2
            except:
                logging.error('The country name {} could'\
                        ' not be mapped to an iso3166 alpha2 country code.'\
                        ' guide {} will not contain a'\
                        ' country code.'.format(country,g))
                bar.next()
                error = True
                continue

        # insert the alpha2 code into the guide.
        cur_content['Cities'][0]['alpha2'] = alpha2

        # reserialize the guide content.
        with open(g,'w') as file_guide:
            json.dump(cur_content, file_guide)

        bar.next()

    return error

def categories(guides):
    """
    collect categories/subcategories from the guides and serialize them
    on top.
    """

    error = False
    for guide in guides:
        cur_guide_content = None
        subjects = dict()

        with open(guide,'r') as fileguide:
            cur_guide_content = json.load(fileguide, object_pairs_hook=collections.OrderedDict)
            cur_guide_content = dict(cur_guide_content)

        if not cur_guide_content:
            logging.error('no content found in {}'.format(guide))
            continue

        try:
            guide_pois = cur_guide_content['Cities'][0]['pois']
        except Exception as e:
            logging.error('could not get a hold on the pois for {}. Guide will not be considered'.format(guide))
            error = True
            continue

        for poi in guide_pois:
            category = poi.get("category", None)
            if category:
                # just add the category to the subjects if not already in.
                if not category in subjects:
                    subjects[category] = set()

                subcategory = poi.get("subcategory", None)
                if subcategory:
                    subjects[category].add(subcategory)

            else:
                continue

        guide_subject = cur_guide_content.get('Subjects', None)
        if guide_subject == None:
            error = True
            logging.error('could not get a hold of the guide subject for {}. Categories rectification ignored for this guide'.format(guide))
            continue
        else:
            new_subjects = dict()
            for k,v in subjects.items():
                new_subjects[k] = list(v)


            # Assign the current guide subjects.
            cur_guide_content['Subjects'] = new_subjects

            # reserialize the guide.
            with open(guide,'w') as fileguide:
                json.dump(cur_guide_content, fileguide)

    return error

def banner(guides,
           endpoint,
           function_description_class,
           user_agent,
           nailgun_bin,
           description_gen):
    """
    Insert a banner picture into a guide and download it on the file system.
    """

    nailguninit(nailgun_bin, description_gen)

    error = False
    pbar = Bar('fetching the depiction banner for the guides',max=len(guides)+1)
    pbar.start()

    for i, g in enumerate(guides):
        url = depiction_url(g, user_agent, function_description_class,
                endpoint)
        if url:
            guide_folder = os.path.dirname(g)
            filename = url_filename(url)
            error = download(guide_folder, filename, url)
            error |= zip_insert(guide_folder, filename)
            error |= remove_banner(guide_folder, filename)
            if error:
                logging.error('could not download/insert/remove {0}. There '\
                        'will be no banner for {1}'.format(url, g))
                insert_error = jsonsert.imagesert(g, None, None)

            else:
                logging.info('inerting details into the guide {0}'.format(g))
                insert_error = jsonsert.imagesert(g, filename, url)

        else:
            logging.error('could not find a depiction image for {0} so there will be no banner'.format(g))
            insert_error = jsonsert.imagesert(g, None, None)
            error = True

        if insert_error:
            logging.error("problem inserting the image into {0}".format(g))
            error = True

        pbar.next()


    pbar.finish()
    return error

def remove_banner(guide_folder, filename):
    """
    remove the banner file from the folder of the guide.
    """

    absolute_filename = os.path.join(guide_folder, filename)

    remove_template = "rm -f {0}"
    remove_instance = remove_template.format(absolute_filename)

    status = subprocess.call(remove_instance, shell=True)

    error = status != 0
    return error

def depiction_url(guide_filename, user_agent, classpath, endpoint):
    """
    Uses the description generator to retrieve the depiction url of the
    guide.
    """

    content = None
    with open(guide_filename,'r') as guide_file:
        content = json.load(guide_file, object_pairs_hook = collections.OrderedDict)
    if not content:
        logging.error("could not load json guide from {0}."\
                " No depiction url can be found".format(guide_filename))
        return None

    search = cityinfo.cityinfo(content)
    uri = cityres.cityres(search, endpoint)

    if not uri:
        logging.error("could not find a dbpedia resource for {0}."\
                " No depiction url can be found.".format(guide_filename))
        return None

    unquoted_uri = unquote(uri)
    # infer the english wikivoyage from the uri.
    wiki_urls = urlinfer.urlinferwiki([unquoted_uri])

    wikivoyage = "wikivoyage"
    wikipedia = "wikipedia"

    wikivoyage_urls = [u for u in wiki_urls if wikivoyage in urlparse(u).netloc]
    wikipedia_urls = [u for u in wiki_urls if wikipedia in urlparse(u).netloc]


    depiction_url = None

    if len(wikivoyage_urls) > 0:
        depiction_url = depiction_source(wikivoyage_urls[0],
                classpath,
                user_agent)
    if len(wikipedia_urls) > 0 and not depiction_url:
        depiction_url = depiction_source(wikipedia_urls[0],
                classpath,
                user_agent)

    if not depiction_url:
        logging.error("could not infer a depiction source for {0}.".format(guide_filename))

    return depiction_url

def depiction_source(src, classpath, user_agent):
    """
    returns a depiction url from the src. Will return None if not found."
    """

    depiction_template = "ng-nailgun {0} -u '{1}' -d '{2}' &> /dev/null"
    depiction_instance = depiction_template.format(classpath, user_agent ,src)

    result = subprocess.check_output(depiction_instance,
                                     shell=True,
                                     universal_newlines=True)
    if result == 'nil\n':
        logging.error("wikison returned nil for {0}".format(src))
        return None

    result = unquote(result.strip())
    return result

def download(folder, filename, url):
    """
    Uses wget to fetch the url content and saves it to folder under filename.
    inserts it into the pics.zip file
    """

    absolute_filename = os.path.join(folder, filename)

    wget_template = "wget -O {0} {1}"
    wget_instance = wget_template.format(absolute_filename, url)

    status = subprocess.call(wget_instance, shell = True)
    error = status != 0
    return error

def zip_insert(folder, filename, zipname='pics.zip'):
    """
    inserts the banner into the already existing pics.zip file. Create the
    pics.zip file if it does not exist.
    """

    absolute_zipname = os.path.join(folder,zipname)
    absolute_filename = os.path.join(folder,filename)

    zip_insert_template = "zip -g -j {0} {1}"
    zip_insert_instance = zip_insert_template.format(
            absolute_zipname,
            absolute_filename
            )

    logging.info("insert zip with {0}".format(zip_insert_instance))
    status = subprocess.call(zip_insert_instance, shell = True)
    error = status != 0
    return error

def url_filename(url):
    """
    returns an appropriate filename for the given url.

    Example
    =======

    >>> url_filename("http://mycooldomain.com/path/to/file.jpg")
    'file.jpg'

    >>> url_filename("http://mycooldomain.com/api.php?param=1")
    'api.php'

    >>> url_filename(";asddasdad")
    ''

    """

    parsed = urlparse(url)
    split_path = parsed.path.split('/')

    filename = ''
    if len(split_path) > 1:
        filename = split_path[-1]

    return filename

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

        # notice the 0 index here. This is ok because there is only one city
        # per guide. Maybe that will not be the case in the future.
        pois = jsonguide['Cities'][0]['pois']

        pbar = Bar('extracting description for the poi(s) in {0}:'.format(g),max=len(pois)+1)
        pbar.start()
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
                        v['text'] = content.get('article',None)
                        v['source']['url'] = content.get('url',None)

            pbar.next()

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
    ed_gen_template = 'ng-nailgun {0} -u "{1}" -m {2} &> /dev/null'
    ed_gen_instance = ed_gen_template.format(class_path, user_agent, urls_args)

    content = subprocess.check_output(ed_gen_instance, shell=True,
            universal_newlines=True)

    return content


def guide_content(guide):
    """
    return the content of a guide.
    """

    content = None
    with open(guide,'r') as file_guide:
        content = json.load(file_guide,
                object_pairs_hook = collections.OrderedDict)

    if not content:
        logging.error('problem while loading the content for {}'.format(guide))
        return None
    else:
        return content


def remove_street_picture(guides):
    """
    Remove pictures from the poi when the subcategory is street.
    """

    removed_pic_name = []
    Error = False
    bar = Bar('removing street pics',max=len(guides))
    bar.start()
    for guide in guides:
        content = guide_content(guide)
        if not content:
            continue
        else:
            # get the pois
            pois = None
            try:
                pois = content['Cities'][0]['pois']
            except Exception as e:
                logging.error('guide {} did not contain pois. Street picture'\
                        ' will not be removed.'.format(guide))
                bar.next()
                continue

            for p in pois:
                sub = p.get('subcategory')
                if sub == 'street':
                    try:
                        pic = p['picture']['picture']
                        removed_pic_name.append(pic)
                        p.pop('picture')
                    except Exception as e:
                        continue

            # reserialize the content.
            with open(guide, 'w') as file_guide:
                json.dump(content,file_guide)

            #remove_from_zip(guide, removed_pic_name)

        bar.next()

    bar.finish()

    return Error

def archive_filename(guide_filename):
    """
    return the full path of the archive given guide_filename.
    """

    archive_name = 'pics.zip'
    dirname = os.path.dirname(guide_filename)

    arch_filename = os.path.join(dirname,archive_name)
    return arch_filename


def remove_from_zip(guide, removed_pic_name):
    """
    Los Pollos Hermanos.
    """

    # Get the filename of the tar archive.
    archive_name = archive_filename(guide)
    pic_set = set(removed_pic_name)

    tmp_dest = '/tmp/pictures'
    with ZipFile(archive_name, 'r') as z:
        new_files = [n for n in z.namelist() if n not in pic_set]
        z.extractall(tmp_dest, new_files)

    with ZipFile(archive_name, 'w') as z:
        for f in new_files:
            z.write(os.path.join(tmp_dest, f),arcname=f)

    # Delete the content of the tmp destination.
    shutil.rmtree(tmp_dest)

    return

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


    searches= {}

    pbar = Bar('extracting editorial content for guides:',max=len(guides)+1)
    pbar.start()

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
        pbar.next()

    pbar.finish()
    return error


def editorial_content(urls, class_path, user_agent):
    """
    from a collection of given url, generate some editorial content.
    """
    quoted_urls = quote_urls(urls)
    urls_args = " ".join(quoted_urls)
    ed_gen_template = 'ng-nailgun {0} -u "{1}" {2} &> /dev/null'
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
    the mtrip datastore machine.
    """

    print("starting nailgun ...")
    subprocess.call("ng-nailgun ng-stop &> /dev/null", shell=True)

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

    ng_cp_template = "ng-nailgun ng-cp {0} &> /dev/null"
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

    subprocess.call("ng-nailgun ng-stop &> /dev/null", shell=True)
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
    directories = [os.path.join(path,d) for d in os.listdir(path) if os.path.isdir(os.path.join(path,d))]

    # get the result filename from the dir
    guides = [guide_file(d,guide_name) for d in directories if guide_file(d, guide_name)]

    return guides

def guide_file(path,guide_name):
    """ Return the json filename guide found in path. None if it cannot be
    found. """

    dir_content = [os.path.join(path,content) for content in os.listdir(path) if guide_name in os.path.join(path,content)]

    if len(dir_content) > 0:
        return dir_content[0]
    else:
        return None

def remove_homepage_guide(guide_name, domains):
    """
    remove the bad homepage from the guide.
    """

    domains_set = set(domains)

    with open(guide_name,'r') as guide:
        content = json.load(guide, object_pairs_hook = collections.OrderedDict)

    if not content:
        error = True
        return error

    pois = None

    try:
        pois = content['Cities'][0]['pois']
    except KeyError:
        logging.error('{0} contained no POIs. Skipping'.format(guide_name))
        error = True
        return error

    for poi in pois:
        try:
            homepage = poi['homepage']['homepage']
            parsed_homepage = urlparse(homepage)
            full_homepage_domain = parsed_homepage.netloc
            tld = full_homepage_domain.split(".")[-2]
            if tld in domains_set:
                poi['homepage'] = {"homepage" : None}
        except Exception:
            pass

    error = True
    with open(guide_name,'w') as guide:
        json.dump(content,guide)
        error = False

    return error

def remove_homepage_from_domains(guides,domains):
    """
    for all the guides, will remove the homepage of the poi that match a
    given domain.
    """
    pbar = Bar('removing bad homepages from guides',max=len(guides)+1)
    pbar.start()

    error = False
    for i,g in enumerate(guides):
        remove_error = remove_homepage_guide(g,domains)
        if remove_error:
            logging.error("could not remove the bad homepage'\
                    ' from {0}".format(g))
            error |= True

        pbar.next()

    pbar.finish()

    return error

def unquote(uri):
    """
    remove the " at each end of a string if present.
    """
    if len(uri) < 2:
        return uri

    if uri[0] == '"' and uri[-1] == '"':
        return uri[1:-1]

if __name__ == '__main__':
    main()

