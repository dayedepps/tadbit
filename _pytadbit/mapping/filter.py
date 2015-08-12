"""
17 nov. 2014


"""
from pytadbit.mapping.restriction_enzymes import count_re_fragments
import multiprocessing as mu
from subprocess import Popen, PIPE

def apply_filter(fnam, outfile, masked, filters=None, reverse=False, old=False,
                 verbose=True):
    """
    Create a new file with reads filtered

    :param fnam: input file path, where non-filtered read are stored
    :param outfile: output file path, where filtered read will be stored
    :param masked: dictionary given by the
       :func:`pytadbit.mapping.filter.filter_reads`
    :param None filters: list of numbers corresponding to the filters we want
       to apply (numbers correspond to the keys in the masked dictionary)
    :param False reverse: if set, the resulting outfile will only contain the
       reads filtered, not the valid pairs.
    :param False verbose:
    """
    masked_reads = set()
    filters = filters or masked.keys()
    if old:
        for filt in filters:
            masked_reads.update(masked[filt]['reads'])
    else:
        for k in masked:
            if k in filters:
                masked_reads.update(open(masked[k]['fnam']).read().split())
    out = open(outfile, 'w')
    fhandler = open(fnam)
    while True:
        line = next(fhandler)
        if not line.startswith('#'):
            break
        out.write(line)
    if reverse:
        cond = lambda x, y: x in y
    else:
        cond = lambda x, y: x not in y
    count = 0
    try:
        while True:
            read = line.split('\t', 1)[0]
            if cond(read, masked_reads):
                count += 1
                out.write(line)
            line = next(fhandler)
    except StopIteration:
        pass
    if verbose:
        print '   %d reads written to file' % count
    out.close()


def filter_reads(fnam, output=None, max_molecule_length=500,
                 over_represented=0.005, max_frag_size=100000,
                 min_frag_size=100, re_proximity=5, verbose=True,
                 savedata=None, min_dist_to_re=750, fast=True):
    """
    Filter mapped pair of reads in order to remove experimental artifacts (e.g.
    dangling-ends, self-circle, PCR artifacts...)
    
    Applied filters are:    
       1- self-circle        : reads are coming from a single RE fragment and
          point to the outside (----<===---===>---)
       2- dangling-end       : reads are coming from a single RE fragment and
          point to the inside (----===>---<===---)
       3- error              : reads are coming from a single RE fragment and
          point in the same direction
       4- extra dangling-end : reads are coming from different RE fragment but
          are close enough (< max_molecule length) and point to the inside
       5- too close from RES : semi-dangling-end filter, start position of one
          of the read is too close (5 bp by default) from RE cutting site. This
          filter is skipped in case read is involved in multi-contact. This
          filter may be too conservative for 4bp cutter REs.
       6- too short          : remove reads coming from small restriction less
          than 100 bp (default) because they are comparable to the read length
       7- too large          : remove reads coming from large restriction
          fragments (default: 100 Kb, P < 10-5 to occur in a randomized genome)
          as they likely represent poorly assembled or repeated regions
       8- over-represented   : reads coming from the top 0.5% most frequently
          detected restriction fragments, they may be prone to PCR artifacts or
          represent fragile regions of the genome or genome assembly errors
       9- duplicated         : the combination of the start positions of the
          reads is repeated -> PCR artifact (only keep one copy)
       10- random breaks     : start position of one of the read is too far (
          more than min_dist_to_re) from RE cutting site. Non-canonical
          enzyme activity or random physical breakage of the chromatin.
    
    :param fnam: path to file containing the pair of reads in tsv format, file
       generated by :func:`pytadbit.mapping.mapper.get_intersection`
    :param None output: PATH where to write files containing IDs of filtered
       reads. Uses fnam by default.
    :param 500 max_molecule_length: facing reads that are within
       max_molecule_length, will be classified as 'extra dangling-ends'
    :param 0.005 over_represented: to remove the very top fragment containing
       more reads
    :param 100000 max_frag_size: maximum fragment size allowed (fragments should
       not span over several bins)
    :param 100 min_frag_size: remove fragment that are too short (shorter than
       the sequenced read length)
    :param 5 re_proximity: should be adjusted according to RE site, to filter
       semi-dangling-ends
    :param 750 min_dist_to_re: minimum distance the start of a read should be
       from a RE site (usually 1.5 times the insert size). Applied in filter 10
    :param None savedata: PATH where to write the number of reads retained by
       each filter
    :param True fast: parallel version, requires 4 CPUs and more RAM memory

    :return: dicitonary with, as keys, the kind of filter applied, and as values
       a set of read IDs to be removed

    *Note: Filtering is not exclusive, one read can be filtered several times.*
    """

    if not output:
        output = fnam

    if not fast: # mainly for debugging
        if verbose:
            print 'filtering duplicates'
        masked, total = _filter_duplicates(fnam,output)
        if verbose:
            print 'filtering same fragments'
        masked.update(_filter_same_frag(fnam, max_molecule_length, output))
        if verbose:
            print 'filtering fro RE'
        masked.update(_filter_from_res(fnam, max_frag_size, min_dist_to_re,
                                       re_proximity, min_frag_size, output))
        if verbose:
            print 'filtering over representeds'
        masked.update(_filter_over_represented(fnam, over_represented, output))
    else:
        pool = mu.Pool(4)
        a = pool.apply_async(_filter_same_frag,
                             args=(fnam, max_molecule_length, output))
        b = pool.apply_async(_filter_from_res,
                             args=(fnam, max_frag_size, min_dist_to_re,
                                   re_proximity, min_frag_size, output))
        c = pool.apply_async(_filter_over_represented,
                             args=(fnam, over_represented, output))
        d = pool.apply_async(_filter_duplicates,
                             args=(fnam,output))
        pool.close()
        pool.join()
        masked, total = d.get()
        masked.update(b.get())
        masked.update(c.get())
        masked.update(a.get())

    # if savedata or verbose:
    #     bads = len(frozenset().union(*[masked[k]['reads'] for k in masked]))
    if savedata:
        out = open(savedata, 'w')
        out.write('Mapped both\t%d\n' % total)
        for k in xrange(1, len(masked) + 1):
            out.write('%s\t%d\n' % (masked[k]['name'], masked[k]['reads']))
        # out.write('Valid pairs\t%d\n' % (total - bads))
        out.close()
    if verbose:
        print 'Filtered reads (and percentage of total):\n'
        print '     %-25s : %12d (100.00%%)' % ('Mapped both', total)
        print '  ' + '-' * 53
        for k in xrange(1, len(masked) + 1):
            print '  %2d- %-25s : %12d (%6.2f%%)' %(
                k, masked[k]['name'], masked[k]['reads'],
                float(masked[k]['reads']) / total * 100)
        # print '\n     %-25s : %12d (%6.2f%%)' %(
        #     'Valid-pairs', total - bads, float(total - bads) / (
        #         total) * 100)
    return masked

def _filter_same_frag(fnam, max_molecule_length, output):
    # t0 = time()
    masked = {1 : {'name': 'self-circle'       , 'reads': 0}, 
              2 : {'name': 'dangling-end'      , 'reads': 0},
              3 : {'name': 'error'             , 'reads': 0},
              4 : {'name': 'extra dangling-end', 'reads': 0}}
    outfil = {}
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k] = open(masked[k]['fnam'], 'w')
    fhandler = open(fnam)
    line = fhandler.next()
    while line.startswith('#'):
        line = fhandler.next()
    try:
        while True:
            (read,
             cr1, pos1, sd1, _, _, re1,
             cr2, pos2, sd2, _, _, re2) = line.split('\t')
            ps1, ps2, sd1, sd2 = map(int, (pos1, pos2, sd1, sd2))
            if cr1 == cr2:
                if re1 == re2.rstrip():
                    if sd1 != sd2:
                        if (ps2 > ps1) == sd2:
                            # ----<===---===>---                   self-circles
                            masked[1]["reads"] += 1
                            outfil[1].write(read + '\n')
                        else:
                            # ----===>---<===---                   dangling-ends
                            masked[2]["reads"] += 1
                            outfil[2].write(read + '\n')
                    else:
                        # --===>--===>-- or --<===--<===-- or same errors
                        masked[3]["reads"] += 1
                        outfil[3].write(read + '\n')
                elif (abs(ps1 - ps2) < max_molecule_length
                      and sd2 != sd1
                      and (ps2 > ps1) != sd2):
                    # different fragments but facing and very close
                    masked[4]["reads"] += 1
                    outfil[4].write(read + '\n')
            line = fhandler.next()
    except StopIteration:
        pass
    # print 'done 1', time() - t0
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k].close()
    return masked

def _filter_duplicates(fnam, output):
    total = 0
    masked = {9 : {'name': 'duplicated'        , 'reads': 0}}
    outfil = {}
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k] = open(masked[k]['fnam'], 'w')
    uniq_check = set() # huge set
    fhandler = open(fnam)
    line = fhandler.next()
    while line.startswith('#'):
        line = fhandler.next()
    try:
        while True:
            (read,
             cr1, pos1, _, _, _, _,
             cr2, pos2, _, _, _, _) = line.split('\t')
            uniq_key = '_'.join(sorted((cr1 + pos1, cr2 + pos2)))
            if uniq_key in uniq_check:
                masked[9]["reads"] += 1
                outfil[9].write(read + '\n')
            else:
                uniq_check.add(uniq_key)
            total += 1
            line = fhandler.next()
    except StopIteration:
        pass
    del uniq_check
    # print 'done 4', time() - t0
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k].close()
    return masked, total


def _filter_duplicates_DEV(fnam, output):
    # TODO: use mkfifo to create a named pipe that wold hold reads sorted by
    #       columns 2,3 and 8,9. Check redundancy on this file by reading it.
    # t0 = time()
    total = 0
    masked = {9 : {'name': 'duplicated'        , 'reads': 0}}
    outfil = {}
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k] = open(masked[k]['fnam'], 'w')

    proc = Popen(["sort", "-k", "2,9", "-t", "\t", fnam], stdout=PIPE)
    previous = (None, None)
    for line in proc.stdout:
        try:
            (read,
             cr1, pos1, _, _, _, _,
             cr2, pos2, _, _, _, _) = line.split('\t')
        except ValueError:
            continue
        current = sorted((cr1 + pos1, cr2 + pos2))
        if current == previous:
            masked[9]["reads"] += 1
            outfil[9].write(read + '\n')
        previous = current
        total += 1
    proc.wait()
    # print 'done 4', time() - t0
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k].close()
    return masked, total


def _filter_from_res(fnam, max_frag_size, min_dist_to_re,
                     re_proximity, min_frag_size, output):
    # t0 = time()
    masked = {5 : {'name': 'too close from RES', 'reads': 0},
              6 : {'name': 'too short'         , 'reads': 0},
              7 : {'name': 'too large'         , 'reads': 0},
              10: {'name': 'random breaks'     , 'reads': 0}}
    outfil = {}
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k] = open(masked[k]['fnam'], 'w')
    fhandler = open(fnam)
    line = fhandler.next()
    while line.startswith('#'):
        line = fhandler.next()
    try:
        while True:
            (read,
             _, pos1, _, _, rs1, re1,
             _, pos2, _, _, rs2, re2) = line.split('\t')
            ps1, ps2, re1, rs1, re2, rs2 = map(int, (pos1, pos2, re1, rs1, re2, rs2))
            diff11 = re1 - ps1
            diff12 = ps1 - rs1
            diff21 = re2 - ps2
            diff22 = ps2 - rs2
            if ((diff11 < re_proximity) or
                (diff12 < re_proximity) or 
                (diff21 < re_proximity) or
                (diff22 < re_proximity)):
                # multicontacts excluded if fragment is internal (not the first)
                if not '~' in read:
                    masked[5]["reads"] += 1
                    outfil[5].write(read + '\n')
            if (((diff11 > min_dist_to_re) and
                 (diff12 > min_dist_to_re)) or 
                ((diff21 > min_dist_to_re) and
                 (diff22 > min_dist_to_re))):
                masked[10]["reads"] += 1
                outfil[10].write(read + '\n')
            dif1 = re1 - rs1
            dif2 = re2 - rs2
            if (dif1 < min_frag_size) or (dif2 < min_frag_size):
                masked[6]["reads"] += 1
                outfil[6].write(read + '\n')
            if (dif1 > max_frag_size) or (dif2 > max_frag_size):
                masked[7]["reads"] += 1
                outfil[7].write(read + '\n')
            line = fhandler.next()
    except StopIteration:
        pass
    # print 'done 2', time() - t0
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k].close()
    return masked

def _filter_over_represented(fnam, over_represented, output):
    # t0 = time()
    frag_count = count_re_fragments(fnam)
    num_frags = len(frag_count)
    cut = int((1 - over_represented) * num_frags + 0.5)
    # use cut-1 because it represents the length of the list
    cut = sorted([frag_count[crm] for crm in frag_count])[cut - 1]
    masked = {8 : {'name': 'over-represented'  , 'reads': 0}}
    outfil = {}
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k] = open(masked[k]['fnam'], 'w')
    fhandler = open(fnam)
    line = fhandler.next()
    while line.startswith('#'):
        line = fhandler.next()
    try:
        while True:
            read, cr1,  _, _, _, rs1, _, cr2, _, _, _, rs2, _ = line.split('\t')
            if (frag_count.get((cr1, rs1), 0) > cut or
                  frag_count.get((cr2, rs2), 0) > cut):
                masked[8]["reads"] += 1
                outfil[8].write(read + '\n')
            line = fhandler.next()
    except StopIteration:
        pass
    # print 'done 3', time() - t0
    for k in masked:
        masked[k]['fnam'] = output + '_' + masked[k]['name'].replace(' ', '_') + '.tsv'
        outfil[k].close()
    return masked