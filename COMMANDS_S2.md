# Download cage files manually
https://fantom.gsc.riken.jp/5/data/
https://fantom.gsc.riken.jp/5/datafiles/latest/extra/CAGE_peaks/hg19.cage_peak_phase1and2combined_counts.osc.txt.gz
https://fantom.gsc.riken.jp/5/datafiles/reprocessed/mm10_v9/extra/CAGE_peaks_expression/mm10_fair+new_CAGE_peaks_phase1and2_counts.osc.txt.gz

# run preprocessFeatureFiles in parallel
nohup bash source/run_all_preprocessing.bash & echo $! > log/preprocess_all.pid

# run runIntersect in parallel
<!-- nohup bash source/run_all_intersect.bash & echo $! > log/run_all_intersect.pid -->
nohup bash source/run_all_intersect_MOUSE_CAGE.bash & echo $! > log/run_all_intersect_MOUSE_CAGE.pid

# just mouse
source/runIntersect position/hg19.mm10.50bp.m.gz \
feature/preprocessed/mm10_CAGE/mm10_fair+new_CAGE_peaks_phase1and2_counts.osc.txt.gz \
feature/intersect/mm10_CAGE/mm10_fair+new_CAGE_peaks_phase1and2_counts.osc.txt.gz \
1

# Aggregate preprocessed feature data for 1 million genomic region (1 chunk)
``` example of one command:
# human:
python -u source/generateDataThreaded.py -p position/hg19.mm10.50bp.h.gz -ca feature/intersect/hg19_CAGE/ -ch feature/intersect/hg19_ChromHMM/ -dn feature/intersect/hg19_DNaseChIPseq/ -rn feature/intersect/hg19_RNAseq/ -chn 25 -can 1829 -fn 8824 -o data/split/all_1.h.gz -s -c 5 -i 1

# mouse:
python -u source/generateDataThreaded_DEBUG.py -p position/hg19.mm10.50bp.m.gz   -ca feature/intersect/mm10_CAGE/   -ch feature/intersect/mm10_ChromHMM/   -dn feature/intersect/mm10_DNaseChIPseq/   -rn feature/intersect/mm10_RNAseq/   -chn 15 -can 1073 -fn 3313   -o data/split/all_1.m.gz -s -c 5 -i 1
```i 

# Aggregate preprocessed feature data for 1 million genomic region (parallel)
```example command:
# human:
python source/countAndProcessRegions.py   -p position/hg19.mm10.50bp.h.gz   -ca feature/intersect/hg19_CAGE/   -ch feature/intersect/hg19_ChromHMM/   -dn feature/intersect/hg19_DNaseChIPseq/   -rn feature/intersect/hg19_RNAseq/   -chn 25 -can 1829 -fn 8824   -o data/split/   --parallel   --max-processes 10

# mouse
python source/countAndProcessRegions.py   -p position/hg19.mm10.50bp.m.gz   -ca feature/intersect/mm10_CAGE/   -ch feature/intersect/mm10_ChromHMM/   -dn feature/intersect/mm10_DNaseChIPseq/   -rn feature/intersect/mm10_RNAseq/   -chn 15 -can 1073 -fn 3313   -o data/split/   --parallel   --max-processes 10
```

For human:
What to do next:
1. Run the script with nohup for background execution:
   nohup bash data/split/process_regions.sh > log/main_process.log 2>&1 &
   echo $! > pid/main_process.pid  # Save the main process PID
2. After all chunks are processed, run: nohup bash data/split/combine_chunks.sh > log/combine_chunks_main.log 2>&1 &

For mouse:

What to do next:
1. Run the script with nohup for background execution:
   nohup bash data/split/process_mouse_regions.sh > log/mouse_main_process.log 2>&1 &
   echo $! > pid/mouse_main_process.pid  # Save the main process PID
2. After all chunks are processed, run: nohup bash data/split/combine_mouse_chunks.sh > log/combine_mouse_chunks_main.log 2>&1 &

Process Management:
- All PIDs will be stored in the pid/ directory
- To kill all running processes: for p in $(cat pid/mouse_chunk_*.pid 2>/dev/null); do kill $p; done
- To check status: ls -l log/ | grep mouse_chunk


## No need nohup for python script
The implementation follows a two-step process:

1. **Setup Phase** (Python script):
   - The Python script counts regions, generates commands, and creates shell scripts
   - This phase is typically quick (seconds or minutes)
   - You run this normally: `python source/countAndProcessRegions.py ...`

2. **Execution Phase** (Shell script):
   - The shell script created by the Python script does the actual heavy processing
   - This is where you use nohup: `nohup bash data/split/process_regions.sh > log/main_process.log 2>&1 &`

The only case when you would need to run the Python script itself with nohup is if you use the `--execute` flag, which makes the Python script directly execute all the processing instead of creating a shell script:

```bash
# Only in this case would you need nohup on the Python command
nohup python source/countAndProcessRegions.py --execute --parallel ... > log/python_execution.log 2>&1 &
```

The preferred approach is the two-step process (without `--execute`), as it:
1. Keeps the setup and execution phases separate
2. Gives you a chance to review the generated commands before running them
3. Produces shell scripts that have better process control and signal handling

In short: Run the Python script normally, then use nohup on the generated shell script.


# Split input data for training, validation, test, and model comparison based on human and mouse chromosomes to ensure no data leakage.

```bash
nohup python source/splitData.py -A data/all.h.gz -B data/all.m.gz -N 32285361 -o data/ $(cat example/splitData_args_complete.txt) > log/splitData.log 2>&1 &
```

# 2.7 Prepare the data generated above for training
nohup bash -c "START_TIME=\$(date +%s); echo \"Started at: \$(date)\" > log/prepare_data.log; echo \"PID: \$$\" >> log/prepare_data.log; bash source/prepareData data data; END_TIME=\$(date +%s); echo \"Ended at: \$(date)\" >> log/prepare_data.log; echo \"Total runtime: \$((\$END_TIME - \$START_TIME)) seconds\" >> log/prepare_data.log" > nohup.out 2>&1 & echo $! >> log/prepare_data.log