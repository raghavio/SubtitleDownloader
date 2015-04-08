from os import path

import os
import sys
import struct
import xmlrpclib

server_url = 'http://api.opensubtitles.org/xml-rpc';
user_agent = 'OSTestUserAgent'

class OpenSubtitlesAPI:

    server = None

    def searchSub(self, token, data):
        result = self.server.SearchSubtitles(token, data)
        if result['status'] == "200 OK":
            for i in result['data']:#SubBad
                print "S%sE%s - %s" % (i['SeriesSeason'], i['SeriesEpisode'], i['MovieName'])
                print ""
                print ""
            return result

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
            return returnedhash
        except(IOError):
              return "IOError"

    def login(self, lang, username="", password=""):
        try:
            result = self.server.LogIn(username, password, lang, user_agent)
            return result
        except Exception, e:
            print 'An error occured while logging in: %s' % e
            sys.exit(1)

    def init(self, files, lang):
        self.server = xmlrpclib.Server(server_url);
        loginData = self.login(lang)

        if loginData['status'] == "200 OK":
            token = loginData['token']
            searchData = []
            for file in files:
                _hash = self.hashFile(file)
                fileSize = path.getsize(file)

                videoFile = {'moviehash' : _hash, 'moviebytesize' : fileSize, 'sublanguageid' : lang}
                searchData.append(videoFile)

            self.searchSub(token, searchData)

videoExts =".avi.mp4.mkv.mpeg.3gp2.3gp.3gp2.3gpp.60d.ajp.asf.asx.avchd.bik.mpe.bix\
            .box.cam.dat.divx.dmf.dv.dvr-ms.evo.flc.fli.flic.flv.flx.gvi.gvp.h264.m1v.m2p\
            .m2ts.m2v.m4e.m4v.mjp.mjpeg.mjpg.mpg.moov.mov.movhd.movie.movx.wx.mpv\
            .mpv2.mxf.nsv.nut.ogg.ogm.omf.ps.qt.ram.rm.rmvb.swf.ts.vfw.vid.video.viv\
            .vivo.vob.vro.wm.wmv.wmx.wrap.wvx.x264.xvid"

def main():
    if len(sys.argv) == 1:
        print("Specify the path to the directory or file.")
        sys.exit(1)

    directory = sys.argv[1]

    files = []
    for file in os.listdir(directory):
        if path.isfile(path.join(directory, file)):
            ext = path.splitext(file)[1]
            if ext == "": #Getting .DS_STORE
                continue
            if ext in videoExts:
                files.append(path.join(directory,file))
    o = OpenSubtitlesAPI()
    o.init(files, 'eng')

if __name__ == '__main__':
    main()
