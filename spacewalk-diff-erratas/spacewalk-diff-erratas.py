#!/usr/bin/python
# Script that creates a new channel and merges data 
#
# Author: Martin Zehetmayer <angrox@idle.at>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# ---------------
#
# This script checks if there is a newer version of a package for specific 
# systems available.
#
#
#  usage: spacewalk-diff-erratas.py [options]
#
#  options:
#    -h, --help            show this help message and exit
#    -f CFG_FILE, --config-file=CFG_FILE
#                          Config file for servers, users, passwords
#    -p PACKAGE, --package=PACKAGE
#                          Package name, ex: bash
#    -s SYSTEM, --system=SYSTEM
#                          Name of the System or "all" for all systems. Regex can
#                          be used to specify more than one server, ex.
#                          webserver*
#    -c CHANNEL, --channel=CHANNEL
#                          [OPTIONAL] The channel to check against. By default
#                          systems channels (base and child) are checked. If you
#                          use this option only THIS channel is checked. No child
#                          channels will be checked!
#    -r RELEASE, --release=RELEASE
#                          [OPTIONAL] Check only a specific release. Values are:
#                          5, 6
#  
#
# The configuration file must be parseable bei ConfigParser:
# Example: 
#
# [Spacewalk]
# spw_server = spacewalk.example.com
# spw_user   = api_user_1
# spw_pass   = api_password_1


import xmlrpclib
import ConfigParser
import optparse
import sys
import os
import re

from optparse import OptionParser
from distutils.version import LooseVersion



def parse_args():
    parser = OptionParser()
    parser.add_option("-f", "--config-file", type="string", dest="cfg_file",
            help="Config file for servers, users, passwords")
    parser.add_option("-p", "--package", type="string", dest="package",
            help="Package name, ex: bash")
    parser.add_option("-s", "--system", type="string", dest="system",
            help="Name of the System or \"all\" for all systems. Regex can be "
            "used to specify more than one server, ex. webserver*")
    parser.add_option("-c", "--channel", type="string", dest="channel",
            help="[OPTIONAL] The channel to check against. By default systems channels "
            "(base and child) are checked. If you use this option only THIS channel "
            "is checked. No child channels will be checked!")
    parser.add_option("-r", "--release", type="string", dest="release",
            help="[OPTIONAL] Check only a specific release. Values are: 5, 6")
    parser.add_option("-e", "--errata", type="string", dest="errata",
            help="[OPTIONAL] Lists erratas missing in the system")

    (options,args) = parser.parse_args()
    return options



def check_package(spacewalk, spacekey, entry, packagename):
    for package in spacewalk.system.listPackages(spacekey, entry["id"]):
        if package["name"] == packagename:
            found_entry=package
            break
    try: 
        latest=spacewalk.system.listLatestAvailablePackage(spacekey, entry["id"], packagename)[0]["package"]
    except: 
        print ". No package information for package %s on system %s found." % (packagename, entry["name"])
        return
    checked=spacewalk.system.listOlderInstalledPackages(spacekey, entry["id"], latest["name"],latest["version"], latest["release"], latest["epoch"])
    laversionstring="%s-%s" % (latest["version"], latest["release"])
    if not checked:
        print "- Package %s on system %s is up to date (%s-%s)" % (latest["name"], entry["name"], latest["version"], latest["release"] )
    else:
        print "- Package %s on system %s is OLDER (%s-%s vs %s-%s)" % (latest["name"], entry["name"], found_entry["version"], found_entry["release"], latest["version"], latest["release"])
       


def check_channel_package(spacewalk, spacekey, entry, packagename, channelentry):
    for package in spacewalk.system.listPackages(spacekey, entry["id"]):
        if package["name"] == packagename:
            found_entry=package
            break
    m=re.search("(.*)\.el\d", "%s-%s" % (found_entry["version"], found_entry["release"]))
    if m is not None:
        sysversion=m.group(1)
    else:
        print "- Could not check version on system %s." % entry["name"]
    if LooseVersion(sysversion) < LooseVersion(channelentry):
        print "- Package %s on system %s is OLDER (%s vs %s)" % (packagename, entry["name"], sysversion, channelentry)
    else:
        print "- Package %s on system %s is up to date (%s)" % (packagename, entry["name"], sysversion)



def get_errata(spacewalk, spacekey, server, channel):
    print channel
    serverchannel_lastmod=spacewalk.system.getSubscribedBaseChannel(spacekey, server["id"])["last_modified"]
    missing_errata=[]
    # Missing errata of own channel
    for errata in spacewalk.system.getRelevantErrata(spacekey, server["id"]):
       if errata["id"] not in missing_errata:
            missing_errata.append(errata["id"])
    # Missing errata of other channel 
    if channelentry is not None:
        for errata in spacewalk.channel.software.listErrata(spacekey, channel["id"], serverchannel_lastmod):
           if errata["id"] not in missing_errata:
                missing_errata.append(errata["id"])
    print missing_errata
    sys.exit(1)
      
        
    


        

def main():         
    # Get the options
    options = parse_args()
    # read the config
    if options.cfg_file: 
        config = ConfigParser.ConfigParser()
        try:
            config.read (options.cfg_file) 
        except:
            print "Could not read config file %s.  Try -h for help" % options.cfg_file
            sys.exit(1)
        try: 
            spw_server = config.get ('Spacewalk', 'spw_server')
            spw_user = config.get ('Spacewalk', 'spw_user')
            spw_pass = config.get ('Spacewalk', 'spw_pass')
        except: 
            print "The file %s seems not to be a valid config file." % options.cfg_file
            sys.exit(1)
    else:
        print "Options -f (Configfile) not given! Try -h for help"
        sys.exit(1)

    if options.system is None or options.package is None:
        print "Missing package or system name.  Try -h for help"
        sys.exit(1)

    spacewalk = xmlrpclib.Server("https://%s/rpc/api" % spw_server, verbose=0)
    spacekey = spacewalk.auth.login(spw_user,spw_pass)

    package=spacewalk.packages.search.name(spacekey, options.package)
    if not package:
        print "Package %s could not be found." % options.package
        spacewalk.auth.logout(spacekey)
        sys.exit(1)

    if options.channel is not None:
        try: 
            channelpackages=spacewalk.channel.software.listLatestPackages(spacekey, options.channel)
        except:
            print "Channel %s not found." % options.channel
            spacewalk.auth.logout(spacekey)
            sys.exit(1)
        for chpkg in channelpackages:
            if chpkg["name"] == options.package:
                print "Package found in channel"
                m=re.search("(.*)\.el\d", "%s-%s" % (chpkg["version"], chpkg["release"]))
                if m is not None:
                    channelentry=m.group(1)
                    break
        
  
    if options.system == "all":
        entries=spacewalk.system.listSystems(spacekey)
    else:
        entries=spacewalk.system.searchByName(spacekey, options.system)
    if entries:
        for entry in entries:
            #print entry["id"]
            if options.errata is not None:
                get_errata(spacewalk, spacekey, entry, options.channel)    

            release=spacewalk.system.getDetails(spacekey, entry["id"])["release"]
            if options.release:
                if release != "%sServer" % options.release:
                    print ". Release mismatch for system %s" % entry["name"]
                    continue
            if options.channel is not None:
                check_channel_package(spacewalk, spacekey, entry, options.package, channelentry)
            else: 
                check_package(spacewalk, spacekey, entry, options.package)
    else:
        print "No system(s) found" % options.system
        spacewalk.auth.logout(spacekey)
        sys.exit(1)
    spacewalk.auth.logout(spacekey)


## MAIN
if __name__ == "__main__":
    main()  

