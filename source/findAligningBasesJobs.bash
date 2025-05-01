#!/bin/bash

# --- Configuration ---
# Path to the LECIF source directory (updated to use absolute path)
LECIF_SOURCE_DIR="$(dirname "$0")"
# Path to the findAligningBases.py script
PYTHON_SCRIPT="${LECIF_SOURCE_DIR}/findAligningBases.py"
# Directory containing the downloaded axtNet files
AXTNET_DIR="position/axtNet"
# Path to the mm10 chromosome sizes file
# Download from: http://hgdownload.cse.ucsc.edu/goldenpath/mm10/bigZips/mm10.chrom.sizes
MM10_CHROM_SIZES="position/mm10.chrom.sizes"
# Directory to save the output files
OUTPUT_DIR="position/aligning_bases_by_chrom"
# Python executable (use python3 if python defaults to python2)
PYTHON_EXEC="python"
# Maximum number of concurrent jobs
MAX_JOBS=100
# Log file for PIDs
PID_LOG_FILE="${OUTPUT_DIR}/job_pids.log"
# Log file for completion status and timing
COMPLETION_LOG_FILE="${OUTPUT_DIR}/job_completion.log"
# --- End Configuration ---

# Check if the python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at $PYTHON_SCRIPT"
    echo "Hint: The path should be relative to where you're executing the script from, not relative to this script's location"
    exit 1
fi

# Check if the axtNet directory exists
if [ ! -d "$AXTNET_DIR" ]; then
    echo "Error: axtNet directory not found at $AXTNET_DIR"
    exit 1
fi

# Check if the mm10 chromosome sizes file exists
if [ ! -f "$MM10_CHROM_SIZES" ]; then
    echo "Error: mm10.chrom.sizes file not found at $MM10_CHROM_SIZES"
    echo "Please download it from http://hgdownload.cse.ucsc.edu/goldenpath/mm10/bigZips/mm10.chrom.sizes"
    exit 1
fi

# Create the output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Clear or create the log files at the start
> "$PID_LOG_FILE"
> "$COMPLETION_LOG_FILE"

echo "Starting processing of axtNet files (max ${MAX_JOBS} parallel jobs)..."
echo "Logging PIDs to ${PID_LOG_FILE}"
echo "Logging completion status and timing to ${COMPLETION_LOG_FILE}"

# Initialize job counter
job_count=0

# Loop through all relevant axtNet files in the directory
for axt_file in "$AXTNET_DIR"/chr*.hg19.mm10.net.axt.gz
do
    # Check if the file exists (handles cases where the glob doesn't match anything)
    if [ -e "$axt_file" ]; then
        # Extract the base filename (e.g., chr21.hg19.mm10.net.axt.gz)
        base_filename=$(basename "$axt_file")
        # Extract the chromosome name (e.g., chr21)
        # This assumes the format chr<number/X>.hg19.mm10.net.axt.gz
        chr_name=$(echo "$base_filename" | cut -d'.' -f1)

        # Construct the output filename (e.g., hg19.chr21.mm10.basepair.gz)
        output_filename="${OUTPUT_DIR}/hg19.${chr_name}.mm10.basepair.gz"

        echo "Launching job for $base_filename -> $output_filename"

        # Run the python script in the background
        ( # Start subshell to group commands and capture exit status
            start_time_inner=$(date +%s.%N) # High-resolution start time

            "$PYTHON_EXEC" "$PYTHON_SCRIPT" \
                -a "$axt_file" \
                -m "$MM10_CHROM_SIZES" \
                -o "$output_filename"

            status=$? # Capture exit status
            end_time_inner=$(date +%s.%N) # High-resolution end time

            # Calculate duration using awk for floating point arithmetic
            duration=$(awk -v start="$start_time_inner" -v end="$end_time_inner" 'BEGIN {print end - start}')

            # Log completion status, duration, and end time
            echo "File: ${base_filename} | Duration: ${duration} s | Status: ${status} | End: $(date +'%Y-%m-%d %H:%M:%S')" >> "${COMPLETION_LOG_FILE}"

            # Optional: Echo status to main script output (might be noisy)
            # if [ $status -ne 0 ]; then
            #     echo "Error processing $base_filename (PID: $$). Status: $status. Duration: ${duration} s."
            # else
            #    echo "Finished job for $base_filename (PID: $$). Duration: ${duration} s."
            # fi
        ) & # Run the subshell in the background

        # Capture the PID of the last backgrounded process
        pid=$!
        # Log PID, filename and launch time
        echo "PID: ${pid} | File: ${base_filename} | Start: $(date +'%Y-%m-%d %H:%M:%S')" >> "${PID_LOG_FILE}"

        # Increment job counter
        ((job_count++))

        # Check if the maximum number of jobs has been reached
        if [ "$job_count" -ge "$MAX_JOBS" ]; then
            echo "Reached max jobs (${MAX_JOBS}), waiting for a job to finish..."
            # Wait for any background job to finish
            wait -n
            # Decrement job counter (optional, as wait -n handles it, but good for clarity)
             ((job_count--))
        fi
    fi
done

# Wait for all remaining background jobs to complete
echo "Waiting for remaining jobs to finish..."
wait

echo "Processing complete."
echo "Output files are in $OUTPUT_DIR"
echo "PID logs are in ${PID_LOG_FILE}"
echo "Completion logs are in ${COMPLETION_LOG_FILE}"