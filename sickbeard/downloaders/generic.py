# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement # This isn't required in Python 2.6

import datetime
import os
import sys
import re
import urllib2
import copy
import traceback
import re
import base64

import sickbeard

from sickbeard import helpers, classes, logger, db

from sickbeard.common import Quality, MULTI_EP_RESULT, SEASON_RESULT
from sickbeard import tvcache
from sickbeard import encodingKludge as ek
from sickbeard.exceptions import ex

from lib.hachoir_parser import createParser

from sickbeard.name_parser.parser import NameParser, InvalidNameException

class GenericDownloader:

    NZB = "nzb"
    TORRENT = "torrent"
    VOD = "strm"    # just to keep SB happy, not really an extension like the other two.

    def __init__(self, name):

        # these need to be set in the subclass
        self.downloaderType = None
        self.name = name
        self.url = ''

        self.supportsBacklog = False

        self.cache = tvcache.TVCache(self)

    def getID(self):
        return GenericDownloader.makeID(self.name)

    @staticmethod
    def makeID(name):
        return re.sub("[^\w\d_]", "_", name).lower()

    def imageName(self):
        return self.getID() + '.png'

    def _checkAuth(self):
        return

    def isActive(self):
        if self.downloaderType == GenericDownloader.NZB and sickbeard.USE_NZBS:
            return self.isEnabled()
        elif self.downloaderType == GenericDownloader.TORRENT and sickbeard.USE_TORRENTS:
            return self.isEnabled()
        elif self.downloaderType == GenericDownloader.VOD and sickbeard.USE_VODS:
            return self.isEnabled()
        else:
            return False

    def isEnabled(self):
        """
        This should be overridden and should return the config setting eg. sickbeard.MYPROVIDER
        """
        return False

    def getResult(self, episodes):
        """
        Returns a result of the correct type for this downloader
        """

        if self.downloaderType == GenericDownloader.NZB:
            result = classes.NZBSearchResult(episodes)
        elif self.downloaderType == GenericDownloader.TORRENT:
            result = classes.TorrentSearchResult(episodes)
        elif self.downloaderType == GenericDownloader.VOD:
            result = classes.VODSearchResult(episodes)
        else:
            result = classes.SearchResult(episodes)

        result.downloader = self

        return result


    def getURL(self, url, headers=None):
        """
        By default this is just a simple urlopen call but this method should be overridden
        for downloaders with special URL requirements (like cookies)
        """

        if not headers:
            headers = []

        result = None

        result = helpers.getURL(url, headers)

        if result is None:
            logger.log(u"Error loading "+self.name+" URL: " + url, logger.ERROR)
            return None

        return result

    def downloadResult2(self, result):
        """
        Save the result to disk.
        """

        logger.log(u"Downloading a result from " + self.name+" at " + result.url)

        data = self.getURL(result.url)

        if data == None:
            return False

        # use the appropriate watch folder
        if self.downloaderType == GenericDownloader.NZB:
            saveDir = sickbeard.NZB_DIR
            writeMode = 'w'
        elif self.downloaderType == GenericDownloader.TORRENT:
            saveDir = sickbeard.TORRENT_DIR
            writeMode = 'wb'
        else:
            return False

        # use the result name as the filename
        fileName = ek.ek(os.path.join, saveDir, helpers.sanitizeFileName(result.name) + '.' + self.downloaderType)

        logger.log(u"Saving to " + fileName, logger.DEBUG)

        try:
            fileOut = open(fileName, writeMode)
            fileOut.write(data)
            fileOut.close()
            helpers.chmodAsParent(fileName)
        except IOError, e:
            logger.log("Unable to save the file: "+ex(e), logger.ERROR)
            return False

        # as long as it's a valid download then consider it a successful snatch
        return self._verify_download(fileName)

    def _verify_download(self, file_name=None):
        """
        Checks the saved file to see if it was actually valid, if not then consider the download a failure.
        Returns a Boolean
        """

        logger.log(u"Verifying Download %s" % file_name, logger.DEBUG)

        if self.downloaderType == GenericDownloader.TORRENT:
            # According to /usr/share/file/magic/archive, the magic number for
            # torrent files is
            #    d8:announce
            # So instead of messing with buggy parsers (as was done here before)
            # we just check for this magic instead.
            try:
                with open(file_name, "rb") as f:
                    magic = f.read(11)
                    if magic == "d8:announce":
                        return True
                    else:
                        logger.log("Magic number for %s is not 'd8:announce' got '%s' instead" % (file_name, magic), logger.WARNING)
                        #logger.log(f.read())
                        return False
            except Exception, eparser:
                logger.log("Failed to read magic numbers from file: "+ex(eparser), logger.ERROR)
                logger.log(traceback.format_exc(), logger.DEBUG)
                return False

        return True

    def _get_title_and_url(self, item):
        """
        Retrieves the title and URL data from the item XML node
        item: An xml.dom.minidom.Node representing the <item> tag of the RSS feed
        Returns: A tuple containing two strings representing title and URL respectively
        """
        title = helpers.get_xml_text(item.getElementsByTagName('title')[0])
        try:
            url = helpers.get_xml_text(item.getElementsByTagName('link')[0])
            if url:
                url = url.replace('&amp;','&')
        except IndexError:
            url = None

        return (title, url)


class TorrentDownloader(GenericDownloader):

    def __init__(self, name):

        GenericDownloader.__init__(self, name)

        self.downloaderType = GenericDownloader.TORRENT

    def getHashFromMagnet(self, magnet):
        """
        Pull the hash from a magnet link (if possible).
        Handles the various possible encodings etc.
        (returning a 40 byte hex string).
        Returns None on failure
        """
        logger.log('magnet: ' + magnet, logger.DEBUG)
        info_hash_search = re.search('btih:([0-9A-Z]+)', magnet, re.I)
        if info_hash_search:
            torrent_hash = info_hash_search.group(1)

            # hex hashes will be 40 characters long, base32 will be 32 chars long
            if len(torrent_hash) == 32:
                # convert the base32 to base 16
                logger.log('base32_hash: ' + torrent_hash, logger.DEBUG)
                torrent_hash = base64.b16encode(base64.b32decode(torrent_hash, True))
            elif len(torrent_hash) <> 40:
                logger.log('Torrent hash length (%d) is incorrect (should be 40), returning None' % (len(torrent_hash)), logger.DEBUG)
                return None

            logger.log('torrent_hash: ' + torrent_hash, logger.DEBUG)
            return torrent_hash.upper()
        else:
            # failed to pull info hash
            return None

    def magnetToTorrent(self, magnet):
        """
        This returns a single (best guess) url for a torrent file for the passed-in
        magnet link.
        For now it just uses the first entry from MAGNET_TO_TORRENT_URLS.
        If there's any problem with the magnet link, this will return None.
        """
        torrent_hash = self.getHashFromMagnet(magnet)
        if torrent_hash:
            return MAGNET_TO_TORRENT_URLS[0] % torrent_hash.upper()
        else:
            # failed to pull info hash
            return None

    def urlIsBlacklisted(self, url):
        """
        For now this is just a hackish way of blacklisting direct links to
        extratorrent.com (which, despite appearing to be .torrent links, are
        actualling advertisement pages)
        """
        if url is None:
            return False
        if url.startswith('http://extratorrent.com/') or url.startswith('https://extratorrent.com/'):
            return True
        return False

    def getURL(self, url, headers=None):
        """
        Overridden to deal with possible magnet links (but still best to not
        pass magnet links to this - downloadResult has better handling with fallbacks)
        """
        if url and url.startswith('magnet:'):
            torrent_url = self.magnetToTorrent(url)
            if torrent_url:
                logger.log(u"Changed magnet %s to %s" % (url, torrent_url), logger.DEBUG)
                url = torrent_url
            else:
                logger.log(u"Failed to handle magnet url %s, skipping..." % url, logger.DEBUG)
                return None

        # magnet link fixed, just call the base class
        return GenericDownloader.getURL(self, url, headers)

    def downloadResult2(self, result):
        """
        Overridden to handle magnet links (using multiple fallbacks)
        """
        logger.log(u"Downloading a result from " + self.name+" at " + result.url)

        if result.url and result.url.startswith('magnet:'):
            torrent_hash = self.getHashFromMagnet(result.url)
            if torrent_hash:
                urls = [url_fmt % torrent_hash for url_fmt in MAGNET_TO_TORRENT_URLS]
            else:
                logger.log(u"Failed to handle magnet url %s, skipping..." % torrent_hash, logger.DEBUG)
                return False
        else:
            urls = [result.url]

        # use the result name as the filename
        fileName = ek.ek(os.path.join, sickbeard.TORRENT_DIR, helpers.sanitizeFileName(result.name) + '.' + self.downloaderType)

        for url in urls:
            logger.log(u"Trying d/l url: " + url, logger.DEBUG)
            data = self.getURL(url)

            if data == None:
                logger.log(u"Got no data for " + url, logger.DEBUG)
                # fall through to next iteration
            elif not data.startswith("d8:announce"):
                logger.log(u"d/l url %s failed, not a valid torrent file" % (url), logger.MESSAGE)
            else:
                try:
                    fileOut = open(fileName, 'wb')
                    fileOut.write(data)
                    fileOut.close()
                    helpers.chmodAsParent(fileName)
                except IOError, e:
                    logger.log("Unable to save the file: "+ex(e), logger.ERROR)
                    return False

                logger.log(u"Success with url: " + url, logger.DEBUG)
                return True
        else:
            logger.log(u"All d/l urls have failed.  Sorry.", logger.MESSAGE)
            return False


        return False
