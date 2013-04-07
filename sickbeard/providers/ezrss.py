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

import urllib
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

class EZRSSProvider(generic.TorrentProvider):

    def __init__(self):

        generic.TorrentProvider.__init__(self, "EZRSS")

        self.supportsBacklog = True

        self.cache = EZRSSCache(self)

        self.url = 'https://www.ezrss.it/'

        # These are backup feeds, tried in order if the main feed fails.
        # (these just provide "latest", no backlog)
        self.backup_feeds = ['https://rss.thepiratebay.se/user/d17c6a45441ce0bc0c057f19057f95e1',
                             'http://search.twitter.com/search.rss?rpp=30&q=from%3Aeztv_it',
                             'http://feeds.feedburner.com/eztv-rss-atom-feeds?format=xml&max-results=30' ]

    def isEnabled(self):
        return sickbeard.EZRSS

    def imageName(self):
        return 'ezrss.png'

    def getQuality(self, item):

        torrent_node = item.getElementsByTagName('torrent')[0]
        filename_node = torrent_node.getElementsByTagName('fileName')[0]
        filename = get_xml_text(filename_node)

        quality = Quality.nameQuality(filename)

        return quality

    def findSeasonResults(self, show, season):

        results = {}

        if show.air_by_date:
            logger.log(u"EZRSS doesn't support air-by-date backlog because of limitations on their RSS search.", logger.WARNING)
            return results

        results = generic.TorrentProvider.findSeasonResults(self, show, season)

        return results
    def _get_season_search_strings(self, show, season=None):

        params = {}

        if not show:
            return params

        params['show_name'] = sanitizeSceneName(show.name, ezrss=True).replace('.',' ').encode('utf-8')

        if season != None:
            params['season'] = season

        return [params]

    def _get_episode_search_strings(self, ep_obj):

        params = {}

        if not ep_obj:
            return params

        params['show_name'] = sanitizeSceneName(ep_obj.show.name, ezrss=True).replace('.',' ').encode('utf-8')

        if ep_obj.show.air_by_date:
            params['date'] = str(ep_obj.airdate)
        else:
            params['season'] = ep_obj.season
            params['episode'] = ep_obj.episode

        return [params]

    def _doSearch(self, search_params, show=None):

        params = {"mode": "rss"}

        if search_params:
            params.update(search_params)

        searchURL = self.url + 'search/index.php?' + urllib.urlencode(params)

        logger.log(u"Search string: " + searchURL, logger.DEBUG)

        data = self.getURL(searchURL)

        if not data:
            return []

        try:
            parsedXML = parseString(data)
            items = parsedXML.getElementsByTagName('item')
        except Exception, e:
            logger.log(u"Error trying to load EZRSS RSS feed: "+ex(e), logger.ERROR)
            logger.log(u"RSS data: "+data, logger.DEBUG)
            return []

        results = []

        for curItem in items:

            (title, url) = self._get_title_and_url(curItem)

            if not title or not url:
                logger.log(u"The XML returned from the EZRSS RSS feed is incomplete, this result is unusable: "+data, logger.ERROR)
                continue

            results.append(curItem)

        return results

    def _get_title_and_url(self, item):
        (title, url) = generic.TorrentProvider._get_title_and_url(self, item)

        if url and url.startswith(('http://twitter.com/', 'https://twitter.com/')):
            # this feed came from twitter
            #
            # we need to extract the filename and url from the twitter message (the url we have currently is just that of the twitter message,
            # which is of little use to us).
            # The message looks something like this:
            # eztv_it: History Ch The Universe Season 4 08of12 Space Wars XviD AC3 [MVGroup org] - http://t.co/mGTrhB4a
            #
            # Start by splitting the (real) url from the filename
            try:
                title, url = title.rsplit(' - http', 1)
                url = 'http' + url
            except ValueError:
                logger.log(u"Twitter message '%s' could not be split on a http boundary, there'll be no url here, sorry" % (title), logger.MESSAGE)
                url = None

            # Then strip off the leading eztv_it:
            if title.startswith('eztv_it:'):
                title = title[8:]

            # For safety we remove any whitespace too.
            title = title.strip()

            logger.log(u"Extracted the title '%s' and url '%s' from the twitter link"%(title, url), logger.DEBUG)
        else:
            # this feed came from ezrss
            try:
                torrent_node = item.getElementsByTagName('torrent')[0]
                filename_node = torrent_node.getElementsByTagName('fileName')[0]
                filename = get_xml_text(filename_node)

                new_title = self._extract_name_from_filename(filename)
                if new_title:
                    title = new_title
                    logger.log(u"Extracted the name "+title+" from the torrent link", logger.DEBUG)
            except IndexError:
                # we'll get an IndexError above when there's no 'torrent' node,
                # which likely means that this isn't in the special ezrss format.
                # So assume we're working with with a standard rss feed.
                logger.log(u"IndexError while parsing the ezrss feed, maybe it's just standard RSS? Trying that ...", logger.DEBUG)
                (title, url) = generic.GenericProvider._get_title_and_url(self, item)

        # feedburner adds "[eztv] " to the start of all titles, so trim it off
        if title and title[:7] == "[eztv] ":
            title = title[7:]
            logger.log(u"Trimmed [eztv] from title to get %s" % title, logger.DEBUG)

        # ditto VTV:
        if title and title[:6] == "[VTV] ":
            title = title[6:]
            logger.log(u"Trimmed [VTV] from title to get %s" % title, logger.DEBUG)

        return (title, url)

    def _extract_name_from_filename(self, filename):
        name_regex = '(.*?)\.?(\[.*]|\d+\.TPB)\.torrent$'
        logger.log(u"Comparing "+name_regex+" against "+filename, logger.DEBUG)
        match = re.match(name_regex, filename, re.I)
        if match:
            return match.group(1)
        return None


class EZRSSCache(tvcache.TVCache):

    def __init__(self, provider):

        tvcache.TVCache.__init__(self, provider)

        # only poll EZRSS every 15 minutes max
        self.minTime = 15


    def _getRSSData(self):

        def _feed_is_valid(feed):
            #logger.log(u"Checking feed: " + repr(feed), logger.DEBUG)
            try:
                if feed is None:
                    logger.log(u"Feed result is empty!", logger.ERROR)
                    return False

                parsedXML = parseString(feed)

                if parsedXML.documentElement.tagName != 'rss':
                    logger.log(u"Resulting XML isn't RSS, not parsing it", logger.ERROR)
                    return False
                else:
                    items = parsedXML.getElementsByTagName('item')

                    if len(items) > 0:
                        item = items[0]
                        pubDate = get_xml_text(item.getElementsByTagName('pubDate')[0])

                        # pubDate has a timezone, but it makes things much easier if
                        # we ignore it (and we don't need that level of accuracy anyway)
                        pub_date_pieces = pubDate.split(" ")[:-1]
                        p_datetime = datetime.strptime(" ".join(pub_date_pieces), '%a, %d %b %Y %H:%M:%S')
                        p_delta = datetime.now() - p_datetime
                        if p_delta.days > 3:
                            logger.log(u"Last entry in feed (after early parse) is %d days old - assuming feed is broken"%(p_delta.days), logger.MESSAGE)
                            return False
                        else:
                            return True
                    else:
                        logger.log(u"Feed contents are rss (during early parse) but are empty, assuming failure.", logger.MESSAGE)
                        return False

            except Exception, e:
                logger.log(u"Error during early parse of feed: "+ex(e), logger.ERROR)
                logger.log(u"Feed contents: "+repr(feed), logger.DEBUG)
                return False



        url = self.provider.url + 'feed/'

        all_urls = [url] + self.provider.backup_feeds
        for try_url in all_urls:
            logger.log(u"Trying EZRSS URL: " + try_url, logger.DEBUG)
            data = self.provider.getURL(try_url)

            if _feed_is_valid(data):
                logger.log(u"Success with url: " + try_url, logger.DEBUG)
                break;
            else:
                logger.log(u"EZRSS url %s failed" % (try_url), logger.MESSAGE)

        else:
            logger.log(u"All EZRSS urls (including backups) have failed.  Sorry.", logger.MESSAGE)
            data = None

        return data

    def _parseItem(self, item):

        (title, url) = self.provider._get_title_and_url(item)

        if not title or not url:
            logger.log(u"The XML returned from the EZRSS RSS feed is incomplete, this result is unusable", logger.ERROR)
            return

#        if url and url.startswith('magnet:'):
#            torrent_url = self.provider.magnetToTorrent(url)
#            if torrent_url:
#                logger.log(u"Changed magnet %s to %s" % (url, torrent_url), logger.DEBUG)
#                url = torrent_url
#            else:
#                logger.log(u"Failed to handle magnet url %s, skipping..." % url, logger.DEBUG)
#                return

        if url and self.provider.urlIsBlacklisted(url):
            logger.log(u"url %s is blacklisted, skipping..." % url, logger.DEBUG)
            return

        logger.log(u"Adding item from RSS to cache: "+title, logger.DEBUG)

        self._addCacheEntry(title, url)

provider = EZRSSProvider()
