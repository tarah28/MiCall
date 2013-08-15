"""
Distribute pipeline processes across the cluster.
"""

import sys
import os
from glob import glob
from mpi4py import MPI
from seqUtils import convert_fasta
from datetime import datetime

# This process now has awareness of it's process rank
my_rank = MPI.COMM_WORLD.Get_rank()
nprocs = MPI.COMM_WORLD.Get_size()

def timestamp(msg):
	print '[%s] (%d/%d) %s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
			my_rank,
			nprocs,
			msg)


refpath = '/usr/local/share/miseq/refs/cfe'

# Iteratively map sequences in fastQ to reference sequences
root = sys.argv[1]	# Path to the folder containing fastq files
mode = sys.argv[2] 	# Nextera or Amplicon
files = glob(root + '/*R1*.fastq')

# For each file in the list of files 
for i in range(len(files)):

	# Break files up into k buckets - the k-th file bucket will be processed by the k-th process
	if i % nprocs != my_rank:
		continue

	filename = files[i].split('/')[-1]
	timestamp('1_mapping %s' % filename)

	# Map the sequences in this sample to our reference sequences
	os.system('python 1_mapping.py %s %s' % (refpath, files[i]))

# MPI.COMM_WORLD.Barrier() won't allow this code to proceed until all sister processes report to the controller
# that they have reached this point. Otherwise, not all processes will have the same filepath list with
# the subsequent glob, and the rank assignment approach to the division of labor will fail.
MPI.COMM_WORLD.Barrier()

# Create a list of remapped SAM files
files = glob(root + '/*.remap.sam')

for i in range(len(files)):

	# Distribute them evenly to different processes
	if i % nprocs != my_rank:
		continue

	filename = files[i].split('/')[-1]
	timestamp('2_sam2fasta %s' % filename)

	# For each q-cutoff, generate a fasta file
	for qcut in [0, 10, 15, 20]:
		os.system('python 2_sam2fasta_with_base_censoring.py %s %d %s' % (files[i], qcut, mode))


# Fpr amplicon sequencing runs, compute g2p scores for env-mapped FASTAs
if mode == 'Amplicon':
	files = glob(root + '/*env*.fasta')

	for i, file in enumerate(files):

		# Distribute g2p scoring amongst each process
		if i % nprocs != my_rank:
			continue

		filename = files[i].split('/')[-1]
		timestamp('3_g2p_scoring %s' % filename)

		# Generate v3prot and badV3 files from env-specific fasta
		os.system('python 3_g2p_scoring.py %s' % file)



# Generate amino acid count CSVs
files = glob(root + '/*.fasta' if mode == 'Amplicon' else 'csf')

for i, file in enumerate(files):

	if i % nprocs != my_rank:
		continue

	filename = files[i].split('/')[-1]
	timestamp('5_amino_freqs %s' % filename)
	os.system('python 5_amino_freqs.py %s %s' % (file, mode))

# Wait for all threads to complete
MPI.COMM_WORLD.Barrier()
MPI.Finalize()


def prop_x4 (handle, cutoff, min_count):
	total_count = 0
	total_x4_count = 0

	for h, s in fasta:
		# >F00309-IL_variant_0_count_27_fpr_4.0
		tokens = h.split('_')
		try:
			variant = int(tokens[tokens.index('variant')+1])
			count = int(tokens[tokens.index('count')+1])
			fpr = float(tokens[tokens.index('fpr')+1])
		except:
			#print 'ERROR, missing variant, count or fpr in header'
			#print h, s
			continue

		if count <= min_count:
			continue

		total_count += count
		if fpr < cutoff:
			total_x4_count += count

	return (total_x4_count, total_count)


# Create summary _g2p.csv stats file in serial (non-parallel) mode
if my_rank == 0:
	outfile = open(root+'/_g2p.csv', 'w')
	outfile.write('sample,q.cut,fpr.cut,min.count,x4.count,total.count,prop.x4\n')

	# Get files generated by 3_g2p_scoring.py
	files = glob(root + '/*.v3prot')
	for file in files:
		filename = file.split('/')[-1]
		sample, region, qcut = filename.split('.')[:3]
		qcut = int(qcut)
		for mincount in [0, 1, 3, 50]:
			for cutoff in [3.0, 3.5, 4.0, 5.0, 5.75, 7.5]:
				infile = open(file, 'rU')
				lines = infile.readlines()
				fasta = convert_fasta(lines) if len(lines) > 0 else []
				infile.close()
				
				if len(fasta) > 0:
					x4_count, total_count = prop_x4(infile, cutoff, mincount)
				else:
					x4_count = 0
					total_count = 0
				
				outfile.write('%s,%d,%f,%d,%d,%d,%s\n' % (sample, qcut, cutoff, 
					mincount, x4_count, total_count, 
					str(x4_count/float(total_count)) if total_count > 0 else 'NA'))

	outfile.close()
