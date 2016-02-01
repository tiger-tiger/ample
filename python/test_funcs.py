'''
Created on 29 Dec 2015

@author: jmht
'''
import argparse
import cPickle
import imp
import os
import shutil
import sys
import unittest

# Our imports
from ample_util import SCRIPT_EXT, SCRIPT_HEADER
import workers

AMPLE_DIR = os.sep.join(os.path.abspath(os.path.dirname(__file__)).split(os.sep)[ :-1 ])

CLUSTER_ARGS = [ [ '-submit_cluster', 'True' ],
                 [ '-submit_qtype', 'SGE' ],
                 [ '-submit_array', 'True' ],
                 [ '-no_gui', 'True' ],
                 #[ '-submit_max_array', None ],
                 #[ '-submit_queue', None ],
                ]

class AMPLEBaseTest(unittest.TestCase):
    RESULTS_PKL = None
    AMPLE_DICT = None
    def setUp(self):
        self.assertTrue(os.path.isfile(self.RESULTS_PKL),"Missing pkl file: {0}".format(self.RESULTS_PKL))
        with open(self.RESULTS_PKL) as f: self.AMPLE_DICT = cPickle.load(f)
        return

def clean(test_dict):
    for name in test_dict.keys():
        run_dir = test_dict[name]['directory']
        os.chdir(run_dir)
        print "Cleaning {0} in directory {1}".format(name, run_dir)
        work_dir = os.path.join(run_dir, name)
        if os.path.isdir(work_dir): shutil.rmtree(work_dir)
        logfile = work_dir + '.log'
        if os.path.isfile(logfile): os.unlink(logfile)  
        script = work_dir + SCRIPT_EXT
        if os.path.isfile(script): os.unlink(script)

def is_in_args(argt, args):
    if type(argt) is str:
        key = argt
    else:
        key = argt[0]
    return key in [ a[0] for a in args ]
        
def load_module(mod_name, paths):
    try:
        mfile, pathname, desc = imp.find_module(mod_name, paths)
    except ImportError as e:
        print "Cannot find module: {0} - {1}".format(mod_name,e)
        return None
    
    try:
        test_module = imp.load_module(mod_name, mfile, pathname, desc)
    finally:
        mfile.close()
 
    return test_module

def parse_args(test_dict=None, extra_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-clean', action='store_true', default=False,
                        help="Clean up all test files/directories")
    parser.add_argument('-nproc', type=int, default=1,
                        help="Number of processors to run on (1 per job)")
    parser.add_argument('-dry_run', action='store_true', default=False,
                        help="Don\'t actually run the jobs")
    parser.add_argument('-rosetta_dir',
                        help="Location of rosetta installation directory")
    parser.add_argument('-submit_cluster', action='store_true', default=False,
                        help="Submit to a cluster queueing system")
    parser.add_argument('-test_cases', nargs='+',
                        help="A list of test cases to run")
    
    args = parser.parse_args()
    if args.rosetta_dir and not os.path.isdir(args.rosetta_dir):
        print "Cannot find rosetta_dir: {0}".format(args.rosetta_dir)
        sys.exit(1)
    
    argd = vars(args)
    if test_dict:
        if args.clean:
            clean(test_dict)
        else:
            run(test_dict, extra_args=extra_args, **argd)
    else:
        return argd
    
def replace_arg(new_arg, args):
    for i, a in enumerate(args):
        if a[0] == new_arg[0]:
            args[i] = new_arg
            return args
    assert False
    return

def run(test_dict,
        nproc=1,
        submit_cluster=False,
        dry_run=False,
        clean_up=True,
        rosetta_dir=None,
        extra_args=None,
        test_cases=None,
        **kw):

    if dry_run: clean_up = False
    
    if test_cases:
        # Check that we can find the given cases in the complete list
        missing = set(test_cases).difference(set(test_dict.keys()))
        if missing:
            raise RuntimeError,"Cannot find test cases: {0}".format(", ".join(missing))
    else:
        test_cases = test_dict.keys()

    # Create scripts and path to resultsd
    scripts = []
    owd = os.getcwd()
    for name in test_cases:
        run_dir = test_dict[name]['directory']
        os.chdir(run_dir)
        work_dir = os.path.join(run_dir, name)
        args = test_dict[name]['args']
        # Rosetta is the only think likely to change between platforms so we update the entry
        if rosetta_dir and is_in_args('-rosetta_dir', args):
            args = update_args(args, [['-rosetta_dir', rosetta_dir]])
        if extra_args:
            args = update_args(args, extra_args)
        if submit_cluster:
            args = update_args(args, CLUSTER_ARGS)
        script = write_script(work_dir,  args + [['-work_dir', work_dir]])
        scripts.append(script)
        # Set path to the results pkl file we will use to run the tests
        test_dict[name]['resultsd'] = os.path.join(work_dir,'resultsd.pkl')
        if clean_up:
            if os.path.isdir(work_dir): shutil.rmtree(work_dir)
            logfile = work_dir + '.log'
            if os.path.isdir(logfile): os.unlink(logfile)
        
        # Back to where we started
        os.chdir(owd)
    
    # Run all the jobs
    # If we're running on a cluster, we run on as many processors as there are jobs, as the jobs are just
    # sitting and monitoring the queue
    if submit_cluster:
        nproc = len(scripts)
        
    if not dry_run:
        workers.run_scripts(job_scripts=scripts,
                            monitor=None,
                            chdir=True,
                            nproc=nproc,
                            job_name='test')
    
    # Now run the tests
    all_suites = []
    for name in test_cases:
        testClass = test_dict[name]['test']
        testClass.RESULTS_PKL = test_dict[name]['resultsd']
        all_suites.append(unittest.TestLoader().loadTestsFromTestCase(testClass)) 
    
    return unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(all_suites))

def write_script(path, args):
    """Write script - ARGS MUST BE IN PAIRS"""
    ample = os.path.join(AMPLE_DIR,'bin', 'ample.py')
    script = path + SCRIPT_EXT
    with open(script, 'w') as f:
        f.write(SCRIPT_HEADER + os.linesep)
        f.write(os.linesep)
        f.write(ample + " \\" + os.linesep)
        # Assumption is all arguments are in pairs
        #arg_list = [ " ".join(args[i:i+2]) for i in range(0, len(args), 2) ]
        #f.write(" \\\n".join(arg_list))
        for argt in args:
            f.write(" ".join(argt) + " \\\n")
        f.write(os.linesep)
        f.write(os.linesep)
    
    os.chmod(script, 0o777)
    return os.path.abspath(script)

def update_args(args, new_args):
    """Add/update any args"""
    for argt in new_args:
        if not is_in_args(argt, args):
            args.append(argt)
        else:
            replace_arg(argt, args)
    return args
