
import os
import shutil
import unittest

from ample import constants
from ample.modelling import rosetta_model

class Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.thisd =  os.path.abspath( os.path.dirname( __file__ ) )
        cls.ample_share = constants.SHARE_DIR
        cls.testfiles_dir = os.path.join(cls.ample_share,'testfiles')

    def XtestMakeFragments(self):
        """See we can create fragments"""

        optd = {}
        optd['rosetta_dir'] = "/opt/rosetta3.4"
        optd['name'] = "TOXD_"
        optd['work_dir'] =  os.getcwd()
        optd['use_homs'] =  True
        optd['make_frags'] = True
        optd['rosetta_db'] = None
        optd['rosetta_fragments_exe'] =  "/tmp/make_fragments.pl"
        #optd['rosetta_fragments_exe'] =  None
        optd['fasta'] = os.path.join(self.ample_share + "examples", "toxd-example", 
                                     "input", "toxd_.fasta")

        optd['make_models'] = False
        optd['frags_3mers'] = None
        optd['frags_9mers'] = None
        optd['improve_template'] = None

        m = rosetta_model.RosettaModel(optd=optd)
        m.generate_fragments()

    def XtestNoRosetta(self):
        """
        Test without Rosetta
        """
        os.chdir(self.thisd) # Need as otherwise tests that happen in other directories change os.cwd()

        ## Create a dummy script
        script = "dummy_rosetta.sh"
        with open(script,"w") as f:
            content = """#!/usr/bin/env python
for i in range(10):
    f = open( "rosy_{0}.pdb".format(i), "w")
    f.write( "rosy_{0}.pdb".format(i) )
    f.close()"""
            f.write(content)
        os.chmod(script, 0o777)
        
        # Create dummy fragment files
        frags3='3mers'
        frags9='9mers'
        with open(frags3,'w') as f3,open(frags9,'w') as f9:
            f3.write(frags3+"\n")
            f9.write(frags9+"\n")

        # Set options
        optd={}
        optd['nproc'] = 3
        optd['nmodels'] = 30
        optd['work_dir'] = os.getcwd()
        optd['models_dir'] = "XXXmodelsXXX"
        optd['rosetta_db'] = None
        optd['rosetta_dir'] = "/opt/rosetta3.4"
        optd['rosetta_AbinitioRelax'] = os.path.join(os.getcwd(),script)
        optd['frags_3mers'] = frags3
        optd['frags_9mers'] = frags9
        optd['rosetta_fragments_exe'] = None
        optd['use_homs'] = None
        optd['make_models'] = True
        optd['make_frags'] =  False
        optd['fasta'] = "FASTA"
        optd['name'] = "TOXD_"
        optd['improve_template'] = None
        optd['all_atom'] = True
        optd['benchmark_mode'] = False
        optd['transmembrane'] = False
        optd['psipred_ss2'] = None
        optd['rg_reweight'] = None

        optd['domain_termini_distance'] = None
        optd['CC'] = None
        optd['improve_template'] = None

        rm = rosetta_model.RosettaModel(optd=optd)
        mdir = rm.doModelling()
        
        os.unlink(script)
        os.unlink('seedlist')
        os.unlink(frags3)
        os.unlink(frags9)
        shutil.rmtree(mdir)
        
