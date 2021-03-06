
import os

from ample.util import ample_util
from ample.ensembler._ensembler import Cluster

class FPC(object):
    """
    Class 
    """

    def __init__(self):
        pass

    def cluster(self,
                models=None,
                num_clusters=None,
                nproc=1,
                score_type="rmsd",
                cluster_method="kmeans",
                work_dir=None,
                fpc_exe=None,
                max_cluster_size=200,
                benchmark=False
                ):
        
        # FPC default if 5 clusters - we just run with this for the time being
        FPC_NUM_CLUSTERS=5
        if num_clusters is None or num_clusters > FPC_NUM_CLUSTERS:
            msg = "Cannot work with more than {0} clusters, got: {1}.".format(FPC_NUM_CLUSTERS,num_clusters)
            raise RuntimeError(msg)
  
        owd=os.getcwd()
        if not os.path.isdir(work_dir): os.mkdir(work_dir)
        os.chdir(work_dir)
        
        if not len(models) or not all([os.path.isfile(m) for m in models]):
            msg = "Missing models: {0}".format(models)
            raise RuntimeError(msg)
        
        # Create list of files
        flist='files.list'
        with open(flist,'w') as f:
            for m in models:
                f.write("{0}\n".format(os.path.abspath(m)))
        
        if not os.path.isfile(fpc_exe):
            msg = "Cannot find fast_protein_cluster executable: {0}".format(fpc_exe)
            raise RuntimeError(msg)
        
        # Build up the command-line
        cmd=[fpc_exe]
        if score_type=="rmsd":
            cmd += ['--rmsd']
        elif score_type=="tm":
            cmd += ['--tmscore']
        else:
            msg = "Unrecognised score_type: {0}".format(score_type)
            raise RuntimeError(msg)
        
        if cluster_method=="kmeans":
            cmd += ['--cluster_kmeans']
        elif cluster_method=="hcomplete":
            cmd += ['--cluster_hcomplete']
        else:
            msg = "Unrecognised cluster_method: {0}".format(cluster_method)
            raise RuntimeError(msg)
        
        if nproc > 1: cmd += ['--nthreads',str(nproc)]
        
        # Always save the distance matrix
        cmd += ['--write_text_matrix','matrix.txt']
        
        # For benchmark we use a constant seed to make sure we get the same results
        if benchmark: cmd += ['-S','1']
        
        # Finally the list of files
        cmd += ['-i',flist]
        
        logfile=os.path.abspath("fast_protein_cluster.log")
        retcode = ample_util.run_command(cmd,logfile=logfile)
        if retcode != 0:
            msg = "non-zero return code for fast_protein_cluster in cluster!\nCheck logfile:{0}".format(logfile)
            raise RuntimeError(msg)
    
        cluster_list='cluster_output.clusters'
        cluster_stats='cluster_output.cluster.stats'
        if not os.path.isfile(cluster_list) or not os.path.isfile(cluster_stats):
            msg = "Cannot find files: {0} and {1}".format(cluster_list,cluster_stats)
            raise RuntimeError(msg)
        
        # Check stats and get centroids
        csizes=[]
        centroids=[]
        with open(cluster_stats) as f:
            for line in f:
                if line.startswith("Cluster:"):
                    fields=line.split()
                    csizes.append(int(fields[4]))
                    centroids.append(fields[7])
        
        if len(csizes) != FPC_NUM_CLUSTERS:
            msg = "Found {0} clusters in {1} but was expecting {2}".format(len(csizes),cluster_stats,FPC_NUM_CLUSTERS)
            raise RuntimeError(msg)
        
        all_clusters=[[] for i in range(FPC_NUM_CLUSTERS)]
        # Read in the clusters
        with open(cluster_list) as f:
            for line in f:
                fields=line.split()
                model=fields[0]
                idxCluster=int(fields[1])
                all_clusters[idxCluster].append(model)
        
        # Check
        if False:
            # Ignore this test for now as there seems to be a bug in fast_protein_cluster with the printing of sizes
            maxc=None
            for i,cs in enumerate(csizes):
                if not cs == len(all_clusters[i]):
                    msg = "Cluster {0} size {1} does not match stats size {2}".format(i,len(all_clusters[i]),cs)
                    raise RuntimeError(msg)
                if i==0:
                    maxc=cs
                else:
                    if cs > maxc:
                        msg = "Clusters do not appear to be in size order!"
                        raise RuntimeError(msg)
                    
        # make sure all clusters are < max_cluster_size
        for i, c in enumerate(all_clusters):
            if len(c) > max_cluster_size:
                all_clusters[i]=c[:max_cluster_size]
        
        # Create the data - we loop through the number of clusters specified by the user
        clusters=[]
        for i in range(num_clusters):
            cluster = Cluster()
            cluster.method = cluster_method
            cluster.score_type = score_type
            cluster.index = i + 1
            cluster.centroid = centroids[i]
            cluster.num_clusters = num_clusters
            cluster.models = all_clusters[i]
        os.chdir(owd)
        return clusters
