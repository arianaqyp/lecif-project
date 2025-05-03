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
python source/generateDataThreaded.py -p position/hg19.mm10.50bp.h.gz -ca feature/intersect/hg19_CAGE/ -ch feature/intersect/hg19_ChromHMM/ -dn feature/intersect/hg19_DNaseChIPseq/ -rn feature/intersect/hg19_RNAseq/ -chn 25 -can 1829 -fn 8824 -o data/split/all_1.h.gz -s -c 100 -i 1
```
