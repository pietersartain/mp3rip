#!/usr/bin/python

# ~~~~~~~~~~~~ Imports ~~~~~~~~~~~~~~~

import sys,os
import CDDB, DiscID
import string
import urllib
import re
import pprint
from pylast import pylast # http://code.google.com/p/pylast/
import json
import codecs
from optparse import OptionParser
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error

# Sort out any encoding issues. Since we're saving
reload(sys)
sys.setdefaultencoding('utf-8')

# ~~~~~~~~~~~~ Functions ~~~~~~~~~~~~~~~

def sanitize_filename(f):
  # < (less than)
  # > (greater than)
  # : (colon)
  # " (double quote)
  # / (forward slash)
  # \ (backslash)
  # | (vertical bar or pipe)
  # ? (question mark)
  # * (asterisk)
  return re.sub('[><:"\/\\|\?\*]', '_', f)

def repl_func(m):
  return m.group(1) + m.group(2).upper()

def capcase(s):
  return re.sub("(^|\s)(\S)", repl_func, s)

def debug(cmd, DEBUG):
  if (DEBUG):
    print cmd
  else:
    os.system(cmd)

def lastfm_auth():
  try:
    json_file=open('config.json')
    config = json.load(json_file)
    json_file.close()
  except IOError:
    print "No config.json file available, unable to fetch album artwork."
    raise

  password_hash = pylast.md5(config['pylast_password'])
  return pylast.LastFMNetwork(api_key = config['pylast_apikey'],
                              api_secret = config['pylast_apisecret'],
                              username = config['pylast_username'], 
                              password_hash = password_hash)

def multiple_matches(s, query_info):
  print s
  num_matches = len(query_info)
  for i in range(0,num_matches):
    print '['+str(i)+'] '+str(query_info[i])
  print "Please run "+sys.argv[0]+" again, passing -d [index] to use."

def CDDB_info(CDINFO, DISCID):
  # Get some information
  cdrom = DiscID.open(CDINFO,)
  disc_id = DiscID.disc_id(cdrom)

  # Query CDDB
  print "Querying CDDB ... "
  (query_status, query_info) = CDDB.query(disc_id)

  info = False

  # Check for status messages
  if (query_status == 200):
  # 200: success
    print " success."
    info = True

  elif (query_status == 210):
  # 210: Multiple exact matches
    if (DISCID is not None):
      query_info = query_info[DISCID]
      info = True
    else:
      multiple_matches("Multiple exact matches found:", query_info)

  elif (query_status == 211):
  # 211: Multiple inexact matches
    if (DISCID > -1):
      query_info = query_info[DISCID]
      info = True
    else:
      multiple_matches("Multiple inexact matches found:", query_info)

  elif (query_status == 202):
  # 202: No match found
    print " failed. No match found."

  else:
  # Something else went horribly wrong
    print " failed with status "+str(query_status)+":\n"
  
  print "Using: "
  print query_info

  return (info, query_info, disc_id)

# ~~~~~~~~~~~~ Defines ~~~~~~~~~~~~~~~

CDPARANOIA='cdparanoia'
CDINFO='/dev/sr0'
OUTDIR='/tmp'
DEBUG = True

PARANOIA = CDPARANOIA + ' -w -d ' + CDINFO + ' -B'

PP = pprint.PrettyPrinter(indent=2)

# ~~~~~~~~~~~~ Option Parser ~~~~~~~~~~~~~~~

parser = OptionParser()
# Defaults: action="store", type="string", 
parser.add_option("-d", "--disc", type="int", dest="DISCID", help="Multiple disc matches, select the match. 0-index'd.")
parser.add_option("-f", "--file", dest="DISCINFO", help="The disc info file.")
parser.add_option("--file-help", action="store_true", help="Details of the file formatting for the disc info file.")
parser.add_option("-a", "--artwork", dest="ARTFILE", help="The cover art URL")
parser.add_option("--no-art", action="store_true", dest="NOART", help="Continue if no artwork is found.")
#parser.add_option("--no-debug", action="store_false", dest="DEBUG", help="Print the os.system calls instead of executing them. Useful for debugging.")
parser.add_option("-r", "--rip", action="store_false", dest="DEBUG", default=True, help="Rip! ")
parser.add_option("--no-various", action="store_true", dest="NOVARIOUS", default=False, help="Do not split tracks ala various artists.")
#parser.add_option("") # CDINFO - what cd tray to use.
# Reading up on the recommended encoder settings, -V 2 should be pretty transparent.
# http://wiki.hydrogenaudio.org/index.php?title=Lame#Recommended_encoder_settings
parser.add_option("-l", "--lameopts", type="string", dest="LAME_OPTS", default="-b vbr -V 2", help="Options passed to lame, for encoding. Defaults to -b vbr -V 2.")
(options, args) = parser.parse_args()

# ~~~~~~~~~~~~ Main ~~~~~~~~~~~~~~~

if (options.file_help):
  print "The disc info file must contain: artist, album, track names. One on each line. Simples!"
  sys.exit()

if (options.DISCINFO is not None):
  # We are attempting to use a disc info file to generate the read_info directly

  try:
    track_names = codecs.open(options.DISCINFO, "r", "utf-8").read().splitlines()

  except NameError:
    print "I can't find that file! Sure that's the one?"
    sys.exit()

  artist_name = track_names.pop(0)
  album_name  = track_names.pop(0)
  tracks = len(track_names)

  info = True
else:
  # Otherwise, we're going to get the read_info from CDDB
  (info, query_info, disc_id) = CDDB_info(CDINFO,options.DISCID)
  if (info):
    (read_status, read_info) = CDDB.read(query_info['category'], query_info['disc_id'])
    album_info = string.split( read_info['DTITLE'],' / ',1)
    
    artist_name = capcase(album_info[0])
    if (len(album_info) <= 1):
      album_name = capcase(album_info[0])
    else:
      album_name = capcase(album_info[1])
      # If the "/" is absent, it is implied that the 
      # artist and disc title are the same, although in this case the name 
      # should rather be specified twice, separated by the delimiter.
    tracks = disc_id[1]
    track_names = []
    if (options.DEBUG):
      print "CDDB read (status: %s)" % read_status
      print "Number of tracks: %d" % tracks

    for i in range(tracks):
      # In the case of a "Various Artists" CDDB entry, people often do things
      # like:
      #
      # An Artist, An Other Aritist / The Special Track Name
      #
      # This is interesting, because it's all bundled up into the track name
      # so we have to manually split it up.
      # Unfortunately this also means it could be split by anything, not
      # necessarily just a / . For example, the title could be listed like:
      #
      # The Special Track Name - An Artist, An Other Artist
      # 
      # TBH this whole "Various Artists" malarky needs a better check, and
      # then a means of passing in the split character and then ordering the
      # parts. Ugh.
      # For now, though, let's just enable the ability to skip the goddamn
      # thing and just move on with our lives.
      if (options.NOVARIOUS):
        track_names.append(read_info['TTITLE' + `i`])
      else:
        track_info = string.split( read_info['TTITLE' + `i`],' / ',1)

        if (len(track_info) > 1):
          track_names.append(track_info[1]+' - '+track_info[0])
        else:
          track_names.append(read_info['TTITLE' + `i`])

        if (options.DEBUG):
          print "Track info size %d" % len(track_info)
          #print unicode(read_info['TTITLE' + `i`], 'shift_jis')
          #print ":".join("{0:x}".format(ord(c)) for c in read_info['TTITLE' + `i`])

      if (options.DEBUG):
        print `i`+"/"+`tracks`+" "+track_names[i]


# Once we have some info to work with ...
if (info):

  print "Artist: %s" % artist_name
  print "Album:  %s" % album_name

  # Set up some more variables
  ROOTDIR = OUTDIR + '/' + sanitize_filename(artist_name) + '/' + sanitize_filename(album_name)

  # If we get this far, we really should ensure all the directories exist.
  if (os.path.isdir(ROOTDIR)):
    debug("mv '"+ROOTDIR+"' '"+ROOTDIR+"_OLD'", options.DEBUG)
  debug("mkdir -p '"+ROOTDIR+"'", options.DEBUG)

  # Let's deal with the artwork
  if (options.ARTFILE is not None):
    # Shoe-horn a cover art file into the situation.
    art_href = options.ARTFILE
  else:
    # Try and find some artwork from last.fm
    try:
      network = lastfm_auth()
      art_href = network.get_album(artist_name,album_name).get_cover_image(pylast.COVER_EXTRA_LARGE)
    except pylast.WSError:
      print "WSError when looking for artwork! Bailing out now."
      sys.exit()
      
  if (art_href is not None):
    print "Found artwork at:\n %s" % art_href
    ext = art_href.split('.').pop()

    if (ext == "png" or ext == "jpg"):
      art_file = ROOTDIR+'/cover.'+ext
      if (ext == "jpg"):
        mime = "image/jpeg" 
      else:
        mime = "image/png"
    else:
      print "Artwork specified not a sensible image file (.jpg, .png), please try again!"
      sys.exit()

    if (options.DEBUG):
      print "Would be scraping from:\n"+art_href+"\nTo:\n"+art_file
    else:
      urllib.urlretrieve(art_href, art_file)
    
    cover = True
  else:
    print "No artwork to be found."
    # Should we bail out at this point and force the use of the -a option?
    if (options.NOART):
      cover = False
    else:
      print "To continue regardless, rerun this script with --no-art"
      sys.exit()

  # Now let's do some real work ...
  print "Now ripping %.02d tracks" % (tracks)
  debug("cd /tmp && " + PARANOIA, options.DEBUG)

  if (options.DEBUG):
    os.system(CDPARANOIA + ' -d ' + CDINFO + ' -Q')

  # For each file, 
  for i in range(tracks):
    j = i+1
    tid = '%.02d' % j

    print "Now converting track %.02d: %s" % (j, track_names[i])

    FNAME = "/tmp/track"+tid+".cdda.wav"

    TNAME = ROOTDIR+'/'+tid+' - ' + sanitize_filename(track_names[i]) + '.mp3'
    LAME_DO = "lame -h --tt '"+track_names[i]+"' --ta '"+artist_name+"' --tn "+tid+" --tl '"+album_name+"' "+options.LAME_OPTS+" '"+FNAME+"' '"+TNAME+"'"
    debug(LAME_DO, options.DEBUG)

    # Copy the artwork into the file
    if (cover and not options.DEBUG):
      audio = MP3(TNAME, ID3=ID3)
      # add ID3 tag if it doesn't exist
      try:
        audio.add_tags()
      except error:
        pass

      audio.tags.add(
        APIC(
          encoding=3, # 3 is for utf-8
          mime=mime, # image/jpeg or image/png
          type=3, # 3 is for the cover image
          desc=u'Cover',
          data=open(art_file).read()
        )
      )
      audio.save()

# ~~~~~~~~~~~~ Tidy up ~~~~~~~~~~~~~~~
  debug( 'rm /tmp/*.wav' , options.DEBUG)
