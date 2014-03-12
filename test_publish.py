#!/usr/bin/env python3

import json
import mtriputils
from nose import with_setup

from publish import categories


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

    print("guide_result:{}".format(guide_result))
    print("expected_result:{}".format(expected_result))

    assert guide_result == expected_result
    return










