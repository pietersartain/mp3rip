# mp3rip
This is the latest (and likely final) incarnation of a means to consistently rip CDs to mp3. It's rarely used now (unsurprisingly) but was an excellent learning tool, integrating some interesting last.fm accesses.

Originally a shell script, this evolved into Python because I wanted to embed album art during the ripping process, and mutagen was one of the few ID3 libraries that dealt with album art.

It has given me a great deal of joy over the past few years every time I come to use it or to tinker with it, however that also means it's probably not generic enough for general use and any number of other people have assembled ripping programs that are probably better, more functional and less specific to my environment.

## Installation

Unpack the repo somewhere sensible, and then install some dependancies. Under something like Debian Jessie you'll want to:

    $ apt-get install python-cddb python-mutagen cdparanoia

These things are _not_ checked at run time, so the program will barf with an horrendous Python stack trace and a complaint.

## Usage

The help can be accessed via:

    $ ./rip3.py -h

At some point I may write more about what the options do.

## Todo

 * Add input device, output device and ripping program to the command line parameters.
 * Add some more documentation to usage.

## Copyright & licensing
Copyright 2012-2016 Pieter Sartain, and released under the MIT license. See license.txt for details.

[pylast](http://code.google.com/p/pylast/) is included here as a git submodule, made available under the Apache v2 license.