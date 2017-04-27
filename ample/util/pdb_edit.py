"""Useful manipulations on PDB files"""

from __future__ import division, print_function

__author__ = "Adam Simpkin, Jens Thomas & Felix Simkovic"
__date__ = "21 Apr 2017"
__version__ = "2.0"

import glob
import logging
import numpy as np
import os
import tempfile

from cctbx.array_family import flex

import iotbx.file_reader
import iotbx.pdb
import iotbx.pdb.amino_acid_codes

import ample_util
import chemistry
import pdb_model
import residue_map
import sequence_util

three2one = iotbx.pdb.amino_acid_codes.one_letter_given_three_letter
one2three = iotbx.pdb.amino_acid_codes.three_letter_given_one_letter

logger = logging.getLogger()


#  OLD CODE
# def rename_chains(inpdb=None, outpdb=None, fromChain=None, toChain=None):
#     """Rename Chains
#     """
#
#     assert len(fromChain) == len(toChain)
#
#     logfile = outpdb + ".log"
#     cmd = "pdbcur xyzin {0} xyzout {1}".format(inpdb, outpdb).split()
#
#     # Build up stdin
#     stdin = ""
#     for i in range(len(fromChain)):
#         stdin += "renchain {0} {1}\n".format(fromChain[i], toChain[i])
#
#     retcode = ample_util.run_command(cmd=cmd, logfile=logfile, directory=os.getcwd(), dolog=False, stdin=stdin)
#
#     if retcode == 0:
#         # remove temporary files
#         os.unlink(logfile)
#     else:
#         raise RuntimeError, "Error renaming chains {0}".format(fromChain)
#
#     return
#
# def renumber_residues(pdbin, pdbout, start=1):
#     """ Renumber the residues in the chain """
#     pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
#     hierarchy = pdb_input.construct_hierarchy()
#
#     _renumber(hierarchy, start)
#
#     with open(pdbout, 'w') as f:
#         f.write("REMARK Original file:\n")
#         f.write("REMARK   {0}\n".format(pdbin))
#         f.write(hierarchy.as_pdb_string(anisou=False))
#     return
#
#
# def _renumber(hierarchy, start):
#     for model in hierarchy.models():
#         for chain in model.chains():
#             for idx, residue_group in enumerate(chain.residue_groups()):
#                 residue_group.resseq = idx + start
#     return
#
# def standardise(pdbin, pdbout, chain=None, del_hetatm=False):
#     """Rename any non-standard AA, remove solvent and only keep most probably conformation.
#     """
#
#     tmp1 = ample_util.tmp_file_name() + ".pdb"  # pdbcur insists names have a .pdb suffix
#
#     # Now clean up with pdbcur
#     logfile = tmp1 + ".log"
#     cmd = "pdbcur xyzin {0} xyzout {1}".format(pdbin, tmp1).split()
#     stdin = """delsolvent
# noanisou
# mostprob
# """
#     # We are extracting one  of the chains
#     if chain: stdin += "lvchain {0}\n".format(chain)
#
#     retcode = ample_util.run_command(cmd=cmd, logfile=logfile, directory=os.getcwd(), dolog=False, stdin=stdin)
#     if retcode == 0:
#         os.unlink(logfile)  # remove temporary files
#     else:
#         raise RuntimeError("Error standardising pdb!")
#
#     # Standardise AA names and then remove any remaining HETATMs
#     std_residues_cctbx(tmp1, pdbout, del_hetatm=del_hetatm)
#     os.unlink(tmp1)
#
#     return retcode


def _first_chain_only(h):
    for i, m in enumerate(h.models()):
        if i != 0:
            h.remove_model(m)
    m = h.models()[0]
    for i, c in enumerate(m.chains()):
        if i != 0:
            m.remove_chain(c)


def _select(h, sel):
    sel_cache = h.atom_selection_cache().selection(sel)
    return h.select(sel_cache)
        

def backbone(pdbin, pdbout):
    """Only output backbone atoms
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    hierarchy_new = _select(hierarchy, "name n or name ca or name c or name o or name cb")
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy_new.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def calpha_only(pdbin, pdbout):
    """Strip PDB to c-alphas only
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    hierarchy_new = _select(hierarchy, "name ca")
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy_new.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def check_pdb_directory(directory, single=True, allsame=True, sequence=None):
    """Check a directory of structure files

    Parameters
    ----------
    directory : str
       The path to the structure file directory
    single : bool, optional
       Each file contains a single model [default: True]
    allsame : bool, optional
       All structures contain the same sequence [default: True]
    sequence : str, optional
       The sequence of all models

    Returns
    -------
    bool
       A status describing if all structure files are okay

    """
    logger.info("Checking pdbs in directory: %s", directory)
    if os.path.isdir(directory):
        models = glob.glob(os.path.join(directory, "*.pdb"))
        if len(models) > 0 and not (single or sequence or allsame):
            return True
        elif len(models) > 0:
            return check_pdbs(models, sequence=sequence, single=single, allsame=allsame)
        else:
            logger.critical("Cannot find any pdb files in directory: %s", directory)
    else:
        logger.critical("Cannot find directory: %s", directory)
    return False


def check_pdbs(models, single=True, allsame=True, sequence=None):
    """Check a set of structure files

    Parameters
    ----------
    models : list
       A list of paths to structure files
    single : bool, optional
       Each file contains a single model [default: True]
    allsame : bool, optional
       All structures contain the same sequence [default: True]
    sequence : str, optional
       The sequence of all models

    Returns
    -------
    bool
       A status describing if all structure files are okay

    """
    # Get sequence from first model
    if allsame and not sequence:
        try:
            h = iotbx.pdb.pdb_input(models[0]).construct_hierarchy()
        except Exception as e:
            s = "*** ERROR reading sequence from first pdb: {0}\n{1}".format(models[0], e)
            logger.critical(s)
            return False
        sequence = _sequence1(h)  # only one model/chain

    # Store info as simple array - errors, multi, no_protein, sequence_err
    summary = np.zeros((0, 5), dtype=np.uint8)
    for idx, pdb in enumerate(models):
        entry = np.zeros((1, 5), dtype=np.uint8)
        entry[0][0] = idx
        try:
            h = iotbx.pdb.pdb_input(pdb).construct_hierarchy()
        except Exception:
            entry[0][1] = 1
            continue
        if single and h.models_size() != 1 and h.models()[0].chains_size() != 1:
            entry[0][2] = 1
        elif single and not h.models()[0].chains()[0].is_protein():
            entry[0][3] = 1
        elif sequence and sequence != _sequence(h).values()[0]:
            entry[0][4] = 1
        summary = np.concatenate((summary, entry), axis=0)

    # The summary table has no error messages (indicated by 0s)
    if np.count_nonzero(summary[:, 1:]) == 0:
        logger.info("check_pdb_directory - pdb files all seem valid")
        return True
    # The summary table has error messages (indicated by non-0s)
    else:
        s = "\n*** ERROR ***\n"
        if np.count_nonzero(summary[:, 1]) != 0:
            s += "The following pdb files have errors:\n\n"
            for idx in np.nonzero(summary[:, 1])[0]:
                s += "\t{0}\n".format(models[idx])
        elif np.count_nonzero(summary[:, 2]) != 0:
            s += "The following pdb files have more than one chain:\n\n"
            for idx in np.nonzero(summary[:, 2])[0]:
                s += "\t{0}\n".format(models[idx])
        elif np.count_nonzero(summary[:, 3]) != 0:
            s += "The following pdb files do not appear to contain any protein:\n\n"
            for idx in np.nonzero(summary[:, 3])[0]:
                s += "\t{0}\n".format(models[idx])
        elif np.count_nonzero(summary[:, 4]) != 0:
            s += "The following pdb files have diff sequences from the ref sequence: {0}\n\n".format(sequence)
            for idx in np.nonzero(summary[:, 4])[0]:
                s += "\t{0}\n".format(models[idx])
        logger.critical(s)
        return False


def extract_chain(pdbin, pdbout, chain_id, new_chain_id=None, c_alpha=False, renumber=False):
    """Extract a chain from the input PDB
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    chain_id : str
       The chain to extract
    new_chain_id : str, optional
       The chain ID to rename ``chain_id`` to
    c_alpha : bool, optional
       Strip chain residues back to c-alpha atoms [defaut: False]
    renumber : bool, optional
       Renumber the chain [default: False]
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    sel_string = "chain %s and not hetatm" % chain_id
    if c_alpha:
        sel_string += " and name ca" 
    hierarchy_new = _select(hierarchy, sel_string)

    if new_chain_id:
        for model in hierarchy_new.models():
            for chain in model.chains():
                chain.id = new_chain_id

    if renumber:
        _renumber(hierarchy_new, 1)
        hierarchy_new.atoms().reset_serial()

    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy_new.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def extract_model(pdbin, pdbout, model_id):
    """Extract a model from the input PDB

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    model_id : str
       The model to extract

    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    hierarchy_new = _select(hierarchy, "model {0}".format(model_id))
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy_new.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def extract_resSeq(pdbin, chain_id=None):
    """Extract a residue numbers of the input PDB

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    chain_id : str, optional
       The chain to extract

    Returns
    -------
    list
       A list of the residue numbers

    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    hierarchy = pdb_input.construct_hierarchy()

    # We only consider chains from the first model in the hierarchy
    chains = {}
    for chain in hierarchy.models()[0].chains():
        # Check required to avoid overwriting ATOM chain with HETATM one
        if chain.id not in chains:
            chains[chain.id] = chain

    if chain_id is None:
        chain_id = hierarchy.models()[0].chains()[0].id

    return [rg.resseq_as_int() for rg in chains[chain_id].residue_groups()]


def keep_residues(pdbin, pdbout, residue_range, chain_id):
    """Given a range relative to the first residue for a specific chain ID,
    keeps only the residues in that given range

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    residue_range : list, tuple
       The range of residues to keep
    chain_id : str
       The chain to extract
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    # Only keep the specified chain ID
    for model in hierarchy.models():
        for chain in model.chains():
            if chain.id != chain_id:
                model.remove_chain(chain=chain)

    # Renumber the chain
    _renumber(hierarchy, start=1)

    # Remove residues outside the desired range
    residues_to_keep = range(residue_range[0], residue_range[1] + 1)
    for model in hierarchy.models():
        for chain in model.chains():
            for rg in chain.residue_groups():
                if rg.resseq_as_int() not in residues_to_keep:
                    chain.remove_residue_group(rg)

    # remove hetatms
    _strip(hierarchy, hetatm=True)

    # Write to file
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def keep_matching(refpdb=None, targetpdb=None, outpdb=None, resSeqMap=None):
    """Only keep those atoms in targetpdb that are in refpdb and write the result to outpdb.
    We also take care of renaming any chains.
    """

    assert refpdb and targetpdb and outpdb and resSeqMap

    # Paranoid check
    if False:
        refinfo = get_info(refpdb)
        targetinfo = get_info(targetpdb)
        if len(refinfo.models) > 1 or len(targetinfo.models) > 1:
            raise RuntimeError("PDBS contain more than 1 model!")

        if refinfo.models[0].chains != targetinfo.models[0].chains:
            raise RuntimeError("Different numbers/names of chains {0}->{1} between {2} and {3}!".format(
                refinfo.models[0].chains,
                targetinfo.models[0].chains,
                refpdb,
                targetpdb
            ))
            # Now we do our keep matching
    tmp1 = ample_util.tmp_file_name() + ".pdb"  # pdbcur insists names have a .pdb suffix

    _keep_matching(refpdb, targetpdb, tmp1, resSeqMap=resSeqMap)

    # now renumber with pdbcur
    logfile = tmp1 + ".log"
    cmd = "pdbcur xyzin {0} xyzout {1}".format(tmp1, outpdb).split()
    stdint = """sernum
"""
    retcode = ample_util.run_command(cmd=cmd, logfile=logfile, directory=os.getcwd(), dolog=False, stdin=stdint)

    if retcode == 0:
        # remove temporary files
        os.unlink(tmp1)
        os.unlink(logfile)

    return retcode


def _keep_matching(refpdb=None, targetpdb=None, outpdb=None, resSeqMap=None):
    """Create a new pdb file that only contains that atoms in targetpdb that are
    also in refpdb. It only considers ATOM lines and discards HETATM lines in the target.

    Args:
    refpdb: path to pdb that contains the minimal set of atoms we want to keep
    targetpdb: path to the pdb that will be stripped of non-matching atoms
    outpdb: output path for the stripped pdb
    """

    assert refpdb and targetpdb and outpdb and resSeqMap

    def _output_residue(refResidues, targetAtomList, resSeqMap, outfh):
        """Output a single residue only outputting matching atoms, shuffling the atom order and changing the resSeq num"""

        # Get the matching list of atoms
        targetResSeq = targetAtomList[0].resSeq

        refResSeq = resSeqMap.ref2target(targetResSeq)

        # Get the atomlist for the reference
        for (rid, alist) in refResidues:
            if rid == refResSeq:
                refAtomList = alist
                break

        # Get ordered list of the ref atom names for this residue
        rnames = [x.name for x in refAtomList]

        if len(refAtomList) > len(targetAtomList):
            s = "Cannot keep matching as refAtomList is > targetAtomList for residue {0}\nRef: {1}\nTrg: {2}".format(
                targetResSeq,
                rnames,
                [x.name for x in targetAtomList]
            )
            raise RuntimeError(s)

        # Remove any not matching in the target
        alist = []
        for atom in targetAtomList:
            if atom.name in rnames:
                alist.append(atom)

        # List now only contains matching atoms
        targetAtomList = alist

        # Now just have matching so output in the correct order
        for refname in rnames:
            for i, atom in enumerate(targetAtomList):
                if atom.name == refname:
                    # Found the matching atom

                    # Change resSeq and write out
                    atom.resSeq = refResSeq
                    outfh.write(atom.toLine() + "\n")

                    # now delete both this atom and the line
                    targetAtomList.pop(i)

                    # jump out of inner loop
                    break
        return

    # Go through refpdb and find which refResidues are present
    refResidues = []
    targetResSeq = []  # ordered list of tuples - ( resSeq, [ list_of_atoms_for_that_residue ] )

    last = None
    chain = -1
    for line in open(refpdb, 'r'):

        if line.startswith("MODEL"):
            raise RuntimeError("Multi-model file!")

        if line.startswith("TER"):
            break

        if line.startswith("ATOM"):
            a = pdb_model.PdbAtom(line)

            # First atom/chain
            if chain == -1:
                chain = a.chainID

            if a.chainID != chain:
                raise RuntimeError("ENCOUNTERED ANOTHER CHAIN! {0}".format(line))

            if a.resSeq != last:
                last = a.resSeq

                # Add the corresponding resSeq in the target
                targetResSeq.append(resSeqMap.target2ref(a.resSeq))
                refResidues.append((a.resSeq, [a]))
            else:
                refResidues[-1][1].append(a)

    # Now read in target pdb and output everything bar the atoms in this file that
    # don't match those in the refpdb
    t = open(targetpdb, 'r')
    out = open(outpdb, 'w')

    chain = None  # The chain we're reading
    residue = None  # the residue we're reading
    targetAtomList = []

    for line in t:

        if line.startswith("MODEL"):
            raise RuntimeError("Multi-model file!")

        if line.startswith("ANISOU"):
            raise RuntimeError("I cannot cope with ANISOU! {0}".format(line))

        # Stop at TER
        if line.startswith("TER"):
            _output_residue(refResidues, targetAtomList, resSeqMap, out)
            # we write out our own TER
            out.write("TER\n")
            continue

        if line.startswith("ATOM"):

            atom = pdb_model.PdbAtom(line)

            # First atom/chain
            if chain == None:
                chain = atom.chainID

            if atom.chainID != chain:
                raise RuntimeError("ENCOUNTERED ANOTHER CHAIN! {0}".format(line))

            if atom.resSeq in targetResSeq:

                # If this is the first one add the empty tuple and reset residue
                if atom.resSeq != residue:
                    if residue != None:  # Dont' write out owt for first atom
                        _output_residue(refResidues, targetAtomList, resSeqMap, out)
                    targetAtomList = []
                    residue = atom.resSeq

                # If not first keep adding
                targetAtomList.append(atom)

                # We don't write these out as we write them with _output_residue
                continue

            else:
                # discard this line as not a matching atom
                continue

        # For time being exclude all HETATM lines
        elif line.startswith("HETATM"):
            continue
        # Endif line.startswith("ATOM")

        # Output everything else
        out.write(line)

    # End reading loop

    t.close()
    out.close()

    return


def get_info(inpath):
    """Read a PDB and extract as much information as possible into a PdbInfo object
    """

    info = pdb_model.PdbInfo()
    info.pdb = inpath

    currentModel = None
    currentChain = -1

    modelAtoms = []  # list of models, each of which is a list of chains with the list of atoms

    # Go through refpdb and find which ref_residues are present
    f = open(inpath, 'r')
    line = f.readline()
    while line:

        # First line of title
        if line.startswith('HEADER'):
            info.pdbCode = line[62:66].strip()

        # First line of title
        if line.startswith('TITLE') and not info.title:
            info.title = line[10:-1].strip()

        if line.startswith("REMARK"):

            try:
                numRemark = int(line[7:10])
            except ValueError:
                line = f.readline()
                continue

            # Resolution
            if numRemark == 2:
                line = f.readline()
                if line.find("RESOLUTION") != -1:
                    try:
                        info.resolution = float(line[25:30])
                    except ValueError:
                        # RESOLUTION. NOT APPLICABLE.
                        info.resolution = -1

            # Get solvent content
            if numRemark == 280:

                maxread = 5
                # Clunky - read up to maxread lines to see if we can get the information we're after
                # We assume the floats are at the end of the lines
                for _ in range(maxread):
                    line = f.readline()
                    if line.find("SOLVENT CONTENT") != -1:
                        try:
                            info.solventContent = float(line.split()[-1])
                        except ValueError:
                            # Leave as None
                            pass
                    if line.find("MATTHEWS COEFFICIENT") != -1:
                        try:
                            info.matthewsCoefficient = float(line.split()[-1])
                        except ValueError:
                            # Leave as None
                            pass
        # End REMARK

        if line.startswith("CRYST1"):
            try:
                info.crystalInfo = pdb_model.CrystalInfo(line)
            except ValueError, e:
                # Bug in pdbset nukes the CRYST1 line so we need to catch this
                print("ERROR READING CRYST1 LINE in file {0}\":{1}\"\n{2}".format(inpath, line.rstrip(), e))
                info.crystalInfo = None

        if line.startswith("MODEL"):
            if currentModel:
                # Need to make sure that we have an id if only 1 chain and none given
                if len(currentModel.chains) <= 1:
                    if currentModel.chains[0] is None:
                        currentModel.chains[0] = 'A'

                info.models.append(currentModel)

            # New/first model
            currentModel = pdb_model.PdbModel()
            # Get serial
            currentModel.serial = int(line.split()[1])

            currentChain = None
            modelAtoms.append([])

        # Count chains (could also check against the COMPND line if present?)
        if line.startswith('ATOM'):

            # Create atom object
            atom = pdb_model.PdbAtom(line)

            # Check for the first model
            if not currentModel:
                # This must be the first model and there should only be one
                currentModel = pdb_model.PdbModel()
                modelAtoms.append([])

            if atom.chainID != currentChain:
                currentChain = atom.chainID
                currentModel.chains.append(currentChain)
                modelAtoms[-1].append([])

            modelAtoms[-1][-1].append(atom)

        # Can ignore TER and ENDMDL for time being as we'll pick up changing chains anyway,
        # and new models get picked up by the models line

        line = f.readline()
        # End while loop

    # End of reading loop so add the last model to the list
    info.models.append(currentModel)

    f.close()

    bbatoms = ['N', 'CA', 'C', 'O', 'CB']

    # Now process the atoms
    for modelIdx, model in enumerate(info.models):

        chainList = modelAtoms[modelIdx]

        for chainIdx, atomList in enumerate(chainList):

            # Paranoid check
            assert model.chains[chainIdx] == atomList[0].chainID

            # Add list of atoms to model
            model.atoms.append(atomList)

            # Initialise new chain
            currentResSeq = atomList[0].resSeq
            currentResName = atomList[0].resName
            model.resSeqs.append([])
            model.sequences.append("")
            model.caMask.append([])
            model.bbMask.append([])

            atomTypes = []
            for i, atom in enumerate(atomList):

                aname = atom.name.strip()
                if atom.resSeq != currentResSeq and i == len(atomList) - 1:
                    # Edge case - last residue containing one atom
                    atomTypes = [aname]
                else:
                    if aname not in atomTypes:
                        atomTypes.append(aname)

                if atom.resSeq != currentResSeq or i == len(atomList) - 1:
                    # End of reading the atoms for a residue
                    model.resSeqs[chainIdx].append(currentResSeq)
                    model.sequences[chainIdx] += three2one[currentResName]

                    if 'CA' not in atomTypes:
                        model.caMask[chainIdx].append(True)
                    else:
                        model.caMask[chainIdx].append(False)

                    missing = False
                    for bb in bbatoms:
                        if bb not in atomTypes:
                            missing = True
                            break

                    if missing:
                        model.bbMask[chainIdx].append(True)
                    else:
                        model.bbMask[chainIdx].append(False)

                    currentResSeq = atom.resSeq
                    currentResName = atom.resName
                    atomTypes = []

    return info


def match_resseq(targetPdb=None, outPdb=None, resMap=None, sourcePdb=None):
    """

    """

    assert sourcePdb or resMap
    assert not (sourcePdb and resMap)

    if not resMap:
        resMap = residue_map.residueSequenceMap(targetPdb, sourcePdb)

    target = open(targetPdb, 'r')
    out = open(outPdb, 'w')

    chain = None  # The chain we're reading
    residue = None  # the residue we're reading

    for line in target:

        if line.startswith("MODEL"):
            raise RuntimeError("Multi-model file!")

        if line.startswith("ANISOU"):
            raise RuntimeError("I cannot cope with ANISOU! {0}".format(line))

        # Stop at TER
        if line.startswith("TER"):
            # we write out our own TER
            # out.write("TER\n")
            # break
            pass

        if line.startswith("ATOM"):

            atom = pdb_model.PdbAtom(line)

            # First atom/chain
            if chain == None:
                chain = atom.chainID

            if atom.chainID != chain:
                pass
                # raise RuntimeError, "ENCOUNTERED ANOTHER CHAIN! {0}".format( line )

            # Get the matching resSeq for the model
            modelResSeq = resMap.ref2target(atom.resSeq)
            if modelResSeq == atom.resSeq:
                out.write(line)
            else:
                atom.resSeq = modelResSeq
                out.write(atom.toLine() + "\n")
            continue
        # Endif line.startswith("ATOM")

        # Output everything else
        out.write(line)

    # End reading loop

    target.close()
    out.close()

    return


def merge(pdb1=None, pdb2=None, pdbout=None):
    """Merge two pdb files into one"""

    logfile = pdbout + ".log"
    cmd = ['pdb_merge', 'xyzin1', pdb1, 'xyzin2', pdb2, 'xyzout', pdbout]

    # Build up stdin
    stdin = 'nomerge'
    retcode = ample_util.run_command(cmd=cmd, logfile=logfile, directory=os.getcwd(), dolog=False, stdin=stdin)

    if retcode == 0:
        # remove temporary files
        os.unlink(logfile)
    else:
        raise RuntimeError("Error merging pdbs: {0} {1}".format(pdb1, pdb2))

    return


def most_prob(hierarchy, always_keep_one_conformer=True):
    """
    Remove all alternate conformers from the hierarchy.  Depending on the
    value of always_keep_one_conformer, this will either remove any atom_group
    with altloc other than blank or 'A', or it will remove any atom_group
    beyond the first conformer found.
    """

    # Taken from
    # ftp://ftp.ccp4.ac.uk/ccp4/6.4.0/unpacked/lib/cctbx/cctbx_sources/cctbx_project/mmtbx/pdbtools.py

    for model in hierarchy.models():
        for chain in model.chains():
            for residue_group in chain.residue_groups():
                atom_groups = residue_group.atom_groups()
                assert (len(atom_groups) > 0)
                if always_keep_one_conformer:
                    if (len(atom_groups) == 1) and (atom_groups[0].altloc == ''):
                        continue
                    atom_groups_and_occupancies = []
                    for atom_group in atom_groups:
                        if '' == atom_group.altloc:
                            continue
                        mean_occ = flex.mean(atom_group.atoms().extract_occ())
                        atom_groups_and_occupancies.append((atom_group, mean_occ))
                    atom_groups_and_occupancies.sort(lambda a, b: cmp(b[1], a[1]))
                    for atom_group, occ in atom_groups_and_occupancies[1:]:
                        residue_group.remove_atom_group(atom_group=atom_group)
                    single_conf, occ = atom_groups_and_occupancies[0]
                    single_conf.altloc = ''
                else:
                    for atom_group in atom_groups:
                        if not atom_group.altloc in ["", "A"]:
                            residue_group.remove_atom_group(atom_group=atom_group)
                        else:
                            atom_group.altloc = ""
                    if len(residue_group.atom_groups()) == 0:
                        chain.remove_residue_group(residue_group=residue_group)
            if len(chain.residue_groups()) == 0:
                model.remove_chain(chain=chain)
    atoms = hierarchy.atoms()
    new_occ = flex.double(atoms.size(), 1.0)
    atoms.set_occ(new_occ)


def molecular_weight(pdbin, first=False):
    """Determine the molecular weight of a pdb
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    first : bool
       Consider the first chain in the first model only [default: False]

    Returns
    -------
    float
       The molecular weight of the extracted atoms

    Notes
    -----
    This function ignores water molecules.
    
    """
    _, _, mw = _natm_nres_mw(pdbin, first)
    return mw


def num_atoms_and_residues(pdbin, first=False):
    """Determine the number of atoms and residues in a pdb file.
    
    If all is True, return all atoms and residues, else just for the first chain in the first model

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    first : bool
       Consider the first chain in the first model only [default: False]

    Returns
    -------
    int
       The number of atoms
    int
       The number of residues

    """
    natoms, nresidues, _ = _natm_nres_mw(pdbin, first)
    assert natoms > 0 and nresidues > 0
    return natoms, nresidues


def _natm_nres_mw(pdbin, first=False):
    """Function to extract the number of atoms, number of residues and molecular weight
    from a PDB structure
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    hierarchy = pdb_input.construct_hierarchy()

    # Define storage variables
    elements, residues = [], []
    hydrogen_atoms, other_atoms = 0, 0
    water_atoms, water_hydrogen_atoms = 0, 0
    mw = 0
    
    # Pick chain
    if first:
        _first_chain_only(hierarchy)
    
    # Collect all the data using the hierarchy
    for m in hierarchy.models():
        for c in m.chains():
            for rg in c.residue_groups():
                resseq = None
                for ag in rg.atom_groups():
                    if ag.resname in three2one and resseq != rg.resseq:
                        residues.append(ag.resname)
                        resseq = rg.resseq
                        hydrogen_atoms += chemistry.atomic_composition[ag.resname].H
                    for atom in ag.atoms():
                        if ag.resname.strip() == 'HOH' or ag.resname.strip() == 'WAT':
                            water_hydrogen_atoms += (2.0 * atom.occ)
                            water_atoms += (1.0 * atom.occ)
                        else:
                            elements.append((atom.element.strip(), atom.occ))

    # Compute the molecular weight with respect to the occupancy
    for element, occ in elements:
        other_atoms += occ
        mw += chemistry.periodic_table(element).weight() * occ
    mw += hydrogen_atoms * chemistry.periodic_table('H').weight() 
    
    # Compute the number of atoms and number of residues
    natoms = int(other_atoms + hydrogen_atoms + water_atoms + water_hydrogen_atoms - 0.5)
    nresidues = len(residues)

    return natoms, nresidues, mw


def _parse_modres(modres_text):
    """
COLUMNS        DATA TYPE     FIELD       DEFINITION
--------------------------------------------------------------------------------
 1 -  6        Record name   "MODRES"
 8 - 11        IDcode        idCode      ID code of this entry.
13 - 15        Residue name  resName     Residue name used in this entry.
17             Character     chainID     Chain identifier.
19 - 22        Integer       seqNum      Sequence number.
23             AChar         iCode       Insertion code.
25 - 27        Residue name  stdRes      Standard residue name.
30 - 70        String        comment     Description of the residue modification.
"""

    modres = []
    for line in modres_text:
        assert line[0:6] == "MODRES", "Line did not begin with an MODRES record!: {0}".format(line)

        idCode = line[7:11]
        resName = line[12:15].strip()
        # Use for all so None means an empty field
        if line[16].strip(): chainID = line[16]
        seqNum = int(line[18:22])
        iCode = ""
        if line[22].strip(): iCode = line[22]
        stdRes = line[24:27].strip()
        comment = ""
        if line[29:70].strip(): comment = line[29:70].strip()

        modres.append([idCode, resName, chainID, seqNum, iCode, stdRes, comment])

    return modres


def prepare_nmr_model(nmr_model_in, models_dir):
    """Split an nmr pdb into its constituent parts and standardise the lengths"""
    if not os.path.isdir(models_dir): os.mkdir(models_dir)
    split_pdbs = split_pdb(nmr_model_in, models_dir)

    # We can only work with equally sized PDBS so we pick the most numerous if there are different sizes
    lengths = {}
    lmax = 0
    for pdb in split_pdbs:
        h = iotbx.pdb.pdb_input(pdb).construct_hierarchy()
        l = h.models()[0].chains()[0].residue_groups_size()
        if l not in lengths:
            lengths[l] = [pdb]
        else:
            lengths[l].append(pdb)
        lmax = max(lmax, l)

    if len(lengths) > 1:
        # The pdbs were of different lengths
        to_keep = lengths[lmax]
        logger.info('All NMR models were not of the same length, only %d will be kept.', len(to_keep))
        # Delete any that are not of most numerous length
        for p in [p for p in split_pdbs if p not in to_keep]: os.unlink(p)
        split_pdbs = to_keep

    return split_pdbs


def reliable_sidechains(pdbin, pdbout):
    """Only output non-backbone atoms for certain residues
    
    This function strips side chain atoms of residues not defined in the
    following list:
       ['MET', 'ASP', 'PRO', 'GLN', 'LYS', 'ARG', 'GLU', 'SER']

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    
    # Remove sidechains that are in res_names where the atom name is not in atom_names
    res_names = ['MET', 'ASP', 'PRO', 'GLN', 'LYS', 'ARG', 'GLU', 'SER']
    atom_names = ['N', 'CA', 'C', 'O', 'CB']
    select_string = "({residues}) or not ({residues}) and ({atoms})".format(
        atoms=" or ".join(['name %s' % atm.lower() for atm in atom_names]),
        residues=" or ".join(['resname %s' % res.upper() for res in res_names]),
    )
    hierarchy_new = _select(hierarchy, select_string)
    
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy_new.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def rename_chains(pdbin=None, pdbout=None, fromChain=None, toChain=None):
    """Rename Chains"""

    assert len(fromChain) == len(toChain)

    counter = 0
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    for model in hierarchy.models():
        if toChain:
            for chain in model.chains():
                if counter < len(fromChain):
                    if fromChain[0 + counter] == chain.id:
                        chain.id = toChain[0 + counter]
                        counter += 1

    with open(pdbout, 'w') as f:
        f.write("REMARK Original file:" + os.linesep)
        f.write("REMARK   {0}".format(pdbin) + os.linesep)
        if crystal_symmetry is not None:
            f.write(iotbx.pdb.format_cryst1_and_scale_records(crystal_symmetry=crystal_symmetry,
                                                              write_scale_records=True) + os.linesep)
        f.write(hierarchy.as_pdb_string(anisou=False))


def remove_unwanted(hierarchy, residue_list):
    """Remove any residues from the a hierarchy that can't be compared to a
    list of residues"""

    if len(residue_list) != 0:
        # Remove residue groups that are in the NoNative list
        for model in hierarchy.models():
            for chain in model.chains():
                for rg in chain.residue_groups():
                    if rg.resseq_as_int() in residue_list:
                        chain.remove_residue_group(rg)

    return hierarchy


def resseq(pdbin):
    return _resseq(iotbx.pdb.pdb_input(pdbin).construct_hierarchy())


def _resseq(hierarchy):
    """Extract the sequence of residues from a pdb file."""
    chain2data = _sequence_data(hierarchy)
    return dict((k, chain2data[k][1]) for k in chain2data.keys())


def renumber_residues(pdbin, pdbout, start=1):
    """ Renumber the residues in the chain """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    _renumber(hierarchy, start)

    with open(pdbout, 'w') as f:
        f.write("REMARK Original file:" + os.linesep)
        f.write("REMARK   {0}".format(pdbin) + os.linesep)
        if crystal_symmetry is not None:
            f.write(iotbx.pdb.format_cryst1_and_scale_records(crystal_symmetry=crystal_symmetry,
                                                              write_scale_records=True) + os.linesep)
        f.write(hierarchy.as_pdb_string(anisou=False))
    return


def _renumber(hierarchy, start):
    # Renumber the residue sequence
    for model in hierarchy.models():
        for chain in model.chains():
            for idx, residue_group in enumerate(chain.residue_groups()):
                residue_group.resseq = idx + start
    return


def renumber_residues_gaps(pdbin, pdbout, gaps, start=1):
    """
    Renumber the residues in the chain based on specified gaps

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    gaps : list
        List containing True/False for gaps

    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    for model in hierarchy.models():
        for chain in model.chains():
            resseq = 0
            for idx, is_gap in enumerate(gaps):
                if is_gap:
                    continue
                residue_group = chain.residue_groups()[resseq]
                residue_group.resseq = idx + start
                resseq += 1
    
    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def rog_side_chain_treatment(pdbin=None, pdbout=None, rog_data=None, del_orange=False):
    """Takes the ROG score from the input file and uses this to remove side chains
    from the corresponding pdb file"""

    resSeq_data = extract_resSeq(pdbin)

    # Match the ROG data to the resSeq data
    scores = zip(resSeq_data, rog_data)

    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    _rog_side_chain_treatment(hierarchy, scores, del_orange)

    # Finally, write to pdbout
    with open(pdbout, 'w') as f:
        f.write("REMARK Original file:" + os.linesep)
        f.write("REMARK   {0}".format(pdbin) + os.linesep)
        if (crystal_symmetry is not None):
            f.write(iotbx.pdb.format_cryst1_and_scale_records(crystal_symmetry=crystal_symmetry,
                                                              write_scale_records=True) + os.linesep)
        f.write(hierarchy.as_pdb_string(anisou=False))
    return


def _rog_side_chain_treatment(hierarchy, scores, del_orange):
    def _remove(rg):
        atom_names = ['N', 'CA', 'C', 'O', 'CB']
        for ag in rg.atom_groups():
            for atom in ag.atoms():
                if (atom.name.strip() not in atom_names):
                    ag.remove_atom(atom=atom)

    for model in hierarchy.models():
        for chain in model.chains():
            for rg in chain.residue_groups():
                if not del_orange:
                    # Remove just the red scoring side chains
                    res = rg.resseq_as_int()
                    for i, j in scores:
                        if i == res and j == 'red':
                            _remove(rg)
                else:
                    # Only keep the green scoring side chains
                    res = rg.resseq_as_int()
                    for i, j in scores:
                        if i == res and j != 'green':
                            _remove(rg)


def select_residues(pdbin, pdbout, delete=None, tokeep=None, delete_idx=None, tokeep_idx=None):
    """Select specified residues in a given PDB structure

    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    delete : list, tuple, optional
       A list of residues to delete
    tokeep : list, tuple, optional
       A list of residues to keep

    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    if len(hierarchy.models()) > 1 or len(hierarchy.models()[0].chains()) > 1:
        print("pdb {0} has > 1 model or chain - only first model/chain will be kept".format(pdbin))
        _first_chain_only(hierarchy)
    
    chain = hierarchy.models()[0].chains()[0]

    idx = -1
    for residue_group in chain.residue_groups():
        # We ignore hetatms when indexing as we are concerned with residue indexes
        if delete_idx or tokeep_idx:
            if any([atom.hetero for atom in residue_group.atoms()]):
                continue
        idx += 1

        if delete and residue_group.resseq_as_int() not in delete:
            continue
        elif delete_idx and idx not in delete:
            continue
        elif tokeep and residue_group.resseq_as_int() in tokeep: 
            continue
        elif tokeep_idx and idx in tokeep_idx:
            continue
        
        chain.remove_residue_group(residue_group)

    with open(pdbout, 'w') as f:
        f.write("REMARK Original file:" + os.linesep)
        f.write("REMARK   {0}".format(pdbin) + os.linesep)
        f.write(hierarchy.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def sequence(pdbin):
    return _sequence(iotbx.pdb.pdb_input(pdbin).construct_hierarchy())


def _sequence(hierarchy):
    """Extract the sequence of residues from a pdb file."""
    chain2data = _sequence_data(hierarchy)
    return dict((k, chain2data[k][0]) for k in chain2data.keys())


def _sequence1(hierarchy):
    """Return sequence of the first chain"""
    d = _sequence(hierarchy)
    return d[sorted(d.keys())[0]]


def sequence_data(pdbin):
    return _sequence_data(iotbx.pdb.pdb_input(pdbin).construct_hierarchy())


def _sequence_data(hierarchy):
    """Extract the sequence of residues and resseqs from a pdb file."""
    chain2data = {}
    for chain in set(hierarchy.models()[0].chains()):  # only the first model
        if not chain.is_protein(): continue
        got = False
        seq = ""
        resseq = []
        for residue in chain.conformers()[0].residues():  # Just look at the first conformer
            # See if any of the atoms are non-hetero - if so we add this residue
            if any([not atom.hetero for atom in residue.atoms()]):
                got = True
                seq += three2one[residue.resname]
                # resseq.append(int(residue.resseq.strip()))
                resseq.append(residue.resseq_as_int())
        if got: chain2data[chain.id] = (seq, resseq)
    return chain2data


def split_pdb(pdbin, directory=None):
    """Split a pdb file into its separate models
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    directory : str, optional
       A path to a directory to store models in

    Returns
    -------
    list
       The list of split pdb models
    
    Raises
    ------
    RuntimeError
       split_into_chains only works with single-model pdbs

    '"""

    if directory is None: 
        directory = os.path.dirname(pdbin)

    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    # Nothing to do
    n_models = hierarchy.models_size()
    if n_models == 1:
        raise RuntimeError("split_pdb {0} only contained 1 model!".format(pdbin))

    output_files = []
    for k, model in enumerate(hierarchy.models()):
        k += 1
        hierarchy_new = iotbx.pdb.hierarchy.root()
        hierarchy_new.append_model(model.detached_copy())
        if model.id == "":
            model_id = str(k)
        else:
            model_id = model.id.strip()

        output_file = ample_util.filename_append(pdbin, model_id, directory)
        with open(output_file, 'w') as f_out:
            f_out.write("REMARK Model %d of %d" % (k, n_models) + os.linesep)
            f_out.write("REMARK Original file:" + os.linesep)
            f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
            f_out.write(hierarchy_new.as_pdb_string(
                anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
            ))
        output_files.append(output_file)

    return output_files


def split_into_chains(pdbin, chain=None, directory=None):
    """Split a pdb file into its separate chains
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    chain : str, optional
       Specify a single chain to extract 
    directory : str, optional
       A path to a directory to store models in

    Returns
    -------
    list
       The list of split pdb models
    
    Raises
    ------
    RuntimeError
       split_into_chains only works with single-model pdbs

    '"""

    if directory is None: 
        directory = os.path.dirname(pdbin)

    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()
    
    # Nothing to do
    n_models = hierarchy.models_size()
    if n_models != 1: 
        raise RuntimeError("split_into_chains only works with single-model pdbs!")

    output_files = []
    for i, hchain in enumerate(hierarchy.models()[0].chains()):
        if not hchain.is_protein():
            continue
        if chain and not hchain.id == chain: 
            continue
        hierarchy_new = iotbx.pdb.hierarchy.root()
        model_new = iotbx.pdb.hierarchy.model()
        hierarchy_new.append_model((model_new))
        model_new.append_chain(hchain.detached_copy())

        output_file = ample_util.filename_append(pdbin, hchain.id, directory)
        with open(output_file, 'w') as f_out:
            f_out.write("REMARK Original file:" + os.linesep)
            f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
            f_out.write("REMARK Chain {0}".format(hchain.id) + os.linesep)
            f_out.write(hierarchy_new.as_pdb_string(
                anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
            ))
        output_files.append(output_file)

    if not len(output_files): 
        raise RuntimeError("split_into_chains could not find any chains to split")

    return output_files


def standardise(pdbin, pdbout, chain=None, del_hetatm=False):
    """Rename any non-standard AA, remove solvent and only keep most probable conformation."""

    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    hierarchy = pdb_input.construct_hierarchy()

    # Remove solvents defined below
    solvents = {'ADE', 'CYT', 'GUA', 'INO', 'THY', 'URA', 'WAT', 'HOH', 'TIP', 'H2O', 'DOD', 'MOH'}
    for model in hierarchy.models():
        for c in model.chains():
            for rg in c.residue_groups():
                if rg.unique_resnames()[0] in solvents:
                    c.remove_residue_group(rg)

    # Keep the most probably conformer
    most_prob(hierarchy)

    # Extract one of the chains
    if chain:
        for model in hierarchy.models():
            for c in model.chains():
                if c.id != chain:
                    model.remove_chain(c)

    f = tempfile.NamedTemporaryFile("w", delete=False)
    f.write(hierarchy.as_pdb_string(anisou=False))
    f.close()

    # Standardise AA names and then remove any remaining HETATMS
    std_residues(f.name, pdbout, del_hetatm=del_hetatm)

    return


def std_residues(pdbin, pdbout, del_hetatm=False):
    """Map all residues in MODRES section to their standard counterparts
    optionally delete all other HETATMS"""

    pdb_input = iotbx.pdb.pdb_input(pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()

    # Get MODRES Section & build up dict mapping the changes
    modres_text = [l.strip() for l in pdb_input.primary_structure_section()
                   if l.startswith("MODRES")]
    modres = {}
    for id, resname, chain, resseq, icode, stdres, comment in _parse_modres(modres_text):
        if not chain in modres:
            modres[chain] = {}
            modres[chain][int(resseq)] = (resname, stdres)

    hierarchy = pdb_input.construct_hierarchy()
    for model in hierarchy.models():
        for chain in model.chains():
            for residue_group in chain.residue_groups():
                resseq = residue_group.resseq_as_int()
                for atom_group in residue_group.atom_groups():
                    resname = atom_group.resname
                    if chain.id in modres and resseq in modres[chain.id] and modres[chain.id][resseq][0] == resname:
                        # Change modified name to std name
                        # assert modres[chain.id][resseq][0]==resname,\
                        # "Unmatched names: {0} : {1}".format(modres[chain.id][resseq][0],resname)
                        atom_group.resname = modres[chain.id][resseq][1]
                        # If any of the atoms are hetatms, set them to be atoms
                        for atom in atom_group.atoms():
                            if atom.hetero: atom.hetero = False

    if del_hetatm: _strip(hierarchy, hetatm=True)

    with open(pdbout, 'w') as f:
        f.write("REMARK Original file:" + os.linesep)
        f.write("REMARK   {0}".format(pdbin) + os.linesep)
        if crystal_symmetry is not None:
            f.write(iotbx.pdb.format_cryst1_and_scale_records(crystal_symmetry=crystal_symmetry,
                                                              write_scale_records=True) + os.linesep)
        f.write(hierarchy.as_pdb_string(anisou=False))
    return


def strip(pdbin, pdbout, hetatm=False, hydrogen=False, atom_types=[]):
    """Remove atom types from a structure file
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
       
    Raises
    ------
    ValueError
       Define which atoms to strip
    
    """
    if not (hetatm or hydrogen or atom_types):
        msg = "Define which atoms to strip"
        raise ValueError(msg)

    pdb_input = iotbx.pdb.pdb_input(pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    _strip(hierarchy, hetatm=hetatm, hydrogen=hydrogen, atom_types=atom_types)

    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


def _strip(hierachy, hetatm=False, hydrogen=False, atom_types=[]):
    """Remove all hetatoms from pdbfile"""
    def remove_atom(atom, hetatm=False, hydrogen=False, atom_types=[]):
        return (hetatm and atom.hetero) or (hydrogen and atom.element_is_hydrogen()) or atom.name.strip() in atom_types

    for model in hierachy.models():
        for chain in model.chains():
            for residue_group in chain.residue_groups():
                for atom_group in residue_group.atom_groups():
                    to_del = [a for a in atom_group.atoms() if
                              remove_atom(a, hetatm=hetatm, hydrogen=hydrogen, atom_types=atom_types)]
                    for atom in to_del:
                        atom_group.remove_atom(atom)
    return


def to_single_chain(inpath, outpath):
    """Condense a single-model multi-chain pdb to a single-chain pdb"""

    o = open(outpath, 'w')

    firstChainID = None
    currentResSeq = None  # current residue we are reading - assume it always starts from 1
    globalResSeq = None
    globalSerial = -1
    for line in open(inpath):

        # Remove any HETATOM lines and following ANISOU lines
        if line.startswith("HETATM") or line.startswith("MODEL") or line.startswith("ANISOU"):
            raise RuntimeError("Cant cope with the line: {0}".format(line))

        # Skip any TER lines
        if line.startswith("TER"):
            continue

        if line.startswith("ATOM"):
            changed = False

            atom = pdb_model.PdbAtom(line)

            # First atom/residue
            if globalSerial == -1:
                globalSerial = atom.serial
                firstChainID = atom.chainID
                globalResSeq = atom.resSeq
                currentResSeq = atom.resSeq
            else:
                # Change residue numbering and chainID
                if atom.chainID != firstChainID:
                    atom.chainID = firstChainID
                    changed = True

                # Catch each change in residue
                if atom.resSeq != currentResSeq:
                    # Change of residue
                    currentResSeq = atom.resSeq
                    globalResSeq += 1

                # Only change if don't match global
                if atom.resSeq != globalResSeq:
                    atom.resSeq = globalResSeq
                    changed = True

                # Catch each change in numbering
                if atom.serial != globalSerial + 1:
                    atom.serial = globalSerial + 1
                    changed = True

                if changed:
                    line = atom.toLine() + os.linesep

                # Increment counter for all atoms
                globalSerial += 1

        o.write(line)

    o.close()


def translate(pdbin, pdbout, ftranslate):
    """Translate all atoms in a structure file by the provided vector
    
    Parameters
    ----------
    pdbin : str
       The path to the input PDB
    pdbout : str
       The path to the output PDB
    ftranslate : list, tuple
       The vector of fractional coordinates to shift by
    
    """
    pdb_input = iotbx.pdb.pdb_input(file_name=pdbin)
    crystal_symmetry = pdb_input.crystal_symmetry()
    hierarchy = pdb_input.construct_hierarchy()

    # Obtain information about the fractional coordinates
    crystal_info = get_info(pdbin).crystalInfo

    ftranslate = np.asarray([crystal_info.a, crystal_info.b, crystal_info.c]) * np.asarray(ftranslate)
    for atom in hierarchy.atoms():
        atom.set_xyz(np.asarray(atom.xyz) + ftranslate)

    with open(pdbout, 'w') as f_out:
        f_out.write("REMARK Original file:" + os.linesep)
        f_out.write("REMARK   {0}".format(pdbin) + os.linesep)
        f_out.write(hierarchy.as_pdb_string(
            anisou=False, write_scale_records=True, crystal_symmetry=crystal_symmetry
        ))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Manipulate PDB files', prefix_chars="-")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-ren', action='store_true',
                       help="Renumber the PDB")
    group.add_argument('-std', action='store_true',
                       help='Standardise the PDB')
    group.add_argument('-seq', action='store_true',
                       help='Write a fasta of the found AA to stdout')
    group.add_argument('-split_models', action='store_true',
                       help='Split a pdb into constituent models')
    group.add_argument('-split_chains', action='store_true',
                       help='Split a pdb into constituent chains')
    parser.add_argument('input_file',  # nargs='?',
                        help='The input file - will not be altered')
    parser.add_argument('-o', dest='output_file',
                        help='The output file - will be created')
    parser.add_argument('-chain', help='The chain to use')

    args = parser.parse_args()

    # Get full paths to all files
    args.input_file = os.path.abspath(args.input_file)
    if not os.path.isfile(args.input_file):
        raise RuntimeError("Cannot find input file: {0}".format(args.input_file))

    if args.output_file:
        args.output_file = os.path.abspath(args.output_file)
    else:
        n = os.path.splitext(os.path.basename(args.input_file))[0]
        args.output_file = n + "_std.pdb"

    if args.ren:
        renumber_residues(args.input_file, args.output_file, start=1)
    elif args.std:
        standardise(args.input_file, args.output_file, del_hetatm=True, chain=args.chain)
    elif args.seq:
        print(sequence_util.Sequence(pdb=args.input_file).fasta_str())
    elif args.split_models:
        print(split_pdb(args.input_file))
    elif args.split_chains:
        print(split_into_chains(args.input_file, chain=args.chain))

