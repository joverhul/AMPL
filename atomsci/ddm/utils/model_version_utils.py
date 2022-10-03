"""
model_version_utils.py

Misc utilities to get the AMPL model version:

To check the model version

 usage: model_version_utils.py [-h] -i INPUT

 optional arguments:
   -h, --help            show this help message and exit

  -i INPUT, --input INPUT     input directory/file (required)

"""

import argparse
import traceback
import tarfile
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import logging
import pandas as pd
import pdb
import re

logging.basicConfig()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata # python<=3.7


# ampl versions compatible groups
comp_dict = { '1.2': 'group1', '1.3': 'group1', '1.4': 'group2', '1.5': 'group2' }
version_pattern = re.compile(r"[\d.]+")

def get_ampl_version():
    """
    Get the running ampl version

    Returns:
         the AMPL version
    """
    return metadata.version("atomsci-ampl")

def get_ampl_version_from_dir(dirname):
    """
    Get the AMPL versions from a directory

    Args:
        dirname (str): directory
    
    Returns:
        list of AMPL versions
    """
    versions = []
    # loop
    for path in Path(dirname).rglob('*.tar.gz'):
        try:
            version = get_ampl_version_from_model(path.absolute())
            versions.append('{}, {}'.format(path.absolute(), version))
        except (json.decoder.JSONDecodeError, FileNotFoundError) as e:
            logger.exception("Exception message: {}".format(e))
            pass
            
    return '\n'.join(versions)

def get_ampl_version_from_model(filename):
    """
    Get the AMPL version from the tar file's model_metadata.json

    Args:
        filename (str): tar file
    
    Returns:
        the AMPL version number
    """
    tmpdir = tempfile.mkdtemp()
        
    model_fp = tarfile.open(filename, mode='r:gz')
    model_fp.extractall(path=tmpdir)
    model_fp.close()
        
    # make metadata path
    metadata_path = os.path.join(tmpdir, 'model_metadata.json')
    version = get_ampl_version_from_json(metadata_path)
    logger.info('{}, {}'.format(filename, version))
    return version

def get_ampl_version_from_json(metadata_path):
    """
    Parse model_metadata.json to get the AMPL version

    Args:
        filename (str): tar file
    
    Returns:
        the AMPL version number
        
    """
    with open(metadata_path, 'r') as data_file:
        metadata_dict = json.load(data_file)
        version = metadata_dict.get("model_parameters").get("ampl_version", 'probably 1.0.0')
        return version

def validate_version(input):
    valid = re.fullmatch(version_pattern, input)
    if valid is None:
        raise ValueError("Input {} is not valid version format.".format(input))
    return True

def check_version_compatible(input, ignore_check=False):
    """
    Compare the input file's version against the running AMPL version to see if
    they are compatible

    Args:
        filename (str): file or version number
    
    Returns:
        True if the input model version matches the compatible AMPL version group
    
    """
    # get the versions. only compare by the major releases
    model_ampl_version = ""
    # if the input is a tar file, extract it to get the version string
    if (os.path.isfile(input)):
        model_ampl_version = get_ampl_version_from_model(input).strip()[:3]
    else:
        # if the input is not a file. try to parse string like '1.5.0'
        validate_version(input)
        model_ampl_version = input[:3]

    ampl_version = get_ampl_version()[:3]
    logger.info('Version compatible check: {} version = "{}", AMPL version = "{}"'.format(input, model_ampl_version, ampl_version))
    match = (comp_dict[ampl_version]==comp_dict[model_ampl_version])
    
    # raise an exception if not match and we don't want to ignore
    if not match:
        if not ignore_check:
            my_error = ValueError('Version compatible check: {} version: "{}" not matching AMPL compatible version group: "{}"'.format(input, model_ampl_version, ampl_version))
            raise my_error
    return match

#----------------
# main
#----------------
def main(argv):

    # input file/dir (required)
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='input model directory/file')

    args = parser.parse_args()

    finput = args.input

    # check if it's a directory
    if os.path.isdir(finput):
        get_ampl_version_from_dir(finput)
    elif os.path.isfile(finput):
        get_ampl_version_from_model(finput)

if __name__ == "__main__":
   main(sys.argv[1:])
