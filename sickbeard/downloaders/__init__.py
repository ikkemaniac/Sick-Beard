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

__all__ = ['transmission',
           ]

import sickbeard

from os import sys

def sortedDownloaderList():

    initialList = sickbeard.downloaderList + sickbeard.newznabDownloaderList
    downloaderDict = dict(zip([x.getID() for x in initialList], initialList))

    newList = []

    # add all modules in the priority list, in order
    for curModule in sickbeard.DOWNLOADER_ORDER:
        if curModule in downloaderDict:
            newList.append(downloaderDict[curModule])

    # add any modules that are missing from that list
    for curModule in downloaderDict:
        if downloaderDict[curModule] not in newList:
            newList.append(downloaderDict[curModule])

    return newList

def makeDownloaderList():

    return [x.downloader for x in [getDownloaderModule(y) for y in __all__] if x]

def getDownloaderModule(name):
    name = name.lower()
    prefix = "sickbeard.downloaders."
    if name in __all__ and prefix+name in sys.modules:
        return sys.modules[prefix+name]
    else:
        raise Exception("Can't find "+prefix+name+" in "+repr(sys.modules))

def getDownloaderClass(id):

    downloaderMatch = [x for x in sickbeard.downloaderList+sickbeard.newznabDownloaderList if x.getID() == id]

    if len(downloaderMatch) != 1:
        return None
    else:
        return downloaderMatch[0]
