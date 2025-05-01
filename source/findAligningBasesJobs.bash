#!/bin/bash

# --- Configuration ---
# Path to the LECIF source directory
LECIF_SOURCE_DIR="lecif-project/source"
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
# --- End Configuration ---

# Check if the python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at $PYTHON_SCRIPT"
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

echo "Starting processing of axtNet files..."

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

        echo "Processing $base_filename -> $output_filename"

        # Run the python script
        "$PYTHON_EXEC" "$PYTHON_SCRIPT" \
            -a "$axt_file" \
            -m "$MM10_CHROM_SIZES" \
            -o "$output_filename"

        # Optional: Check exit status of the python script
        if [ $? -ne 0 ]; then
            echo "Error processing $base_filename. Check the output/error messages."
        fi
        echo "---" # Separator
    fi
done

echo "Processing complete."
echo "Output files are in $OUTPUT_DIR"