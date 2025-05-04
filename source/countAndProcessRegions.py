#!/usr/bin/env python3
'''
This script counts the total number of regions in a region file and sets up
processing commands for generateDataThreaded.py to handle all chunks efficiently.

It either:
1. Generates a shell script with commands to process all chunks, or
2. If requested, submits jobs directly using a job array system
3. Can directly run multiple chunks in parallel using multiprocessing

This helps automate step 2.4 in the LECIF README.md where feature data needs to be
aggregated for all genomic regions, 1 million regions per chunk.
'''

import argparse
import gzip
import os
import subprocess
import sys
import math
import multiprocessing
import signal
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

def count_regions(region_filename):
    """Count the total number of regions in the gzipped region file."""
    count = 0
    with gzip.open(region_filename, 'rt') as f:
        for _ in f:
            count += 1
    return count

def create_output_dir(directory):
    """Create directory if it doesn't exist."""
    Path(directory).mkdir(parents=True, exist_ok=True)

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

def run_command(command, chunk_id, log_dir):
    """Execute a command, manage PID file, and return its output and status."""
    pid_file = f"pid/chunk_{chunk_id}.pid"
    log_file = f"{log_dir}/chunk_{chunk_id}.log"
    
    try:
        # Create log file with script start message
        with open(log_file, 'w') as f:
            f.write(f"Starting chunk {chunk_id} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Command: {command}\n\n")
        
        print(f"Executing chunk {chunk_id}: {command}")
        
        # Start the process and redirect output
        with open(log_file, 'a') as log:
            process = subprocess.Popen(command, shell=True, stdout=log, stderr=log, universal_newlines=True)
            
            # Write the PID to the PID file
            with open(pid_file, 'w') as f:
                f.write(str(process.pid))
            
            # Wait for the process to complete
            process.wait()
            
            # Record exit code and completion time
            with open(log_file, 'a') as f:
                f.write(f"\nProcess completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Exit code: {process.returncode}\n")
            
            # Remove PID file when done
            if os.path.exists(pid_file):
                os.remove(pid_file)
                
            return process.returncode == 0, command, f"See log file: {log_file}"
            
    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(f"\nError: {str(e)}\n")
        
        # Ensure PID file is removed even if there's an error
        if os.path.exists(pid_file):
            os.remove(pid_file)
            
        return False, command, str(e)

def create_shell_script(commands, output_script, parallel=False, max_processes=None, log_dir="log"):
    """Create a shell script with all the commands."""
    with open(output_script, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Create directories for logs and PIDs\n")
        f.write("mkdir -p log pid\n\n")
        
        f.write("# Function to clean up on exit\n")
        f.write("cleanup() {\n")
        f.write("    echo \"Cleaning up PID files...\"\n")
        f.write("    # Kill all running processes\n")
        f.write("    for pid_file in pid/chunk_*.pid; do\n")
        f.write("        if [ -f \"$pid_file\" ]; then\n")
        f.write("            pid=$(cat \"$pid_file\")\n")
        f.write("            echo \"Killing process $pid from $pid_file\"\n")
        f.write("            kill -TERM $pid 2>/dev/null || echo \"Could not kill $pid\"\n")
        f.write("            rm -f \"$pid_file\"\n")
        f.write("        fi\n")
        f.write("    done\n")
        f.write("    echo \"Cleanup complete\"\n")
        f.write("    exit\n")
        f.write("}\n\n")
        
        f.write("# Set up signal handling\n")
        f.write("trap cleanup SIGINT SIGTERM EXIT\n\n")
        
        f.write("echo \"Starting processing at $(date)\"\n")
        f.write("echo \"Logging to ${PWD}/log/\"\n")
        f.write("echo \"PIDs stored in ${PWD}/pid/\"\n\n")
        
        if parallel:
            # Parallel execution
            max_processes = max_processes or max(1, multiprocessing.cpu_count() - 1)
            f.write(f"# Running commands in parallel (max {max_processes} at once)\n")
            
            # If GNU Parallel is available, use it
            f.write("if command -v parallel &> /dev/null; then\n")
            f.write("    # Use GNU Parallel with proper logging\n")
            f.write("    run_with_parallel() {\n")
            f.write("        chunk_id=$1\n")
            f.write("        shift\n")
            f.write("        # Start the process and redirect output\n")
            f.write("        \"$@\" > \"log/chunk_${chunk_id}.log\" 2>&1 &\n")
            f.write("        pid=$!\n")
            f.write("        echo \"Started chunk ${chunk_id} with PID ${pid}\"\n")
            f.write("        echo \"$pid\" > \"pid/chunk_${chunk_id}.pid\"\n")
            f.write("    }\n")
            f.write("    export -f run_with_parallel\n\n")
            
            f.write("    # Create array of commands\n")
            for i, cmd in enumerate(commands, 1):
                f.write(f"    cmd{i}=({cmd})\n")
            
            f.write("\n    # Run commands with parallel\n")
            f.write("    parallel -j {} run_with_parallel {1} {2} ::: ".format(max_processes))
            cmd_refs = [f"{i} \"${{cmd{i}[@]}}\"" for i in range(1, len(commands) + 1)]
            f.write(" ".join(cmd_refs))
            f.write("\n")
            f.write("else\n")
            # Fall back to background jobs with wait
            f.write("    # Fall back to background jobs with wait\n")
            f.write("    run_with_limit() {\n")
            f.write("        # Wait until we have fewer than max processes running\n")
            f.write("        while [ $(jobs -r | wc -l) -ge {} ]; do\n".format(max_processes))
            f.write("            sleep 1\n")
            f.write("        done\n")
            f.write("        chunk_id=$1\n")
            f.write("        shift\n")
            f.write("        # Start the process and redirect output\n")
            f.write("        \"$@\" > \"log/chunk_${chunk_id}.log\" 2>&1 &\n")
            f.write("        pid=$!\n")
            f.write("        echo \"Started chunk ${chunk_id} with PID ${pid}\"\n")
            f.write("        echo \"$pid\" > \"pid/chunk_${chunk_id}.pid\"\n")
            f.write("    }\n\n")
            
            for i, cmd in enumerate(commands, 1):
                f.write(f"    # Process chunk {i}\n")
                f.write(f"    run_with_limit {i} {cmd}\n")
            
            f.write("\n    # Wait for all background jobs to finish\n")
            f.write("    wait\n")
            f.write("fi\n")
        else:
            # Sequential execution
            for i, cmd in enumerate(commands, 1):
                f.write(f"# Process chunk {i}\n")
                f.write(f"echo \"Starting chunk {i} at $(date)\"\n")
                f.write(f"# Save PID\n")
                f.write(f"{cmd} > \"log/chunk_{i}.log\" 2>&1 &\n")
                f.write(f"pid=$!\n")
                f.write(f"echo \"$pid\" > \"pid/chunk_{i}.pid\"\n")
                f.write(f"echo \"Started chunk {i} with PID $pid\"\n")
                f.write(f"wait $pid\n")
                f.write(f"rm -f \"pid/chunk_{i}.pid\"\n")
                f.write(f"echo \"Finished chunk {i} at $(date)\"\n\n")
        
        f.write("\necho \"All processing completed at $(date)\"\n")
    
    # Make the script executable
    os.chmod(output_script, 0o755)
    print(f"Created shell script: {output_script}")
    print(f"Run with: nohup bash {output_script} > {log_dir}/main_process.log 2>&1 &")
    print(f"To kill all processes: bash -c 'for p in $(cat pid/chunk_*.pid 2>/dev/null); do kill $p 2>/dev/null; done'")

def create_job_array_script(commands, output_script, job_array_type, mem_per_job="16G", time_per_job="12:00:00", log_dir="log"):
    """Create a job array script based on the specified type (SLURM/SGE/LSF)."""
    with open(output_script, 'w') as f:
        f.write("#!/bin/bash\n")
        
        if job_array_type.lower() == "slurm":
            f.write(f"#SBATCH --array=1-{len(commands)}\n")
            f.write("#SBATCH --job-name=LECIF_feature_agg\n")
            f.write(f"#SBATCH --output={log_dir}/LECIF_feature_agg_%A_%a.out\n")
            f.write(f"#SBATCH --error={log_dir}/LECIF_feature_agg_%A_%a.err\n")
            f.write(f"#SBATCH --time={time_per_job}\n")
            f.write(f"#SBATCH --mem={mem_per_job}\n")
            f.write("#SBATCH --cpus-per-task=4\n")  # Request 4 CPUs for the 4 threads
            f.write("\n")
            f.write("mkdir -p pid\n")
            f.write("# Create PID file for this job\n")
            f.write("echo $$ > pid/slurm_${SLURM_ARRAY_TASK_ID}.pid\n\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands, 1):
                f.write(f"commands[{i}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Log the start of the job\n")
            f.write("echo \"Starting job array task ${SLURM_ARRAY_TASK_ID} at $(date)\"\n")
            f.write("echo \"Command: ${commands[$SLURM_ARRAY_TASK_ID]}\"\n\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$SLURM_ARRAY_TASK_ID]}\n\n")
            f.write("# Log the completion and remove PID file\n")
            f.write("echo \"Completed job array task ${SLURM_ARRAY_TASK_ID} at $(date)\"\n")
            f.write("rm -f pid/slurm_${SLURM_ARRAY_TASK_ID}.pid\n")
        
        elif job_array_type.lower() == "sge":
            f.write(f"#$ -t 1-{len(commands)}\n")
            f.write("#$ -N LECIF_feature_agg\n")
            f.write(f"#$ -o {log_dir}/LECIF_feature_agg_$JOB_ID_$TASK_ID.out\n")
            f.write(f"#$ -e {log_dir}/LECIF_feature_agg_$JOB_ID_$TASK_ID.err\n")
            f.write(f"#$ -l h_rt={time_per_job}\n")
            f.write(f"#$ -l h_vmem={mem_per_job}\n")
            f.write("#$ -pe threaded 4\n")  # Request 4 slots/CPUs for the 4 threads
            f.write("\n")
            f.write("mkdir -p pid\n")
            f.write("# Create PID file for this job\n")
            f.write("echo $$ > pid/sge_${SGE_TASK_ID}.pid\n\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands, 1):
                f.write(f"commands[{i}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Log the start of the job\n")
            f.write("echo \"Starting job array task ${SGE_TASK_ID} at $(date)\"\n")
            f.write("echo \"Command: ${commands[$SGE_TASK_ID]}\"\n\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$SGE_TASK_ID]}\n\n")
            f.write("# Log the completion and remove PID file\n")
            f.write("echo \"Completed job array task ${SGE_TASK_ID} at $(date)\"\n")
            f.write("rm -f pid/sge_${SGE_TASK_ID}.pid\n")
        
        elif job_array_type.lower() == "lsf":
            f.write(f"#BSUB -J LECIF_feature_agg[1-{len(commands)}]\n")
            f.write(f"#BSUB -o {log_dir}/LECIF_feature_agg_%J_%I.out\n")
            f.write(f"#BSUB -e {log_dir}/LECIF_feature_agg_%J_%I.err\n")
            f.write(f"#BSUB -W {time_per_job}\n")
            f.write(f"#BSUB -M {mem_per_job}\n")
            f.write("#BSUB -n 4\n")  # Request 4 CPUs for the 4 threads
            f.write("\n")
            f.write("mkdir -p pid\n")
            f.write("# Create PID file for this job\n")
            f.write("echo $$ > pid/lsf_${LSB_JOBINDEX}.pid\n\n")
            f.write("# Create commands array\n")
            f.write("declare -a commands\n")
            for i, cmd in enumerate(commands, 1):
                f.write(f"commands[{i}]=\"{cmd}\"\n")
            f.write("\n")
            f.write("# Log the start of the job\n")
            f.write("echo \"Starting job array task ${LSB_JOBINDEX} at $(date)\"\n")
            f.write("echo \"Command: ${commands[$LSB_JOBINDEX]}\"\n\n")
            f.write("# Execute the command for this array job\n")
            f.write("${commands[$LSB_JOBINDEX]}\n\n")
            f.write("# Log the completion and remove PID file\n")
            f.write("echo \"Completed job array task ${LSB_JOBINDEX} at $(date)\"\n")
            f.write("rm -f pid/lsf_${LSB_JOBINDEX}.pid\n")
        
        else:
            print(f"Unsupported job array type: {job_array_type}")
            sys.exit(1)
    
    # Make the script executable
    os.chmod(output_script, 0o755)
    print(f"Created job array script for {job_array_type}: {output_script}")

def run_commands_parallel(commands, max_workers=None, log_dir="log"):
    """Execute commands in parallel using ProcessPoolExecutor."""
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)
    
    # Create required directories
    create_output_dir("pid")
    create_output_dir(log_dir)
    
    print(f"Running {len(commands)} commands in parallel with {max_workers} workers")
    print(f"Logs will be stored in {log_dir}/")
    print(f"PIDs will be stored in pid/")
    
    # Set up a clean exit handler that kills all child processes
    def signal_handler(sig, frame):
        print(f"\nReceived signal {sig}. Cleaning up...")
        # Read all PIDs and kill them
        for pid_file in Path("pid").glob("chunk_*.pid"):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    print(f"Killing process {pid}")
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        print(f"Process {pid} not found")
                # Remove PID file
                pid_file.unlink()
            except Exception as e:
                print(f"Error processing {pid_file}: {e}")
        print("Cleanup complete. Exiting.")
        sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Execute commands in parallel with proper chunk IDs
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Map each command to a chunk ID
        futures = [executor.submit(run_command, cmd, i, log_dir) 
                 for i, cmd in enumerate(commands, 1)]
        
        # Process results as they complete
        success_count = 0
        failure_count = 0
        results = []
        
        for future in futures:
            try:
                result = future.result()
                results.append(result)
                
                success, cmd, output = result
                if success:
                    success_count += 1
                    print(f"Command completed successfully: {output}")
                else:
                    failure_count += 1
                    print(f"Command failed: {cmd}")
                    print(f"Error: {output}")
            except Exception as e:
                failure_count += 1
                print(f"Error processing command: {e}")
    
    print(f"Completed: {success_count} successful, {failure_count} failed")
    
    # Print failures if any
    if failure_count > 0:
        print("\nFailed commands:")
        for success, cmd, output in results:
            if not success:
                print(f"Command: {cmd}")
                print(f"Error: {output}")
                print("-" * 40)
    
    return success_count == len(commands)

def generate_combine_script(args, num_chunks):
    """Generate a script to combine all output chunks."""
    combine_script = os.path.join(args.output_dir, "combine_chunks.sh")
    with open(combine_script, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Script to combine all processed chunks into a single file\n\n")
        f.write("# Create log directory\n")
        f.write("mkdir -p log\n\n")
        
        # Species identifier (h or m) from the region filename
        species_id = "h" if ".h.gz" in args.region_filename else "m"
        
        # Create the command to combine files
        combine_cmd = f"cat {args.output_dir}/all_*.gz > {args.output_dir}/all.{species_id}.gz"
        f.write(f"echo \"Combining {num_chunks} chunks into a single file...\"\n")
        f.write(f"{combine_cmd} > log/combine_chunks.log 2>&1\n")
        f.write("if [ $? -eq 0 ]; then\n")
        f.write("    echo \"Combination complete.\"\n")
        f.write("else\n")
        f.write("    echo \"Error during combination. Check log/combine_chunks.log\"\n")
        f.write("fi\n")
    
    # Make the script executable
    os.chmod(combine_script, 0o755)
    print(f"Created combine script: {combine_script}")
    print(f"Run with: nohup bash {combine_script} > log/combine_chunks_main.log 2>&1 &")

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
                        help='Type of job array to generate (slurm, sge, lsf) or none for a shell script')
    parser.add_argument('--time-per-job', default='12:00:00',
                        help='Time limit per job for cluster submissions (default: 12:00:00)')
    parser.add_argument('--mem-per-job', default='16G',
                        help='Memory limit per job for cluster submissions (default: 16G)')
    parser.add_argument('--parallel', action='store_true',
                        help='Run commands in parallel when not using job arrays')
    parser.add_argument('--max-processes', type=int, default=None,
                        help='Maximum number of parallel processes to use (default: number of CPUs - 1)')
    parser.add_argument('--execute', action='store_true',
                        help='Execute commands immediately instead of creating scripts')
    parser.add_argument('--log-dir', default='log',
                        help='Directory for storing log files (default: log)')
    
    args = parser.parse_args()
    
    # Ensure the output directory exists
    create_output_dir(args.output_dir)
    create_output_dir(args.log_dir)
    create_output_dir("pid")
    
    # Count total regions
    print(f"Counting regions in {args.region_filename}...")
    num_regions = count_regions(args.region_filename)
    print(f"Total number of regions: {num_regions}")
    
    # Calculate number of chunks
    num_chunks = math.ceil(num_regions / args.chunk_size)
    print(f"Number of chunks (with {args.chunk_size} regions per chunk): {num_chunks}")
    
    # Generate commands for all chunks
    commands = generate_commands(args, num_regions, num_chunks)
    
    # Handle execution based on options
    if args.execute:
        print(f"Executing commands directly with logs in {args.log_dir}/")
        if args.parallel:
            success = run_commands_parallel(commands, args.max_processes, args.log_dir)
            if success:
                print("All commands completed successfully")
            else:
                print("Some commands failed - check the logs")
        else:
            print("Running commands sequentially...")
            for i, cmd in enumerate(commands, 1):
                success, _, output = run_command(cmd, i, args.log_dir)
                if not success:
                    print(f"Command {i} failed: {cmd}")
                    print(output)
    else:
        # Create output script
        if args.job_array != 'none':
            script_path = os.path.join(args.output_dir, f"process_regions_job_array_{args.job_array}.sh")
            create_job_array_script(commands, script_path, args.job_array, 
                                  args.mem_per_job, args.time_per_job, args.log_dir)
        else:
            script_path = os.path.join(args.output_dir, "process_regions.sh")
            create_shell_script(commands, script_path, args.parallel, args.max_processes, args.log_dir)
        
        # Create a script to combine all processed chunks
        generate_combine_script(args, num_chunks)
        
        print("\nWhat to do next:")
        if args.job_array != 'none':
            if args.job_array == 'slurm':
                print(f"1. Submit the job array: sbatch {script_path}")
            elif args.job_array == 'sge':
                print(f"1. Submit the job array: qsub {script_path}")
            elif args.job_array == 'lsf':
                print(f"1. Submit the job array: bsub < {script_path}")
        else:
            print(f"1. Run the script with nohup for background execution:")
            print(f"   nohup bash {script_path} > {args.log_dir}/main_process.log 2>&1 &")
            print(f"   echo $! > pid/main_process.pid  # Save the main process PID")
        
        print(f"2. After all chunks are processed, run: nohup bash {args.output_dir}/combine_chunks.sh > {args.log_dir}/combine_chunks_main.log 2>&1 &")
        print("\nProcess Management:")
        print(f"- All PIDs will be stored in the pid/ directory")
        print(f"- To kill all running processes: for p in $(cat pid/chunk_*.pid 2>/dev/null); do kill $p; done")
        print(f"- To check status: ls -l {args.log_dir}/ | grep chunk")

if __name__ == "__main__":
    main() 