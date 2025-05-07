#!/bin/bash

# --- Configuration ---
# Path to the preprocessing script
PREPROCESS_SCRIPT="source/preprocessFeatureFiles"

# Base directory for raw (input) features
RAW_BASE_DIR="feature/raw"
# Base directory for preprocessed (output) features
PREPROCESSED_BASE_DIR="feature/preprocessed"

# Log file for script output and timing
LOG_FILE="log/preprocess_all_features_MOUSE_CAGE.log"

# Maximum number of concurrent preprocessing jobs
MAX_CONCURRENT_JOBS=100

# --- Check if preprocess script exists and is executable ---
if [ ! -x "${PREPROCESS_SCRIPT}" ]; then
  echo "Error: Preprocessing script '${PREPROCESS_SCRIPT}' not found or not executable." | tee -a "${LOG_FILE}"
  echo "Please ensure the path is correct and run 'chmod +x ${PREPROCESS_SCRIPT}'." | tee -a "${LOG_FILE}"
  exit 1
fi

# --- Define Preprocessing Tasks ---
# Format: "subdirectory_suffix species_code data_type_code"
# Species: 0=Human, 1=Mouse
# Data Type: 0=DNase/ChIP-seq, 1=ChromHMM, 2=CAGE, 3=RNA-seq
declare -a tasks=(
  # "hg19_DNaseChIPseq 0 0"
  # "hg19_ChromHMM 0 1"
  # "hg19_CAGE 0 2"
  # "hg19_RNAseq 0 3"
  # "mm10_DNaseChIPseq 1 0"
  # "mm10_ChromHMM 1 1"
  "mm10_CAGE 1 2"
  # "mm10_RNAseq 1 3"
)

# --- Timing and Logging Initialization ---
# Clear previous log file or create a new one
> "${LOG_FILE}"
echo "Starting parallel batch preprocessing (Max Jobs: ${MAX_CONCURRENT_JOBS})..." | tee -a "${LOG_FILE}"
echo "Log file: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "-------------------------------------" | tee -a "${LOG_FILE}"

# Record overall start time
overall_start_time=$(date +%s) # Seconds since epoch
overall_start_time_human=$(date) # Human-readable time
echo "Overall Script Start Time: ${overall_start_time_human}" | tee -a "${LOG_FILE}"
echo "-------------------------------------" | tee -a "${LOG_FILE}"


# --- Execute Preprocessing Tasks ---
task_num=0
total_tasks=${#tasks[@]}
job_count=0

for task_info in "${tasks[@]}"; do
  task_num=$((task_num + 1))
  # Parse task info
  read -r dir_suffix species_code type_code <<< "${task_info}"

  # Construct full paths
  input_dir="${RAW_BASE_DIR}/${dir_suffix}"
  output_dir="${PREPROCESSED_BASE_DIR}/${dir_suffix}"

  echo "Initiating Task ${task_num}/${total_tasks}: ${dir_suffix} (Species: ${species_code}, Type: ${type_code})" | tee -a "${LOG_FILE}"
  task_start_time_human=$(date)
  # task_start_time_secs=$(date +%s) # Removed as duration is not tracked per task anymore
  echo "Task Start Time: ${task_start_time_human}" | tee -a "${LOG_FILE}"

  # Check if input directory exists
  if [ ! -d "${input_dir}" ]; then
    echo "  WARNING: Input directory '${input_dir}' not found. Skipping task." | tee -a "${LOG_FILE}"
    echo "-------------------------------------" | tee -a "${LOG_FILE}"
    continue # Skip to the next task
  fi

  # Create output directory if it doesn't exist
  mkdir -p "${output_dir}"
  if [ $? -ne 0 ]; then
    echo "  ERROR: Could not create output directory '${output_dir}'. Skipping task." | tee -a "${LOG_FILE}"
    echo "-------------------------------------" | tee -a "${LOG_FILE}"
    continue # Skip to the next task
  fi

  # Construct the command
  command_to_run="${PREPROCESS_SCRIPT} ${input_dir} ${output_dir} ${species_code} ${type_code}"
  echo "  Running command in background: ${command_to_run}" | tee -a "${LOG_FILE}"
  echo "  Detailed output/errors for this task will be in ${LOG_FILE}" | tee -a "${LOG_FILE}"

  # Execute the command in the background, appending its stdout and stderr to the log file
  ${command_to_run} >> "${LOG_FILE}" 2>&1 &

  # Increment job counter
  job_count=$((job_count + 1))

  # Check if max concurrent jobs reached
  if [[ ${job_count} -ge ${MAX_CONCURRENT_JOBS} ]]; then
    echo "  Reached max concurrent jobs (${MAX_CONCURRENT_JOBS}). Waiting for current batch to finish..." | tee -a "${LOG_FILE}"
    wait # Wait for all background jobs in the current batch to complete
    echo "  Current batch finished. Proceeding..." | tee -a "${LOG_FILE}"
    job_count=0 # Reset job counter for the next batch
  fi

  # Removed immediate exit status check and duration calculation as tasks run in parallel
  echo "-------------------------------------" | tee -a "${LOG_FILE}"

done

# --- Wait for any remaining jobs ---
if [[ ${job_count} -gt 0 ]]; then
  echo "Waiting for the final batch of ${job_count} jobs to complete..." | tee -a "${LOG_FILE}"
  wait # Wait for all remaining background jobs
  echo "Final batch finished." | tee -a "${LOG_FILE}"
fi
echo "-------------------------------------" | tee -a "${LOG_FILE}"

# --- Final Timing ---
overall_end_time=$(date +%s)
overall_end_time_human=$(date)
overall_duration=$((overall_end_time - overall_start_time))

echo "Overall Script End Time: ${overall_end_time_human}" | tee -a "${LOG_FILE}"
echo "Total Script Duration: ${overall_duration} seconds" | tee -a "${LOG_FILE}"
echo "Parallel batch preprocessing finished." | tee -a "${LOG_FILE}"

