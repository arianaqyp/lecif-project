#!/usr/bin/env python3
'''
This script counts the total number of regions in a region file and sets up
processing commands for generateDataThreaded.py to handle all chunks efficiently.

It either:
1. Generates a shell script with commands to process all chunks, or
2. If requested, submits jobs directly using a job array system

This helps automate step 2.4 in the LECIF README.md where feature data needs to be
aggregated for all genomic regions, 1 million regions per chunk.
'''

import argparse
import gzip
import os
import subprocess
import sys
import math
from pathlib import Path

def count_regions(region_filename):
    """Count the total number of regions in the gzipped region file."""
    count = 0
    with gzip.open(region_filename, 'rt') as f:
        for _ in f:
            count += 1
    return count

def create_output_dir(output_dir):
    """Create output directory if it doesn't exist."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

def generate_commands(args, num_regions, num_chunks):
    """Generate commands for processing all chunks."""
    commands = []
    
    for i in range(1, num_chunks + 1):
        cmd = [
            f"python source/generateDataThreaded.py",
            f"-p {args.region_filename}",
            f"-ca {args.cage_dir}",
            f"-ch {args.chromhmm_dir}",
            f"-dn {args.dnase_chipseq_dir}",
            f"-rn {args.rnaseq_dir}",
            f"-chn {args.chromhmm_num_states}",
            f"-can {args.cage_num_experiments}",
            f"-fn {args.num_features}",
            f"-o {args.output_dir}/all_{i}.gz",
            "-s",
            f"-c {args.chunk_size}",
            f"-i {i}"
        ]
        commands.append(" ".join(cmd))
    
    return commands

def create_shell_script(commands, output_script):
    """Create a shell script with all the commands."""
    with open(output_script, 'w') as f:
        f.write("#!/bin/bash\n\n")
        for i, cmd in enumerate(commands):
            f.write(f"# Process chunk {i+1}\n")
            f.write(f"{cmd}\n\n")
    
    # Make the script executable
    os.chmod(output_script, 0o755)
    print(f"Created shell script: {output_script}")

def create_job_array_script(commands, output_script, job_array_type):
    """Create a job array script based on the specified type (SLURM/SGE/LSF)."""
    with open(output_script, 'w') as f:
        if job_array_type.lower() == "slurm":
            f.write("#!/bin/bash\n")
            f.write(f"#SBATCH --array=1-{len(commands)}\n")
            f.write("#SBATCH --job-name=LECIF_feature_agg\n")
            f.write("#SBATCH --output=job_logs/LECIF_feature_agg_%A_%a.out\n")
            f.write("#SBATCH --error=job_logs/LECIF_feature_agg_%A_%a.err\n")
            f.write("#SBATCH --time=12:00:00\n")
            f.write("#SBATCH --mem=16G\n")
            f.write("\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands):
                f.write(f"commands[{i+1}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$SLURM_ARRAY_TASK_ID]}\n")
        
        elif job_array_type.lower() == "sge":
            f.write("#!/bin/bash\n")
            f.write(f"#$ -t 1-{len(commands)}\n")
            f.write("#$ -N LECIF_feature_agg\n")
            f.write("#$ -o job_logs/LECIF_feature_agg_$JOB_ID_$TASK_ID.out\n")
            f.write("#$ -e job_logs/LECIF_feature_agg_$JOB_ID_$TASK_ID.err\n")
            f.write("#$ -l h_rt=12:00:00\n")
            f.write("#$ -l h_vmem=16G\n")
            f.write("\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands):
                f.write(f"commands[{i+1}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$SGE_TASK_ID]}\n")
        
        elif job_array_type.lower() == "lsf":
            f.write("#!/bin/bash\n")
            f.write(f"#BSUB -J LECIF_feature_agg[1-{len(commands)}]\n")
            f.write("#BSUB -o job_logs/LECIF_feature_agg_%J_%I.out\n")
            f.write("#BSUB -e job_logs/LECIF_feature_agg_%J_%I.err\n")
            f.write("#BSUB -W 12:00\n")
            f.write("#BSUB -M 16G\n")
            f.write("\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands):
                f.write(f"commands[{i+1}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$LSB_JOBINDEX]}\n")
        
        else:
            print(f"Unsupported job array type: {job_array_type}")
            sys.exit(1)
    
    # Make the script executable
    os.chmod(output_script, 0o755)
    print(f"Created job array script for {job_array_type}: {output_script}")

def generate_combine_script(args, num_chunks):
    """Generate a script to combine all output chunks."""
    combine_script = os.path.join(args.output_dir, "combine_chunks.sh")
    with open(combine_script, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Script to combine all processed chunks into a single file\n\n")
        
        # Species identifier (h or m) from the region filename
        species_id = "h" if ".h.gz" in args.region_filename else "m"
        
        # Create the command to combine files
        combine_cmd = f"cat {args.output_dir}/all_*.gz > {args.output_dir}/all.{species_id}.gz"
        f.write(f"echo \"Combining {num_chunks} chunks into a single file...\"\n")
        f.write(f"{combine_cmd}\n")
        f.write("echo \"Combination complete.\"\n")
    
    # Make the script executable
    os.chmod(combine_script, 0o755)
    print(f"Created combine script: {combine_script}")

def main():
    # Parse command line arguments
    description = 'Count regions and set up processing commands for generateDataThreaded.py'
    parser = argparse.ArgumentParser(description=description)
    
    parser.add_argument('-p', '--region-filename', required=True,
                        help='Path to species-specific region file (.h.gz or .m.gz) from samplePairs.py')
    parser.add_argument('-ca', '--cage-dir', required=True,
                        help='Path to directory with output files from runIntersect for CAGE')
    parser.add_argument('-ch', '--chromhmm-dir', required=True,
                        help='Path to directory with output files from runIntersect for ChromHMM')
    parser.add_argument('-dn', '--dnase-chipseq-dir', required=True,
                        help='Path to directory with output files from runIntersect for DNase-seq and ChIP-seq')
    parser.add_argument('-rn', '--rnaseq-dir', required=True,
                        help='Path to directory with output files from runIntersect for RNA-seq')
    parser.add_argument('-chn', '--chromhmm-num-states', type=int, required=True,
                        help='Number of ChromHMM chromatin states (25 for human, 15 for mouse)')
    parser.add_argument('-can', '--cage-num-experiments', type=int, required=True,
                        help='Number of CAGE experiments (1829 for human, 1073 for mouse)')
    parser.add_argument('-fn', '--num-features', type=int, required=True,
                        help='Total number of features (8824 for human, 3313 for mouse)')
    parser.add_argument('-o', '--output-dir', required=True,
                        help='Path to output directory for storing chunk files')
    parser.add_argument('-c', '--chunk-size', type=int, default=1000000,
                        help='Size of each chunk (default: 1000000)')
    parser.add_argument('--job-array', choices=['slurm', 'sge', 'lsf', 'none'], default='none',
                        help='Type of job array to generate (slurm, sge, lsf) or none for a simple shell script')
    
    args = parser.parse_args()
    
    # Ensure the output directory exists
    create_output_dir(args.output_dir)
    
    # Count total regions
    print(f"Counting regions in {args.region_filename}...")
    num_regions = count_regions(args.region_filename)
    print(f"Total number of regions: {num_regions}")
    
    # Calculate number of chunks
    num_chunks = math.ceil(num_regions / args.chunk_size)
    print(f"Number of chunks (with {args.chunk_size} regions per chunk): {num_chunks}")
    
    # Generate commands for all chunks
    commands = generate_commands(args, num_regions, num_chunks)
    
    # Create job logs directory if needed
    if args.job_array != 'none':
        os.makedirs('job_logs', exist_ok=True)
    
    # Create output script
    if args.job_array != 'none':
        script_path = os.path.join(args.output_dir, f"process_regions_job_array_{args.job_array}.sh")
        create_job_array_script(commands, script_path, args.job_array)
    else:
        script_path = os.path.join(args.output_dir, "process_regions.sh")
        create_shell_script(commands, script_path)
    
    # Create a script to combine all processed chunks
    generate_combine_script(args, num_chunks)
    
    print("\nWhat to do next:")
    print(f"1. Run the generated script: {script_path}")
    print(f"   - For job arrays, submit with: sbatch {script_path} (SLURM)")
    print(f"   - For job arrays, submit with: qsub {script_path} (SGE)")
    print(f"   - For job arrays, submit with: bsub < {script_path} (LSF)")
    print(f"   - For simple shell script: bash {script_path}")
    print(f"2. After all chunks are processed, run: bash {args.output_dir}/combine_chunks.sh")

if __name__ == "__main__":
    main() 