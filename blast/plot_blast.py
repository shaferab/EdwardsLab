'''
Plot blast hits against a genome
'''
import argparse

import matplotlib.pyplot as plt
import os
import sys


def read_blast_file(blastf, evalue=10, query=False, verbose=False, contiglist=[]):
    '''
    Read the blast file and return an array with the number of times each base has been seen.

    We assume that the blast output file is in standard tab delimited output (ie. -outfmt 6 'std').

    :param blastf: blast file name
    :type blastf: str
    :param evalue: The E value cutoff for the hits
    :type evalue: float
    :param query: Whether the genome is the query (default is that the genome is the database)
    :type query: bool
    :param verbose: Print additional stuff
    :type verbose: bool
    :return: A hash of the contig names and an array of hits to that contig
    :rtype: dict
    '''

    # marginal speed up!
    wantedcontigs = set(contiglist)

    # first we iterate through the file to figure out the contigs and their maximum sizes
    contig_size = {}
    with open(blastf, 'r') as f:
        for l in f:
            p=l.strip().split("\t")
            if query:
                curl = max(int(p[6]), int(p[7]))
                if (wantedcontigs and p[0] in wantedcontigs) or not wantedcontigs:
                    if p[0] not in contig_size or curl > contig_size[p[0]]:
                        contig_size[p[0]] = curl
            else:
                curl = max(int(p[8]), int(p[9]))
                if (wantedcontigs and p[1] in wantedcontigs) or not wantedcontigs:
                    if p[1] not in contig_size or curl > contig_size[p[1]]:
                        contig_size[p[1]] = curl


    # create the empty array
    hits = {}
    for c in contig_size:
        hits[c] = []
        for i in range(contig_size[c]+1):
            hits[c].append(0)

    with open(blastf, 'r') as f:
        for l in f:
            p = l.strip().split("\t")
            if float(p[10]) > evalue:
                continue
            contig=''
            if query:
                contig = p[0]
                startpos = int(p[6])
                endpos = int(p[7])
            else:
                contig = p[1]
                startpos = int(p[8])
                endpos = int(p[9])
            if wantedcontigs and contig not in wantedcontigs:
                continue
            for i in range(startpos, endpos+1):
                hits[contig][i] += 1

    return hits


def hits_to_list(hits, printcontigs=False):
    '''
    Convert the hits from a hash to a single list
    :param printcontigs: Print out the locations and order of the contigs
    :type printcontigs: bool
    :param hits: the hash of hits on contig name
    :type hits: dict
    :return: A list with the hits concatenated by length, longest first and a list of all the breaks in the contigs
    :rtype: list, list
    '''

    allhits = []
    breaks=[0]
    contig_size = {x:len(hits[x]) for x in hits}

    for contigcount, c in enumerate(sorted(contig_size, key=lambda x: contig_size[x], reverse=True)):
        allhits += hits[c]
        breaks.append(breaks[-1] + contig_size[c])
        if printcontigs:
            print(str(contigcount) + ": Contig: " + c + " from " + str(breaks[-2]) + " to " + str(breaks[-1]))

    breaks.pop(0)
    return allhits, breaks


def dropzero(hits):
    '''
    Drop zero values and return two lists. One of the x's, and one of the y's
    :param hits: The list of hits
    :type hits: list
    :return: x and y lists
    :rtype: (list, list)
    '''

    xs = []
    ys = []

    for i,j in enumerate(hits):
        if j > 0:
            xs.append(i)
            ys.append(j)
    return (xs, ys)


def window_merge(hits, window):
    '''
    Join the hits within a specified window
    :param hits: The hash of hits and contig sizes
    :type hits: dict
    :param window: The window size to use
    :type window: int
    :return: The hash of contig and coverage at each position. Many positions will be zero
    :rtype: dict
    '''

    # divide the window by 2 to get everything before and after
    window /=2
    avhits = {}
    for c in hits:
        avhits[c] = []
        for i in range(len(hits[c])):
            avhits[c].append(0)
        i = 0
        while i < len(hits[c])-window:
            mini = i - window
            if mini < 0:
                mini = 0
            maxi = i+window
            if maxi > len(hits[c]):
                maxi = len(hits[c])
            # sys.stderr.write("Window: " + str(window) + " i: " + str(i) +  " maxi : " + str(maxi) + " mini: " + str(mini) + "\n")
            avhits[c][i] = 1.0 * sum(hits[c][mini:maxi]) / (maxi-mini)
            i+=window

    return avhits


def plot_hits(hits, breaks=[], window=0, maxy=0):
    '''
    Plot the hits!
    :param breaks: An optional list of contig breakpoints to be added. If an empty list is provided no lines added
    :type breaks: list
    :param hits: The array of hits (eg. from read_blast_file)
    :type hits: list
    :param window: The window size used to make the plot. If 0, this is not used in the image
    :type window: int
    :param maxy: The maximum y value to plot on the figure. If 0 (default) we use the maximum value of the data
    :type maxy; int
    :return: void
    :rtype: void
    '''

    if maxy == 0:
        maxy = max(hits)
    maxx = len(hits)

    x,y = dropzero(hits)
    # x = range(maxx)
    # y = hits
    cx=[200000, 200000]
    cy=[0, 1000]

    #plt.plot(hits)
    line, = plt.plot(x, y, '-')
    if breaks:
        for b in breaks:
            plt.plot([b,b], [0, maxy], 'r-')
    plt.axis([0, maxx, 0, maxy])
    if window > 0:
        plt.ylabel('Average fold coverage across a ' + str(window) + " bp window")
    else:
        plt.ylabel('Fold coverage')
    plt.xlabel('Cumulative position in the genome (bp)')
    plt.show()


def print_region(hitshash, threshold, merge=1000, minwindow=100):
    '''
    Print out the regions with coverage higher than threshold. Assumes a raw hits hash (not windowized)
    :param hitshash: The hits by contig
    :type hitshash: dict
    :param threshold: Minimum coverage
    :type threshold: int
    :param merge: Merge adjacent regions with x bp
    :type merge: int
    :return: None
    :rtype: None
    '''

    contig_size = {x:len(hitshash[x]) for x in hitshash}

    for contig in sorted(contig_size, key=lambda x: contig_size[x], reverse=True):
        inhit = False
        first = None
        last = None
        for i in range(len(hitshash[contig])):
            if hitshash[contig][i] > threshold:
                if not inhit:
                    inhit = True
                    first = i
                    last = i+1
                else:
                    last = i
            else:
                if inhit and i - last > merge:
                    # no longer in a hit and we don't want to save a potential hit
                    inhit = False
                    if last-first > minwindow:
                        print("\t".join(map(str, [contig, first, last, last-first, 1.0 * sum(hitshash[contig][first:last])/(last-first)])))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Plot genome coverage from blast hits and optionally print out regions with coverage above some value')
    parser.add_argument("-b", help='blast file', required=True)
    parser.add_argument('-c', help='minimum coverage for regions to write', type=float)
    parser.add_argument('-a', help='size to merge adjacent regions in printing over coverage (default=1000)', default=1000, type=int)
    parser.add_argument('-m', help='minimum size of window over threshold to print (default=100)', default=100, type=int)
    parser.add_argument('-w', help='window width to merge for plot (default=5000bp) (only affects plot)', default=5000, type=int)
    parser.add_argument('-y', help='maximum y value to plot (default = all hits)', type=int, default=0)
    parser.add_argument('-n', help='suppress the plot (no plot)', action='store_true')
    parser.add_argument('-k', help='include contig breaks (default=no breaks', action='store_true')
    parser.add_argument('-p', help='print a list of the contigs (in order) as they are added to the image', action='store_true')
    parser.add_argument('-o', help='only use data from this contig (or these, you can use multiple -o)', action='append', default=[])
    args = parser.parse_args()


    # plot_hits(hits_to_list(read_blast_file(blastf)))
    # plot_hits(hits_to_list(window_merge(read_blast_file(blastf), 5000)))

    hitshash = read_blast_file(args.b, contiglist=args.o)
    windowhash = window_merge(hitshash, args.w)

    if args.c:
        print_region(hitshash, threshold=args.c, merge=args.a, minwindow=args.m)

    hitlist, breaklist = hits_to_list(windowhash, args.p)

    if not args.n:
        if args.k:
           plot_hits(hitlist, breaks=breaklist, window=args.w, maxy=args.y)
        else:
            plot_hits(hitlist, breaks=[], window=args.w, maxy=args.y)

