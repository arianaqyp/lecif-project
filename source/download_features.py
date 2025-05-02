import pandas as pd
import requests
import os
import time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# --- Configuration ---

# Base directory where the species/data type directories will be created
BASE_OUTPUT_DIR = "feature/raw"

# Mapping from CSV file parts (from SupplementaryTable1) to target directories
# the CSV files are in a subdirectory named 'lecif-project/table/' relative to the script
CSV_DIR_MAP = {
    "table/SupplementaryTable1.xlsx - 1b. Human DNase-seq, ChIP-seq.csv": "hg19_DNaseChIPseq",
    "table/SupplementaryTable1.xlsx - 1c. Human ChromHMM.csv": "hg19_ChromHMM",
    "table/SupplementaryTable1.xlsx - 1d. Human CAGE.csv": "hg19_CAGE",
    "table/SupplementaryTable1.xlsx - 1e. Human RNA-seq.csv": "hg19_RNAseq",
    "table/SupplementaryTable1.xlsx - 1f. Mouse DNase-seq, ChIP-seq.csv": "mm10_DNaseqChIPseq",
    "table/SupplementaryTable1.xlsx - 1g. Mouse ChromHMM.csv": "mm10_ChromHMM",
    "table/SupplementaryTable1.xlsx - 1h. Mouse CAGE.csv": "mm10_CAGE",
    "table/SupplementaryTable1.xlsx - 1i. Mouse RNA-seq.csv": "mm10_RNAseq",
}

# Column name in the CSV files containing the download links
URL_COLUMN_NAME = "Download link"

# Maximum number of concurrent downloads
MAX_WORKERS = 10 # Adjust based on your network capacity

# --- End Configuration ---

def download_file(url, target_dir):
    """Downloads a single file from a URL into the target directory."""
    if pd.isna(url) or not url.strip():
        return url, "Skipped (empty URL)"

    try:
        # Get filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
             # Handle cases where filename might be tricky (e.g., redirects hiding it)
             # Fallback using a generic name or trying to get it from headers
             filename = f"downloaded_{int(time.time()*1000)}" # Simple fallback
             print(f"Warning: Could not determine filename for {url}. Using fallback: {filename}")


        output_path = os.path.join(target_dir, filename)

        # Check if file already exists
        if os.path.exists(output_path):
            return url, f"Skipped (already exists: {filename})"

        # Download the file
        response = requests.get(url, stream=True, allow_redirects=True, timeout=60)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Write file content
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return url, f"Success ({filename})"

    except requests.exceptions.RequestException as e:
        return url, f"Failed ({e})"
    except Exception as e:
        return url, f"Failed (Unexpected error: {e})"

def main():
    """Main function to read CSVs and trigger downloads."""
    print(f"Starting download process. Files will be saved under '{BASE_OUTPUT_DIR}'.")
    print("Please ensure you have 'pandas' and 'requests' installed (`pip install pandas requests`).")
    print("-" * 30)

    # Use ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        total_files_to_download = 0
        total_files_processed = 0

        for csv_path, dir_name in CSV_DIR_MAP.items():
            target_directory = os.path.join(BASE_OUTPUT_DIR, dir_name)
            print(f"\nProcessing: {os.path.basename(csv_path)}")
            print(f"Target Directory: {target_directory}")

            # Check if CSV file exists
            if not os.path.exists(csv_path):
                print(f"Warning: CSV file not found at '{csv_path}'. Skipping.")
                continue

            # Create target directory if it doesn't exist
            os.makedirs(target_directory, exist_ok=True)

            try:
                # Read URLs from CSV
                df = pd.read_csv(csv_path)
                if URL_COLUMN_NAME not in df.columns:
                    print(f"Warning: URL column '{URL_COLUMN_NAME}' not found in '{csv_path}'. Skipping.")
                    continue

                urls = df[URL_COLUMN_NAME].dropna().unique().tolist()
                print(f"Found {len(urls)} unique URLs to download.")
                total_files_to_download += len(urls)

                # Submit download tasks to the executor
                for url in urls:
                     if url and isinstance(url, str) and url.strip():
                        futures.append(executor.submit(download_file, url.strip(), target_directory))
                     else:
                        print(f"Warning: Skipping invalid URL entry: {url}")
                        total_files_processed += 1 # Count as processed even if skipped

            except Exception as e:
                print(f"Error reading or processing CSV '{csv_path}': {e}")

        print(f"\nSubmitted {len(futures)} download tasks across all files.")
        print("Waiting for downloads to complete...")

        # Process results as they complete
        for future in as_completed(futures):
            total_files_processed += 1
            url, status = future.result()
            # Simple progress indicator
            progress = f"[{total_files_processed}/{total_files_to_download + (total_files_processed - len(futures))}]" # Adjust total for skipped
            if "Success" in status or "Skipped" in status :
                 print(f"{progress} {status} - {url}")
            else:
                 print(f"{progress} !!! {status} - {url}", file=sys.stderr)


    print("-" * 30)
    print("Download process finished.")

if __name__ == "__main__":
    main()