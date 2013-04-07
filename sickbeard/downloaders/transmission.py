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
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import urllib, urllib2, httplib
import json
import re
from xml.dom.minidom import parseString
from datetime import datetime

import sickbeard
import generic

from sickbeard.common import Quality
from sickbeard import logger
from sickbeard import tvcache
from sickbeard.helpers import sanitizeSceneName, get_xml_text
from sickbeard.exceptions import ex

class TransmissionDownloader(generic.TorrentDownloader):
    torrent_trackers = [
        'http://tracker.publicbt.com/announce',
        'udp://tracker.istole.it:80/announce',
        'udp://fr33domtracker.h33t.com:3310/announce',
        'http://tracker.istole.it/announce',
        'http://tracker.ccc.de/announce',
        'udp://tracker.publicbt.com:80/announce',
        'udp://tracker.ccc.de:80/announce',
        'http://exodus.desync.com/announce',
        'http://exodus.desync.com:6969/announce',
        'http://tracker.publichd.eu/announce',
        'http://tracker.openbittorrent.com/announce',
    ]

    def __init__(self):

        generic.TorrentDownloader.__init__(self, "Transmission")

    def isEnabled(self):
        return sickbeard.TRANSMISSION

    def imageName(self):
        return 'missing.png'

    def downloadResult(self, result, folderName=None):
        logger.log(u"result:"+str(result))
        logger.log(u"folderName:"+str(folderName))
        url = result.url

        params = {
            'paused': sickbeard.TRANSMISSION_PAUSED,
            'download-dir': sickbeard.TRANSMISSION_BASEDIR + folderName
        }

        torrent_params = {}
        #~ if sickbeard.TRANSMISSION_RATIO is not 'None':
            #~ torrent_params = {
                #~ 'seedRatioLimit': sickbeard.TRANSMISSION_RATIO,
                #~ 'seedRatioMode': sickbeard.TRANSMISSION_RATIO
            #~ }

        logger.log(u"params: " + str(params), logger.DEBUG)
        logger.log(u"torrent_params: " + str(torrent_params), logger.DEBUG)

        try:
            # create RPC object
            trpc = TransmissionRPC( sickbeard.TRANSMISSION_HOST , \
                                    sickbeard.TRANSMISSION_PORT, \
                                    username = sickbeard.TRANSMISSION_USERNAME, \
                                    password = sickbeard.TRANSMISSION_PASSWORD)

            if 'magnet' in url:
                logger.log(u"begin", logger.DEBUG)
                remote_torrent = trpc.add_torrent_uri(url, arguments = params)
                torrent_params['trackerAdd'] = self.torrent_trackers
            else:
                remote_torrent = trpc.add_torrent_file(b64encode(filedata), arguments = params)

            # Change settings of added torrents
            if torrent_params and remote_torrent is not False:
                trpc.set_torrent(remote_torrent['torrent-added']['hashString'], torrent_params)

            return True
        except Exception, err:
            logger.log('Failed to change settings for transfer: %s' % err, logger.ERROR)
            return False


#~ Original code from CouchPotatoServer
#~ file: CouchPotatoServer/couchpotato/core/downloaders/transmission/main.py
#~ commit: 0eff4f0096b5027d1c1d32a8778ea756644a01e8
class TransmissionRPC(object):

    """TransmissionRPC lite library"""

    def __init__(self, host = 'localhost', port = 9091, username = None, password = None):

        super(TransmissionRPC, self).__init__()

        self.url = 'http://' + host + ':' + str(port) + '/transmission/rpc'
        self.tag = 0
        self.session_id = 0
        self.session = {}
        if username and password:
            password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_manager.add_password(realm = None, uri = self.url, user = username, passwd = password)
            opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(password_manager), urllib2.HTTPDigestAuthHandler(password_manager))
            opener.addheaders = [('User-agent', 'couchpotato-transmission-client/1.0')]
            urllib2.install_opener(opener)
        elif username or password:
            logger.log('User or password missing, not using authentication.')
        self.session = self.get_session()

    def _request(self, ojson):
        self.tag += 1
        headers = {'x-transmission-session-id': str(self.session_id)}
        request = urllib2.Request(self.url, json.dumps(ojson).encode('utf-8'), headers)
        try:
            open_request = urllib2.urlopen(request)
            response = json.loads(open_request.read())
            logger.log('request: %s' % json.dumps(ojson), logger.DEBUG)
            logger.log('response: %s' % json.dumps(response), logger.DEBUG)
            logger.log("transmission response: " +str(response), logger.DEBUG)

            if response['result'] == 'success':
                logger.log('Transmission action successfull', logger.DEBUG)
                return response['arguments']
            else:
                logger.log('Unknown failure sending command to Transmission. Return text is: %s' % response['result'], logger.DEBUG)
                return False
        except httplib.InvalidURL, err:
            logger.log('Invalid Transmission host, check your config %s' % err, logger.ERROR)
            return False
        except urllib2.HTTPError, err:
            if err.code == 401:
                logger.log('Invalid Transmission Username or Password, check your config', logger.ERROR)
                return False
            elif err.code == 409:
                msg = str(err.read())
                try:
                    self.session_id = \
                        re.search('X-Transmission-Session-Id:\s*(\w+)', msg).group(1)
                    logger.log('X-Transmission-Session-Id: %s' % self.session_id, logger.DEBUG)

                    # #resend request with the updated header

                    return self._request(ojson)
                except:
                    logger.log('Unable to get Transmission Session-Id %s' % err, logger.ERROR)
            else:
                logger.log('TransmissionRPC HTTPError: %s' % err, logger.ERROR)
        except urllib2.URLError, err:
            logger.log('Unable to connect to Transmission %s' % err, logger.ERROR)

    def get_session(self):
        post_data = {'method': 'session-get', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def add_torrent_uri(self, torrent, arguments):
        arguments['filename'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def add_torrent_file(self, torrent, arguments):
        arguments['metainfo'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def set_torrent(self, torrent_id, arguments):
        arguments['ids'] = torrent_id
        post_data = {'arguments': arguments, 'method': 'torrent-set', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def get_alltorrents(self, arguments):
        post_data = {'arguments': arguments, 'method': 'torrent-get', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def stop_torrent(self, torrent_id, arguments):
        arguments['ids'] = torrent_id
        post_data = {'arguments': arguments, 'method': 'torrent-stop', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)

    def remove_torrent(self, torrent_id, remove_local_data, arguments):
        arguments['ids'] = torrent_id
        arguments['delete-local-data'] = remove_local_data
        post_data = {'arguments': arguments, 'method': 'torrent-remove', 'tag': self.tag}
        logger.log(u"post_data: " + str(post_data), logger.DEBUG)
        return self._request(post_data)


downloader = TransmissionDownloader()
