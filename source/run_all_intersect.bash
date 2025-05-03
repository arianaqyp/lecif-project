#!/bin/bash

# --- Configuration ---
# Path to the intersection script
INTERSECT_SCRIPT="source/runIntersect"

# Path to the human coordinate file (output from samplePairs.py)
HUMAN_COORD_FILE="position/hg19.mm10.50bp.h.gz"
# Path to the mouse coordinate file (output from samplePairs.py)
MOUSE_COORD_FILE="position/hg19.mm10.50bp.m.gz"

# Base directory containing preprocessed feature files (input for this script)
PREPROCESSED_BASE_DIR="feature/preprocessed"
# Base directory where intersect results will be stored (output)
INTERSECT_BASE_DIR="feature/intersect"

# Log file for script output and timing
LOG_FILE="log/intersect_all_features.log"
# Directory for log file
LOG_DIR=$(dirname "${LOG_FILE}")

# Maximum number of concurrent intersect jobs
# Adjust based on your system's resources (CPU cores, memory, disk I/O)
MAX_CONCURRENT_JOBS=100

# --- Sanity Checks ---

# Check if intersect script exists and is executable
if [ ! -x "${INTERSECT_SCRIPT}" ]; then
  echo "Error: Intersection script '${INTERSECT_SCRIPT}' not found or not executable." | tee -a "${LOG_FILE}"
  echo "Please ensure the path is correct and run 'chmod +x ${INTERSECT_SCRIPT}'." | tee -a "${LOG_FILE}"
  exit 1
fi

# Check if coordinate files exist
if [ ! -f "${HUMAN_COORD_FILE}" ]; then
  echo "Error: Human coordinate file '${HUMAN_COORD_FILE}' not found." | tee -a "${LOG_FILE}"
  exit 1
fi
if [ ! -f "${MOUSE_COORD_FILE}" ]; then
  echo "Error: Mouse coordinate file '${MOUSE_COORD_FILE}' not found." | tee -a "${LOG_FILE}"
  exit 1
fi

# Check if preprocessed directory exists
if [ ! -d "${PREPROCESSED_BASE_DIR}" ]; then
  echo "Error: Preprocessed features base directory '${PREPROCESSED_BASE_DIR}' not found." | tee -a "${LOG_FILE}"
  exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# --- Timing and Logging Initialization ---
# Clear previous log file or create a new one
> "${LOG_FILE}"
echo "Starting parallel batch intersection (Max Jobs: ${MAX_CONCURRENT_JOBS})..." | tee -a "${LOG_FILE}"
echo "Log file: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "-------------------------------------" | tee -a "${LOG_FILE}"

# Record overall start time
overall_start_time=$(date +%s) # Seconds since epoch
overall_start_time_human=$(date) # Human-readable time
echo "Overall Script Start Time: ${overall_start_time_human}" | tee -a "${LOG_FILE}"
echo "-------------------------------------" | tee -a "${LOG_FILE}"

# --- Find and Process Feature Files ---
processed_count=0

# Array to store PIDs of background processes
declare -a pids

# Function to get current number of running jobs
count_running_jobs() {
  local running=0
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      running=$((running + 1))
    fi
  done
  echo "$running"
}

# Use find to get all .gz files within the preprocessed subdirectories
# -print0 and read -d $'\0' handle filenames with spaces or special characters
find "${PREPROCESSED_BASE_DIR}" -type f -name "*.gz" -print0 | while IFS= read -r -d $'\0' preprocessed_file; do
  processed_count=$((processed_count + 1))
  echo "Found file ${processed_count}: ${preprocessed_file}" | tee -a "${LOG_FILE}"

  # Extract subdirectory name (e.g., hg19_DNaseChIPseq) and filename
  relative_path=${preprocessed_file#${PREPROCESSED_BASE_DIR}/} # Remove base path prefix
  subdir_name=$(dirname "${relative_path}")
  feature_filename=$(basename "${preprocessed_file}")

  # Determine species and coordinate file
  species_coord_file=""
  if [[ "${subdir_name}" == *"hg19"* ]]; then
    species_coord_file="${HUMAN_COORD_FILE}"
    echo "  Species: Human (using ${HUMAN_COORD_FILE})" | tee -a "${LOG_FILE}"
  elif [[ "${subdir_name}" == *"mm10"* ]]; then
    species_coord_file="${MOUSE_COORD_FILE}"
    echo "  Species: Mouse (using ${MOUSE_COORD_FILE})" | tee -a "${LOG_FILE}"
  else
    echo "  WARNING: Cannot determine species from subdirectory '${subdir_name}'. Skipping file." | tee -a "${LOG_FILE}"
    continue
  fi

  # Determine data type code for runIntersect
  # 0 = DNase/ChIP-seq, 1 = ChromHMM/CAGE/RNA-seq
  data_type_code=""
  if [[ "${subdir_name}" == *"DNaseChIPseq"* ]]; then
    data_type_code="0"
    echo "  Data Type: DNase/ChIP-seq (code 0)" | tee -a "${LOG_FILE}"
  elif [[ "${subdir_name}" == *"ChromHMM"* || "${subdir_name}" == *"CAGE"* || "${subdir_name}" == *"RNAseq"* ]]; then
    data_type_code="1"
    echo "  Data Type: ChromHMM/CAGE/RNA-seq (code 1)" | tee -a "${LOG_FILE}"
  else
    echo "  WARNING: Cannot determine data type from subdirectory '${subdir_name}'. Skipping file." | tee -a "${LOG_FILE}"
    continue
  fi

  # Construct output path and create directory
  intersect_output_dir="${INTERSECT_BASE_DIR}/${subdir_name}"
  intersect_output_file="${intersect_output_dir}/${feature_filename}"
  mkdir -p "${intersect_output_dir}"
  if [ $? -ne 0 ]; then
    echo "  ERROR: Could not create output directory '${intersect_output_dir}'. Skipping file." | tee -a "${LOG_FILE}"
    continue
  fi
  echo "  Output file: ${intersect_output_file}" | tee -a "${LOG_FILE}"

  # Wait until we have fewer than MAX_CONCURRENT_JOBS running
  while [ "$(count_running_jobs)" -ge "${MAX_CONCURRENT_JOBS}" ]; do
    echo "  Current running jobs: $(count_running_jobs). Waiting for a job to finish..." | tee -a "${LOG_FILE}"
    # Sleep briefly to avoid excessive CPU usage in the loop
    sleep 1
    
    # Clean up the pids array by removing completed jobs
    for i in "${!pids[@]}"; do
      if ! kill -0 "${pids[$i]}" 2>/dev/null; then
        unset "pids[$i]"
      fi
    done
    # Re-index array to remove empty slots
    pids=("${pids[@]}")
  done

  # Construct the command
  command_to_run="${INTERSECT_SCRIPT} ${species_coord_file} ${preprocessed_file} ${intersect_output_file} ${data_type_code}"
  echo "  Running command in background: ${command_to_run}" | tee -a "${LOG_FILE}"

  # Execute the command in the background, appending its stdout and stderr to the log file
  ${command_to_run} >> "${LOG_FILE}" 2>&1 &
  
  # Store the PID of the background job
  pid=$!
  pids+=("$pid")
  echo "  Started job with PID: $pid. Current job count: $(count_running_jobs)" | tee -a "${LOG_FILE}"

done

# --- Wait for any remaining jobs ---
echo "-------------------------------------" | tee -a "${LOG_FILE}"
echo "All intersection tasks launched. Waiting for remaining $(count_running_jobs) jobs to complete..." | tee -a "${LOG_FILE}"
wait # Wait for all remaining background jobs
echo "All jobs finished." | tee -a "${LOG_FILE}"
echo "-------------------------------------" | tee -a "${LOG_FILE}"

# --- Final Timing ---
overall_end_time=$(date +%s)
overall_end_time_human=$(date)
overall_duration=$((overall_end_time - overall_start_time))

echo "Overall Script End Time: ${overall_end_time_human}" | tee -a "${LOG_FILE}"
echo "Total Script Duration: ${overall_duration} seconds" | tee -a "${LOG_FILE}"
echo "Parallel batch intersection finished." | tee -a "${LOG_FILE}"

