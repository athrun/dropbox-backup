What this script does
======================

This script will download the content of an user's dropbox into
a local directory for backup purposes.
This script can be useful on systems where it is not possible to run
the official dropbox client, like NAS systems using PPC CPUs.

How to use
===========

    usage: dl_dropbox.py [-h] folder

    This tool will backup the content of an user's dropbox to a specified local
    directory.

    positional arguments:
      folder      destination backup directory

    optional arguments:
      -h, --help  show this help message and exit


Here is an example showing basic usage:

    ./dropbox-backup.py /path/to/backup/folder

This will download the entire content of the user's dropbox in the specified folder.

Note:

 * Tool expects a `backup.cfg` file inside the specified directory. See below.
 * The first time the tool is used, it will prompt for access authorization using OAuth.


Syntax of the backup.cfg file
==============================

This file should contain the Dropbox API key and secret that the tool will use to access
dropbox.
It should look like this:

    [dropbox]
    app_key = aa1aaaaa1aaaa
    app_secret = 2b2b2bb2bbb2b2

*Important: This file must be accessible in read/write mode by the tool.*
