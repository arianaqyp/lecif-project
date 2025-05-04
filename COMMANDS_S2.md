# Download cage files manually
https://fantom.gsc.riken.jp/5/data/
https://fantom.gsc.riken.jp/5/datafiles/latest/extra/CAGE_peaks/hg19.cage_peak_phase1and2combined_counts.osc.txt.gz
https://fantom.gsc.riken.jp/5/datafiles/latest/extra/CAGE_peaks/mm9.cage_peak_phase1and2combined_counts_ann.osc.txt.gz

# run preprocessFeatureFiles in parallel
nohup bash source/run_all_preprocessing.bash & echo $! > log/preprocess_all.pid
<!-- nohup bash source/run_all_preprocessing.bash & echo $! > log/preprocess_all_rna_seq.pid  (We've missed out the RNAseq, did not have bigWigtoBedGraph installed) -->

# run runIntersect in parallel
nohup bash source/run_all_intersect.bash & echo $! > log/run_all_intersect.pid
nohup bash source/run_all_intersect.bash & echo $! > log/run_all_intersect_rna_seq.pid  (We've missed out the RNAseq, did not have bigWigtoBedGraph installed)

# Aggregate preprocessed feature data for 1 million genomic region (1 chunk)
``` example of one command:
python -u source/generateDataThreaded.py -p position/hg19.mm10.50bp.h.gz -ca feature/intersect/hg19_CAGE/ -ch feature/intersect/hg19_ChromHMM/ -dn feature/intersect/hg19_DNaseChIPseq/ -rn feature/intersect/hg19_RNAseq/ -chn 25 -can 1829 -fn 8824 -o data/split/all_1.h.gz -s -c 5 -i 1
```

# Aggregate preprocessed feature data for 1 million genomic region (parallel)
```example command:
python source/countAndProcessRegions.py   -p position/hg19.mm10.50bp.h.gz   -ca feature/intersect/hg19_CAGE/   -ch feature/intersect/hg19_ChromHMM/   -dn feature/intersect/hg19_DNaseChIPseq/   -rn feature/intersect/hg19_RNAseq/   -chn 25 -can 1829 -fn 8824   -o data/split/   --parallel   --max-processes 20
```

If need to kill:
```
# Kill all chunk processes
for p in $(cat pid/chunk_*.pid 2>/dev/null); do kill $p; done

# Kill a specific chunk
kill $(cat pid/chunk_5.pid)
```
To check logging:
```
# Check status of all chunks
ls -l log/ | grep chunk

# View progress of a specific chunk
tail -f log/chunk_5.log
```

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
