"""

information needed

 - path working directory with mapped reads or list of SAM/BAM/MAP files

"""

from argparse                       import HelpFormatter
from pytadbit.utils.sqlite_utils    import print_db
import sqlite3 as lite
from os import path

DESC = "Describe jobs and results in a given working directory"

def run(opts):
    check_options(opts)
    con = lite.connect(path.join(opts.workdir, 'trace.db'))
    with con:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for table in cur.fetchall():
            if table[0].lower() in opts.tables:
                print_db(cur, table[0])

def populate_args(parser):
    """
    parse option from call
    """
    parser.formatter_class=lambda prog: HelpFormatter(prog, width=95,
                                                      max_help_position=27)

    glopts = parser.add_argument_group('General options')

    glopts.add_argument('-w', '--workdir', dest='workdir', metavar="PATH",
                        action='store', default=None, type=str,
                        help='''path to working directory (generated with the
                        tool tadbit mapper)''')

    glopts.add_argument('-t', '--table', dest='tables', metavar='',
                        action='store', nargs='+', type=str,
                        choices=['1', 'paths', '2', 'jobs',
                                 '3', 'mapped_outputs',
                                 '4', 'mapped_inputs', '5', 'parsed_outputs',
                                 '6', 'intersection_outputs',
                                 '7', 'filter_outputs', '8', 'normalize_outputs'],
                        default=tuple(range(1, 8)),
                        help='''[%(default)s] what tables to show, wrte either the sequence of
                        names or indexes, according to this list:
                        1: paths, 2: jobs, 3: mapped_outputs,
                        4: mapped_inputs, 5: parsed_outputs,
                        6: intersection_outputs, 7: filter_outputs,
                        8: normalize_outputs''')

    parser.add_argument_group(glopts)

def check_options(opts):
    if not opts.workdir: raise Exception('ERROR: output option required.')

    table_idx = {
        '1': 'paths',
        '2': 'jobs',
        '3': 'mapped_outputs',
        '4': 'mapped_inputs',
        '5': 'parsed_outputs',
        '6': 'intersection_outputs',
        '7': 'filter_outputs',
        '8': 'normalize_outputs'}
    for t in range(len(opts.tables)):
        opts.tables[t] = table_idx.get(opts.tables[t].lower(),
                                         opts.tables[t].lower())
