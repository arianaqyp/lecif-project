#!/bin/bash

# --- Configuration ---
# Define the paths for the input file, output files.
# !! IMPORTANT: Adjust these paths if necessary to match your directory structure !!

INPUT_FILE="position/hg19.mm10.50bp.gz"
ODD_OUTPUT_FILE="position/hg19.oddchr.mm10.50bp.gz"
EVEN_OUTPUT_FILE="position/hg19.evenchr.mm10.50bp.gz"

# --- Pre-checks ---

# Check if the input file exists
if [ ! -f "${INPUT_FILE}" ]; then
  echo "Error: Input file '${INPUT_FILE}' not found." >&2
  exit 1
fi

# Ensure the output directory exists (create if it doesn't)
# Extracts the directory part from one of the output files
OUTPUT_DIR=$(dirname "${ODD_OUTPUT_FILE}")
mkdir -p "${OUTPUT_DIR}"
if [ $? -ne 0 ]; then
  echo "Error: Could not create output directory '${OUTPUT_DIR}'." >&2
  exit 1
fi

# --- Execution and Timing ---

echo "Starting chromosome split for ${INPUT_FILE}..."
echo "Outputting odd chromosomes to: ${ODD_OUTPUT_FILE}"
echo "Outputting even chromosomes to: ${EVEN_OUTPUT_FILE}"

# Use curly braces { ... } to group the commands
# Apply the 'time' command to the group
# Redirect stderr (where 'time' outputs) to stdout (&1) so it's captured by nohup's redirection
time {
    # Pipeline for ODD chromosomes
    gzip -cd "${INPUT_FILE}" | \
    awk -v OFS="\t" '{sub("chr", "" ,$1); print $0}' | \
    awk -v OFS="\t" '$1 % 2 {print "chr"$0}' | gzip > "${ODD_OUTPUT_FILE}"

    # Check if the first command failed (e.g., awk error, gzip error)
    if [ $? -ne 0 ]; then
        echo "Error during odd chromosome processing." >&2
        # Decide if you want to exit or continue
        # exit 1 # Uncomment to stop if odd processing fails
    fi

    # Pipeline for EVEN chromosomes
    gzip -cd "${INPUT_FILE}" | \
    awk -v OFS="\t" '{sub("chr", "" ,$1); print $0}' | \
    awk -v OFS="\t" '($1 % 2 == 0) {print "chr"$0}' | gzip > "${EVEN_OUTPUT_FILE}"

    # Check if the second command failed
    if [ $? -ne 0 ]; then
        echo "Error during even chromosome processing." >&2
        # exit 1 # Uncomment to stop if even processing fails
    fi

} 2>&1

echo "Chromosome split process finished."

