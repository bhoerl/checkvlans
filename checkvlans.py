#!/usr/bin/env python

import sys
import smtplib
import string
import re

from optparse import OptionParser


def sendmail(header, output, switchnames):

    message = header + output

    BODY = string.join((
            "From: nagios@mydomain.com",
            "To: noc@mydomain.com",
            "Subject: Check " + switchnames + " VLANs" ,
            "",
            message
            ), "\r\n")
    server = smtplib.SMTP("MY-SMTP-SERVER")
    server.sendmail("nagios@mydomain.com", ["noc@mydomain.com"], BODY)
    server.quit()


def expandedvlans(s):

    r = []
    for i in s.split(','):
        if '-' not in i:
            r.append(int(i))
        else:
            l,h = map(int, i.split('-'))
            r+= range(l,h+1)
    return r


def openconfigbackup(switch):
    # read switch configuration as list
    configbackuppath = "/var/Konfigurationsbackup/"

    with open(configbackuppath + switch + "/current.cfg") as f:
        lines = list(f)
    return lines


def generateifindex(switchconfig, description):

    interface_indexes = []

    for line in switchconfig:
        if line.startswith("interface port-channel"):
            # save found list index to variable
            port_channel_index = switchconfig.index(line)
            description_index = port_channel_index +1
            # if 'CLUSTER-VLAN-SUMMARY' is found add to interface_indexes
            if description in switchconfig[description_index]:
                interface_indexes.append(port_channel_index)
    return interface_indexes


def generatevlandb(switchconfig):

    vlandb = []

    for line in switchconfig:
        # match beginning of line + "vlan" + space + number
        if re.search("^vlan\s[0-9]", line):
            for i in expandedvlans(line.strip("vlan ").strip()):
                vlandb.append(i)
    return vlandb


def generateoutput(reference_output, output, switchnames, description):

    if output:
        print "Error in " + switchnames + " VLAN configuration"
        header = "Error in " + switchnames + " VLAN configuration:\n" + reference_output + "\n"
        sendmail(header, output, switchnames)
        sys.exit(2)
    else:
        print "VLAN configuration " + switchnames + " " +  description + " OK"
        header = "VLAN configuration " + switchnames + " " +  description + " OK.\n"
        sendmail(header, output, switchnames)
        sys.exit(0)


def getreferencevlans(switchconfig, switch, firstinterfaceindex):

    for line in switchconfig[firstinterfaceindex:]:
        if "switchport trunk allowed vlan" in line:
            referencevlans = expandedvlans(line.strip("  switchport trunk allowed vlan "))
            break

    interface_output = switchconfig[firstinterfaceindex].strip()
    description_output = switchconfig[firstinterfaceindex + 1].strip()

    reference_output = "Switch: " + switch + "\n"
    reference_output += "Interface: " + interface_output + "\n"
    reference_output += "Description: " + description_output + "\n"
    reference_output += "Reference: " + str(referencevlans).strip("[]") + "\n"
    reference_output += "\n"

    return referencevlans, reference_output


def checkvlans(switchconfig, switch, interface_indexes, vlandb, referencevlans):

    error = False
    error_output = ""
    vlandb_error_output = ""

    # read until no item in list
    while interface_indexes:
        # start looping from the beginning of the first index
        for line in switchconfig[interface_indexes[0]:]:
            # if switchport trunk allowed vlan is found for the first time, generate ouput,
            # then break loop to beginn with next index
            if "switchport trunk allowed vlan" in line:
                vlans = expandedvlans(line.strip("  switchport trunk allowed vlan "))
                interface_output = switchconfig[interface_indexes[0]].strip()
                description_output = switchconfig[interface_indexes[0] + 1].strip()
                # check vlan database
                for vlanid in vlans:
                    if not vlanid in vlandb:
                        error = True
                        vlandb_error_output += "Swtich: " + switch + "\n"
                        vlandb_error_output += "Interface: " + interface_output + "\n"
                        vlandb_error_output += "VLAN not in VLAN-Database: " + str(vlanid) + "\n"
                        vlandb_error_output += "\n"
                # compare the lists
                x = list(set(vlans).difference(set(referencevlans)))
                y = list(set(referencevlans).difference(set(vlans)))
                # move on if no error on compare
                if not x and not y:
                    del interface_indexes[0]
                    break
                else:
                    error = True
                    error_output += "Swtich: " + switch + "\n"
                    error_output += "Interface: " + interface_output + "\n"
                    error_output += "Description: " + description_output + "\n"
                    # add a dot to the end of line so outlook knowns there should come a new line
                    error_output += "VLANs: " + str(vlans).strip("[]") + ".\n"
                    if x: error_output += "Change from reference-port (+): " + str(x).strip("[]") + ".\n"
                    if y: error_output += "Change from reference-port (-): " + str(y).strip("[]") + ".\n"
                    error_output += "\n"
                    del interface_indexes[0]
                    break

    if error is True:
        return vlandb_error_output + error_output
    else:
        # return empty string for sendmail instead of None
        return ""


def main ():

    help_message = "\n check vlan configuration\n" \
                    "\n 'checkvlans.py --help' for more information\n"
    usage = "\n %prog -d <description> -s <switches>"

    parser = OptionParser(usage=usage)

    parser.add_option("-d",
                  dest="description",
                  help="description to search")
    parser.add_option("-s",
                  dest="switches",
                  help="single switch or comma sperated list of switches to check")

    (options, args) = parser.parse_args()

    if not options.description or not options.switches:
        print help_message
        sys.exit(3)
    else:
        output = ""
        createreferencevlans = False
        switches = options.switches.split(",")
        switchnames = options.switches.replace(",", "/")
        description = options.description
        for switch in switches:
            switchconfig = openconfigbackup(switch)
            interface_indexes = generateifindex(switchconfig, description)
            vlandb = generatevlandb(switchconfig)
            # only create reference vlans for first switch in loop
            if not createreferencevlans:
                referencevlans, reference_output = getreferencevlans(switchconfig, switch, interface_indexes[0])
                # interface for reference vlans should not be checked further so its removed from list
                del interface_indexes[0]
                createreferencevlans = True
            output += checkvlans(switchconfig, switch, interface_indexes, vlandb, referencevlans)
        generateoutput(reference_output, output, switchnames, description)

if __name__ == '__main__':
    main()
