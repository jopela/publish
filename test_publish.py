#!/usr/bin/env python3

import json
import mtriputils
import os
import shutil

from nose import with_setup

from zipfile import ZipFile

from publish import categories
from publish import descriptions_url
from publish import must_remove_attraction
from publish import archive_filename
from publish import remove_from_zip
from publish import remove_street_picture


test_guide_filename = '/root/dev/publish/test-guides/Lisbon-test/result.json'
test_guide_path = '/root/dev/publish/test-guides'


def setup_func():
    """
    create a test guide.
    """

    test_guide = test_guide_filename
    # overwrite the content of this guide with fake poi.
    test_guide_content = {
            "Subjects":
            {},
            "Cities": [
                {"name":"Lisbon",
                "pois": [
                    {
                        "category":"restaurants",
                        "subcategory":"american"
                    },
                    {
                        "category":"restaurants",
                        "subcategory":"pizza"
                    },
                    {
                        "category":"entertainment",
                        "subcategory":"bar"
                    },
                    {
                        "category":"shopping",
                        "subcategory":"electronic"
                    },
                    ]
                }]
            }

    # dump the content into the file.

    with open(test_guide,'w') as fileguide:
        json.dump(test_guide_content, fileguide)

    return

def tear_down():
    """
    does nothing, successfully.
    """
    return


@with_setup(setup_func, tear_down)
def test_categories():
    single_guide_name = test_guide_filename
    guide_name = 'result.json'
    guides = mtriputils.list_guides(test_guide_path, guide_name)

    expected_result = {
                "restaurants": ["american", "pizza"],
                "entertainment" : ["bar"],
                "shopping" : ["electronic"]
            }

    result = categories(guides)

    # get the subject part of the guide we just modified
    test_guide_content = None
    with open(single_guide_name,'r') as fileguide:
        test_guide_content = json.load(fileguide)

    # get the subject section from the guide
    guide_result = test_guide_content['Subjects']

    assert guide_result == expected_result
    return

def test_descriptions_url():

    expected = ['http://wikipedia.org/wiki/Montreal',
                'http://wikitravel.org/wiki/Montreal']

    descriptions = {"fr":
                    {"source":
                        {"url":expected[1]}},
                    "en":
                    {"source":
                        {"url":expected[0]}}}


    result = descriptions_url(descriptions)


    return


def test_must_remove_attraction():

    poi = {
                    "category": "attractions",
                    "ranking": 1355,
                    "duration": 20,
                    "price_range": 'null',
                    "homepage": {
                        "homepage": 'null'
                    },
                    "descriptions": {
                        "fr": {
                            "source": {
                                "url": "http://facebook.com/159772950715149",
                                "source": "Facebook",
                                "id": 10809262
                            },
                            "text": "Mairie des Lilas est une station du métro de Paris sur la ligne 11, dans la commune des Lilas."
                        }
                    }
                }

    result = must_remove_attraction(poi)
    assert result

    return

def test_must_not_remove_attraction():

    poi = {
                    "category": "attractions",
                    "ranking": 19,
                    "duration": 20,
                    "price_range": 'null',
                    "homepage": {
                        "homepage": 'null'
                    },
                    "descriptions": {
                        "fr": {
                            "source": {
                                "url": "http://facebook.com/159772950715149",
                                "source": "Facebook",
                                "id": 10809262
                            },
                            "text": "Mairie des Lilas est une station du métro de Paris sur la ligne 11, dans la commune des Lilas."
                        },
                        "en" :{
                            "source":{
                                "url":"http://wikitravel.org/lol",
                                "source":"Facebook",
                                "id":10292929292
                                }
                            }
                        }
                    }


    result = must_remove_attraction(poi)
    assert not result

    return

def test_must_not_remove_attraction_wiki():

    poi = {
                    "category": "attractions",
                    "ranking": 1000,
                    "duration": 20,
                    "price_range": 'null',
                    "homepage": {
                        "homepage": 'null'
                    },
                    "descriptions": {
                        "fr": {
                            "source": {
                                "url": "http://facebook.com/159772950715149",
                                "source": "Facebook",
                                "id": 10809262
                            },
                            "text": "Mairie des Lilas est une station du métro de Paris sur la ligne 11, dans la commune des Lilas."
                        },
                        "en" :{
                            "source":{
                                "url":"http://wikipedia.org/lol",
                                "source":"Facebook",
                                "id":10292929292
                                }
                            }
                        }
                    }


    result = must_remove_attraction(poi)
    assert not result

    return


def test_archive_filename():
    expected = '/data/guide/lol/pics.zip'
    arg = '/data/guide/lol/result.json'

    result = archive_filename(arg)

    assert result == expected
    return

def test_remove_from_zip_setup():
    # create 2 files, hello world and wrtie inside them their content.

    test_dir = '/tmp/test_archive'

    # create the directory. Dont flip out if already exists.
    os.makedirs(test_dir, exist_ok = True)
    files = ['hello.txt','world.txt']

    absolute_files = [os.path.join(test_dir, f) for f in files]

    for f in absolute_files:
        with open(f,'w+') as file_name:
            file_name.write('hello world\n')

    # create a zip archive with those file.
    with ZipFile(os.path.join(test_dir,'pics.zip'),'w') as z:
        for f in absolute_files:
            z.write(f,os.path.basename(f))

    # delete the files from the folder.
    for f in absolute_files:
        os.remove(f)

    return

def test_remove_zip_teardown():

    # Remove the archive from the tmp destination.
    test_dir = '/tmp/test_archive'
    shutil.rmtree(test_dir)

    return

@with_setup(test_remove_from_zip_setup, test_remove_zip_teardown)
def test_remove_zip():
    """
    must remove the given filenames from the archive
    """

    guide_name = '/tmp/test_archive/result.json'
    removed_pic_name = ['hello.txt']

    # call the function.
    remove_from_zip(guide_name, removed_pic_name)

    # now get the content of the archive and make sure it only contains
    # world.txt
    archive_name = archive_filename(guide_name)
    content = None
    with ZipFile(archive_name, 'r') as z:
        content = z.namelist()

    assert content == ['world.txt']
    return

def test_remove_street_picture_setup():

    test_dir = '/tmp/testguide'

    # Recursively copy the content of Test guide into the test temp folder.
    shutil.copytree('/data/guides/Testguide',test_dir)
    return

def test_remove_street_picture_teardown():

    test_dir = '/tmp/testguide'
    shutil.rmtree(test_dir)
    return

@with_setup(test_remove_street_picture_setup, test_remove_street_picture_teardown)
def test_remove_street_name():

    guides = ['/tmp/testguide/Paris-267/result.json']

    # call the function with side effect.
    remove_street_picture(guides)

    # make sure the guide contains no picture when is has subcategory
    # street

    def has_street_pic(guides):
        content = None
        for g in guides:
            with open(g,'r') as guide:
                content = json.load(guide)

            pois = content['Cities'][0]['pois']
            for p in pois:
                sub = p.get('subcategory')
                pic = p.get('picture')

                if sub == 'street' and pic:
                    return True

        return False

    assert not has_street_pic(guides)
    return
