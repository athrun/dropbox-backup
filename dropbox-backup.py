#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Cadet"
__version__ = "$Revision: 1.0 $"

# Include the Dropbox SDK libraries
from dropbox import client, rest, session
import sys, os, shutil, urlparse, urllib
import argparse
import logging
import subprocess
import ConfigParser

logging.basicConfig(format='%(levelname)s:%(lineno)d:%(message)s', level=logging.INFO)

CONFIG = {}

ACCESS_TYPE = 'dropbox'
ROOT_DIR = ""
CONFIG_FILE = "backup.cfg"

DBX_CLIENT = None

def setup_argparse ():
    desc = """
    This tool will backup the content of an user's dropbox to a specified local directory.
    """
    global ROOT_DIR
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument ("folder", help="destination backup directory")
    args = parser.parse_args ()
    # Validate and store
    path = os.path.realpath (os.path.normpath (args.folder))
    validate_root_dir (path)
    ROOT_DIR = path

def validate_root_dir (path):
    """ Make sure root dir contains a config file
        with the APP_KEY/APP_SECRET
    """
    global CONFIG
    path = os.path.realpath (os.path.normpath (path))
    try:
        config = ConfigParser.ConfigParser ()
        config.read (os.path.join (path, CONFIG_FILE))
        for (key, value) in config.items ("dropbox"):
            CONFIG[key.upper()] = value
        config.get ("dropbox", "APP_KEY") and config.get ("dropbox", "APP_SECRET")
    except ConfigParser.Error as cpe:
        logging.error ("Unable to load config from %s!", os.path.join (path, CONFIG_FILE))
        logging.error ("%s: %s" % (type (cpe).__name__, cpe.message))
        sys.exit (1)
    except Exception as e:
        raise e

def initialize ():
    global DBX_CLIENT
    sess = session.DropboxSession (CONFIG["APP_KEY"], CONFIG["APP_SECRET"], ACCESS_TYPE)
    sess = handle_oauth (sess)
    DBX_CLIENT = client.DropboxClient(sess)

def handle_oauth (sess):
    """ Retrieve OAUTH token & secret from config
        or retrieve new ones if required.
    """
    global CONFIG
    if not CONFIG.get ("OAUTH_TOKEN") or not CONFIG.get ("OAUTH_TOKEN"):
        # Get a new set of tokens
        request_token = sess.obtain_request_token()
        url = sess.build_authorize_url(request_token)
        print "URL:", url
        print "Please visit this website and press the 'Allow' button"
        print "Then hit 'Enter' here."
        raw_input()

        # This will fail if the user didn't visit
        # the above URL and hit 'Allow'
        access_token = sess.obtain_access_token(request_token)
        tokens = urlparse.parse_qs (access_token)
        for key in tokens.items ():
            CONFIG[key.upper()] = tokens[key]
        save_config (ROOT_DIR)
    else:
        sess.set_token (CONFIG["OAUTH_TOKEN"], CONFIG["OAUTH_TOKEN_SECRET"])

    return sess

def save_config (path):
    """ Save content of CONFIG to CONFIG_FILE.
    """
    config = ConfigParser.SafeConfigParser ()
    config.read (os.path.join (path, CONFIG_FILE))
    if not config.has_section ("dropbox"):
        config.add_section ("dropbox")
    for key in CONFIG.keys():
        config.set ("dropbox", key, CONFIG [key])
    with open (os.path.join (path, CONFIG_FILE), "wb") as configfile:
        config.write (configfile)

def rmtree_safe (path):
    """ Safely remove a folder tree: make sure the folder tree
        is located within ROOT_DIR before acting.
    """
    path = os.path.normpath (path)
    path = os.path.realpath (path)
    if os.path.commonprefix ([ROOT_DIR, path]) != ROOT_DIR:
        logging.warning ("Potentially unsafe operation. Will not remove %s." % path)
        return
    shutil.rmtree (path)

def unlink_safe (path):
    """ Safely unlink a file: make sure the file is located
        within ROOT_DIR before acting.
    """
    path = os.path.normpath (path)
    path = os.path.realpath (path)
    if os.path.commonprefix ([ROOT_DIR, path]) != ROOT_DIR:
        logging.warning ("Potentially unsafe operation. Will not remove %s." % path)
        return
    os.unlink (path)

def _dl_hook (count, block_size, total_size):
    """ Utility function to report the download status
        on stdout.
    """
    p = ((100 * count) * block_size) / total_size
    if p > 100:
        p = 100
    print '\r %3d %%' % p,
    if p == 100:
        print
    sys.stdout.flush()

def fetch_and_save_file (element):
    (i_path, metadata) = element
    path = metadata.get ("path") # to get case-sensitive path
    path_on_fs = os.path.join (ROOT_DIR, path[1:])
    logging.info("Fetching [%s]" % path_on_fs)
    try:
        media = DBX_CLIENT.media (i_path)
        (filename, headers) = urllib.urlretrieve (media["url"], reporthook=_dl_hook)
        subprocess.check_call (["mv", filename, path_on_fs])
    except rest.ErrorResponse as de:
        logging.error ("%s: %s" % (type (de).__name__, de.message))
        raise
    except Exception as e:
        logging.error ("%s: %s" % (type (e).__name__, e.message))
        raise

def get_delta ():
    cursor = CONFIG.get("CURSOR", None)
    logging.info ("Getting Delta information")
    delta = DBX_CLIENT.delta (cursor=cursor)
    while delta.get ("has_more"):
        logging.info ("Getting more delta information")
        delta_plus = DBX_CLIENT.delta (delta.get ("cursor"))
        delta ["has_more"] = delta_plus.get ("has_more")
        delta ["entries"] += delta_plus.get ("entries", [])
    logging.debug (delta)
    return delta

def reset_root_dir ():
    """ Safely removes the content of ROOT_DIR, except for
        the config file.
    """
    if os.path.exists (ROOT_DIR):
        print "Removing content of %s - Yes/No?" % ROOT_DIR
        r = raw_input ("=> ")
        if r.lower () == 'yes':
            for element in os.listdir (ROOT_DIR):
                if element == CONFIG_FILE:
                    continue
                path = os.path.join (ROOT_DIR, element)
                if os.path.isdir (path):
                    rmtree_safe (path)
                else:
                    unlink_safe (path)

def act_on_delta (delta):
    if delta.get ('reset'):
        reset_root_dir ()

    if not os.path.exists (ROOT_DIR):
        print "Creating dropbox root: %s" % ROOT_DIR
        os.makedirs (ROOT_DIR)

    for element in delta.get ("entries"):
        # Go through all entries and deal with
        # them accordingly.
        (i_path, metadata) = element

        if not metadata:
            # This path was deleted since last time
            # we should remove it.
            logging.info ("Removing element %s", i_path)
            path_on_fs = os.path.join (ROOT_DIR, i_path[1:])
            if os.path.exists (path_on_fs):
                logging.warning ("Removing %s" % path_on_fs)
                if os.path.isdir (path_on_fs):
                    logging.warning ("==> shutil.rmtree (path_on_fs)")
                    rmtree_safe (path_on_fs)
                else:
                    logging.warning ("==> os.path.unlink (path_on_fs)")
                    unlink_safe (path_on_fs)
            continue

        path = metadata.get ("path", i_path) # to get case-sensitive path if possible
        path_on_fs = os.path.join (ROOT_DIR, path[1:])
        logging.info ("Processing element %s", path)
        logging.debug ("Path on FS: %s", path_on_fs)

        if metadata.get ("is_dir"):
            # This is a directory, we should create if it
            # doesn't exist (and then apply metadata to it?)
            if os.path.exists (path_on_fs) and not os.path.isdir (path_on_fs):
                # Remove the file
                logging.warning ("Unlink %s" % path_on_fs)
                logging.warning ("os.unlink (path_on_fs)")
                unlink_safe (path_on_fs)

            if not os.path.isdir (path_on_fs):
                # Create the directory
                os.makedirs (path_on_fs)
        else:
            # This is a file.
            if os.path.exists (path_on_fs) and not os.path.isfile (path_on_fs):
                # Remove existing element if it's not a file
                logging.warning ("Removing %s" % path_on_fs)
                logging.warning ("==> shutil.rmtree (path_on_fs)")
                rmtree_safe (path_on_fs)
            if not os.path.exists (os.path.dirname (path_on_fs)):
                # Create folder tree if required
                os.makedirs (os.path.dirname (path_on_fs))

            # Fetch and save file
            fetch_and_save_file (element)

def main ():
    setup_argparse ()
    initialize ()

    # Fetch new entries
    delta = get_delta ()
    act_on_delta (delta)

    # Save cursor status for next time
    CONFIG["CURSOR"] = delta["cursor"]
    save_config (ROOT_DIR)

if __name__ == "__main__":
    try:
        main ()
    except KeyboardInterrupt:
        pass
