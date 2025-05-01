#!/bin/bash

# Base URL for the axtNet files
BASE_URL="https://hgdownload.cse.ucsc.edu/goldenpath/hg19/vsMm10/axtNet/"

# Directory to save the downloaded files
OUTPUT_DIR="axtNet_files"

# Create the output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Starting download of axtNet files to $OUTPUT_DIR..."

# Loop through chromosomes 1-22
for i in {1..22}
do
  FILENAME="chr${i}.hg19.mm10.net.axt.gz"
  FILE_URL="${BASE_URL}${FILENAME}"
  echo "Downloading $FILENAME..."
  curl -o "${OUTPUT_DIR}/${FILENAME}" "$FILE_URL"
  if [ $? -ne 0 ]; then
    echo "Error downloading $FILENAME. Please check the URL or your connection."
  fi
done

# Download chromosome X file
FILENAME_X="chrX.hg19.mm10.net.axt.gz"
FILE_URL_X="${BASE_URL}${FILENAME_X}"
echo "Downloading $FILENAME_X..."
curl -o "${OUTPUT_DIR}/${FILENAME_X}" "$FILE_URL_X"
if [ $? -ne 0 ]; then
    echo "Error downloading $FILENAME_X. Please check the URL or your connection."
fi

echo "Download complete."