#~
#~ TransmissionRPC Lite library
#~ Taken from CouchPotatoServer
#~ https://github.com/RuudBurger/CouchPotatoServer.git
#~ 67612fce986449462686747ee0183556b62cf262
#~


from base64 import b64encode
import httplib
import json
import os.path
import re
import urllib2
import logging

class TransmissionRPCLite(object):

    """TransmissionRPC lite library"""

    def __init__(self, host = 'localhost', port = 9091, username = None, password = None):

        super(TransmissionRPCLite, self).__init__()

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
            self.log().debug('User or password missing, not using authentication.')
        self.session = self.get_session()

    def _request(self, ojson):
        self.tag += 1
        headers = {'x-transmission-session-id': str(self.session_id)}
        request = urllib2.Request(self.url, json.dumps(ojson).encode('utf-8'), headers)
        try:
            open_request = urllib2.urlopen(request)
            response = json.loads(open_request.read())
            self.log().debug('response: %s', json.dumps(response))
            if response['result'] == 'success':
                self.log().debug('Transmission action successfull')
                return response['arguments']
            else:
                self.log().debug('Unknown failure sending command to Transmission. Return text is: %s', response['result'])
                return False
        except httplib.InvalidURL, err:
            self.log().error('Invalid Transmission host, check your config %s', err)
            return False
        except urllib2.HTTPError, err:
            if err.code == 401:
                self.log().error('Invalid Transmission Username or Password, check your config')
                return False
            elif err.code == 409:
                msg = str(err.read())
                try:
                    self.session_id = \
                        re.search('X-Transmission-Session-Id:\s*(\w+)', msg).group(1)
                    self.log().debug('X-Transmission-Session-Id: %s', self.session_id)

                    # #resend request with the updated header

                    return self._request(ojson)
                except:
                    self.log().error('Unable to get Transmission Session-Id %s', err)
            else:
                self.log().error('TransmissionRPC HTTPError: %s', err)
        except urllib2.URLError, err:
            self.log().error('Unable to connect to Transmission %s', err)

    def get_session(self):
        post_data = {'method': 'session-get', 'tag': self.tag}
        return self._request(post_data)

    def add_torrent_uri(self, torrent, arguments):
        arguments['filename'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        return self._request(post_data)

    def add_torrent_file(self, torrent, arguments):
        arguments['metainfo'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        return self._request(post_data)

    def set_torrent(self, torrent_id, arguments):
        arguments['ids'] = torrent_id
        post_data = {'arguments': arguments, 'method': 'torrent-set', 'tag': self.tag}
        return self._request(post_data)

    def log(self):
        return logging.getLogger(__name__)

