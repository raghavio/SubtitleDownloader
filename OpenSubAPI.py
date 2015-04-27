################################################################################
# Author: Raghav Sharma                                                        #
# E-mail: Raghav_FTW@hotmail.com                                               #
#                                                                              #
# License: GNU General Public License v2.0                                     #
#                                                                              #
# A subtitle downloader using the www.opensubtitles.org API                    #
# Look http://trac.opensubtitles.org/projects/opensubtitles for more details.  #
#                                                                              #
# Copyright (C) 2015 Raghav Sharma                                             #
#                                                                              #
# This program is free software; you can redistribute it and/or modify         #
# it under the terms of the GNU General Public License as published by         #
# the Free Software Foundation; either version 2 of the License, or            #
# (at your option) any later version.                                          #
#                                                                              #
# This program is distributed in the hope that it will be useful,              #
# but WITHOUT ANY WARRANTY; without even the implied warranty of               #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                #
# GNU General Public License for more details                                  #
################################################################################

from os import path

import os
import sys
import struct
import collections

import xmlrpclib
import gzip
import base64

server_url = "http://api.opensubtitles.org/xml-rpc";
user_agent = "OSTestUserAgent" # Test user agent, you should request a new one.

class OpenSubtitlesAPI:

    server = None

    def createSubFile(self, gzipSub, subFilePath):
        with open(subFilePath, 'wb') as subFile:
            subFile.write(gzipSub)

        with gzip.open(subFilePath, 'rb') as subFileGzip:
            decodedSub = subFileGzip.read()

        with open(subFilePath, 'wb') as subFile:
            subFile.write(decodedSub)

    def decodeSub(self, encodedSub):
        decoded_sub = base64.b64decode(encodedSub)
        return decoded_sub

    def downloadEncodedSub(self, token, subId):
        try:
            result = self.server.DownloadSubtitles(token, [subId])
            if result['status'] != "200 OK":
                print ("Server returned: '" + result['status'] + "' while \
                        downloading sub")
                return None

            data = result['data']
            if data == False:
                print ("Couldn't find subtitle for this file.")
                return None

            encodedSub = data[0]['data']
            return encodedSub
        except Exception as e:
            print ('An error occured while downloading sub: %s') % e
            sys.exit(1)

    # This is our custom rating algorithm, to find the best suitable sub
    # in a list of dictionaries. It inserts our calulated rating value in
    # the dictionary and returns the list.
    def ratingAlgorithm(self, data):
        for i in data:
            i['ratingAlgo'] = 0
            if int(i['SubBad']) > 0:
                i['ratingAlgo'] -= 5
            rating = float(i['SubRating'])
            if rating < 4.0 and rating > 0.0:
                i['ratingAlgo'] -= 5
            else:
                i['ratingAlgo'] += round(rating)
            if i['UserRank'] == "administrator" or i['UserRank'] == "trusted":
                i['ratingAlgo'] += 1
        return data

    # OpenSubtitles DB is fucked up, it returns multiple results and
    # sometimes of different movies/series. So we have to do a lot of
    # shit to find the best sub.
    def searchSub(self, token, data):
        try:
            result = self.server.SearchSubtitles(token, data)

            if result['status'] != "200 OK":
                print ("Server returned: '" + result['status'] + "' while \
                        searching for sub")
                return None

            data = result['data']

            if data == False:
                print ("Couldn't find subtitle for this file.")
                return None

            # Gets the two most common movie from result by matching
            # their imdb ids.
            # (Like I said, sometimes there can be different movies
            # in result, so we use the most common movie one (by
            # checking their IMDB ids) and use that. We get the 2nd
            # most common to check if the count of 1 & 2 are not equal,
            # in that case we use the original result.
            c = collections.Counter(i['IDMovieImdb'] for i in data)
            mostCommon = c.most_common(2)
            movieCount = len(mostCommon)

            # We choose the most common movie if the count of
            # 1st & 2nd are different. [0][0] is IMDb id and
            # [0][1] is count of those IMDb ids in result
            isMostCommon = (movieCount == 1 or
                            (movieCount > 1 and
                            mostCommon[0][1] != mostCommon[1][1]))
            if isMostCommon:
                data = [i for i in data if i['IDMovieImdb'] == mostCommon[0][0]]

            data = self.ratingAlgorithm(data)

            # We sort the data on the basis of our rating algorithm
            # and sub add date(Assuming the latest sub would be better)
            sortedData = sorted(data,
                                key=lambda k: (float(k['ratingAlgo']),
                                                k['SubAddDate']),
                                reverse=True)

            # We get the top most result
            result = sortedData[0]

            # No need to change the sub name to actual movie name if
            # we're not sure the movie is correct or not
            if isMostCommon:
                if result['MovieKind'] == "episode":
                    fileName = "[S%02dE%02d] %s" % (
                                    int(result['SeriesSeason']),
                                    int(result['SeriesEpisode']),
                                    result['MovieName'].replace('" ', ' - ')
                                                        .replace('"', '')
                                                        .replace('/', ':'))
                else:
                    fileName = "[%s] %s" % (result['MovieYear'],
                                            result['MovieName'])
            else:
                fileName = None
            result['customName'] = fileName

            return result
        except Exception as e:
            print ('An error occured while searching sub: %s') % e
            sys.exit(1)

    # This is a special hash function to match a subtitle files against the
    # movie files. Got this Python implementation from their site.
    #
    # http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
    def hashFile(self, name):
        try:
            longlongformat = '<q'  # little-endian long long
            bytesize = struct.calcsize(longlongformat)

            f = open(name, "rb")

            filesize = path.getsize(name)
            hash = filesize

            if filesize < 65536 * 2:
                return "SizeError"

            for x in range(65536/bytesize):
                buffer = f.read(bytesize)
                (l_value,)= struct.unpack(longlongformat, buffer)
                hash += l_value
                hash = hash & 0xFFFFFFFFFFFFFFFF #to remain as 64bit number


            f.seek(max(0,filesize-65536),0)
            for x in range(65536/bytesize):
                buffer = f.read(bytesize)
                (l_value,)= struct.unpack(longlongformat, buffer)
                hash += l_value
                hash = hash & 0xFFFFFFFFFFFFFFFF

            f.close()
            returnedhash =  "%016x" % hash
            return str(returnedhash), str(filesize)
        except(IOError):
              return "IOError"

    # This will end the session id.
    # This is totally unnecessary to call, but OCD.
    def logout(self, token):
        try:
            self.server.LogOut(token)
        except Exception as e:
            print ('An error occured while logging out: %s') % e
            sys.exit(1)

    def login(self, lang, username="", password=""):
        try:
            result = self.server.LogIn(username, password,
                                        lang, user_agent)
            return result
        except Exception as e:
            print ('An error occured while logging in: %s') % e
            sys.exit(1)

    def init(self, files, lang):
        self.server = xmlrpclib.Server(server_url);

        loginData = self.login(lang)
        if loginData['status'] != "200 OK":
            print ("Server returned: '" + loginData['status'] +"' while \
                    logging in")
            return
        token = loginData['token']
        for i, file in enumerate(files):
            _hash, fileSize = self.hashFile(file)
            if _hash == "SizeError" or _hash == "IOError":
                print ("Uh-oh, a " + _hash + " occured. Make sure your file\
                        is greater than 132kb")
                continue

            searchData = [{'moviehash' : _hash, 'moviebytesize' : fileSize,
                            'sublanguageid' : lang}]
            result = self.searchSub(token, searchData)

            if result is None:
                files.pop(i)
                continue
            subId = result['IDSubtitleFile']
            encodedSub = self.downloadEncodedSub(token, subId)

            if encodedSub is None: #This would never happen but meh...
                files.pop(i)
                continue

            gzipSub = self.decodeSub(encodedSub)

            root, fileName = path.split(file)
            # If we want to rename the video file name with data from
            # database we set the 'customName' to our new name.
            # If we're not sure about the accuracy of result returnd, we
            # don't. So 'customName' is None. see searchSub() for more info
            renameFile = result['customName'] is not None
            if renameFile:
                fileExt = path.splitext(fileName)[1]
                fileName = result['customName']
                newMovieFile = path.join(root,
                                         fileName + fileExt)
                os.rename(file, newMovieFile)

            # Gets the sub file path
            subFile = path.join(root,
                                fileName + "." + result['SubFormat'])
            self.createSubFile(gzipSub, subFile)
            print ("Downloaded subtitle for %s") % (fileName)
        self.logout(token)

videoExts =".avi.mp4.mkv.mpeg.flv.3gp2.3gp.3gp2.3gpp.60d.ajp.asf.asx.avchd.bik\
            .mpe.bix.box.cam.dat.divx.dmf.dv.dvr-ms.evo.flc.fli.flic.flx.gvi\
            .gvp.h264.m1v.m2p.m2ts.m2v.m4e.m4v.mjp.mjpeg.mjpg.mpg.moov.mov\
            .movhd.movie.movx.wx.mpv.mpv2.mxf.nsv.nut.ogg.ogm.omf.ps.qt.ram\
            .rm.rmvb.swf.ts.vfw.vid.video.viv.vivo.vob.vro.wm.wmv.wmx.wrap\
            .wvx.x264.xvid"

def main():
    if len(sys.argv) == 1:
        print ("Specify the path to the directory or file.")
        sys.exit(1)

    downloadPath = sys.argv[1]

    downloadFiles = []
    if path.isfile(downloadPath):
        downloadFiles.append(downloadPath)
    else: #if directory
        for root, dirs, files in os.walk(downloadPath):
            for fileName in files:
                ext = path.splitext(fileName)[1]
                if ext != "": # Getting .DS_Store unless
                    if ext in videoExts:
                        file = path.join(root, fileName)
                        downloadFiles.append(file)

    o = OpenSubtitlesAPI()
    #Use http://en.wikipedia.org/wiki/List_of_ISO_639-2_codes for languages
    o.init(downloadFiles, 'eng')

if __name__ == '__main__':
    main()
