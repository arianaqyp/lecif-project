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

# Path to the Excel file relative to the script's execution directory
EXCEL_FILE_PATH = "table/SupplementaryTable1.xlsx"

# Mapping from Excel sheet names to target directories
SHEET_DIR_MAP = {
    "1b. Human DNase-seq, ChIP-seq": "hg19_DNaseChIPseq",
    "1c. Human ChromHMM": "hg19_ChromHMM",
    # "1d. Human CAGE": "hg19_CAGE",
    "1e. Human RNA-seq": "hg19_RNAseq",
    "1f. Mouse DNase-seq, ChIP-seq": "mm10_DNaseChIPseq",
    "1g. Mouse ChromHMM": "mm10_ChromHMM",
    # "1h. Mouse CAGE": "mm10_CAGE",
    "1i. Mouse RNA-seq": "mm10_RNAseq",
}

# Column name in the CSV files containing the download links
URL_COLUMN_NAME = "link"

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
    """Main function to read Excel sheets and trigger downloads."""
    start_time = time.time() # Record start time
    print(f"Starting download process. Files will be saved under '{BASE_OUTPUT_DIR}'.")
    # print("Please ensure you have 'pandas', 'requests', and 'openpyxl' installed (`pip install pandas requests openpyxl`).") # Added openpyxl
    print("-" * 30)

    # Construct full path to Excel file and check existence
    full_excel_path = os.path.join(os.getcwd(), EXCEL_FILE_PATH)
    print("Looking for Excel file at:", full_excel_path)
    if not os.path.exists(full_excel_path):
        print(f"Error: Excel file not found at '{full_excel_path}'. Please ensure the file exists and the path is correct.", file=sys.stderr)
        sys.exit(1) # Exit if the main Excel file is missing

    # Use ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        total_files_to_download = 0
        total_files_processed = 0

        for sheet_name, dir_name in SHEET_DIR_MAP.items():
            target_directory = os.path.join(BASE_OUTPUT_DIR, dir_name)
            print(f"Processing Sheet: {sheet_name}")
            print(f"Target Directory: {target_directory}")

            # Create target directory if it doesn't exist
            os.makedirs(target_directory, exist_ok=True)

            try:
                # Read URLs from the specific Excel sheet
                # Make sure you have an engine like 'openpyxl' installed: pip install openpyxl
                df = pd.read_excel(full_excel_path, sheet_name=sheet_name)
                # print(df.head()) # Optional: print head for debugging
                if URL_COLUMN_NAME not in df.columns:
                    print(f"Warning: URL column '{URL_COLUMN_NAME}' not found in sheet '{sheet_name}'. Skipping.")
                    continue

                urls = df[URL_COLUMN_NAME].dropna().unique().tolist()
                print(f"Found {len(urls)} unique URLs to download from sheet '{sheet_name}'.")
                total_files_to_download += len(urls)

                # Submit download tasks to the executor
                for url in urls:
                     if url and isinstance(url, str) and url.strip():
                        futures.append(executor.submit(download_file, url.strip(), target_directory))
                     else:
                        print(f"Warning: Skipping invalid URL entry in sheet '{sheet_name}': {url}")
                        total_files_processed += 1 # Count as processed even if skipped

            except Exception as e:
                print(f"Error reading or processing sheet '{sheet_name}' from '{full_excel_path}': {e}", file=sys.stderr)

        if not futures:
             print("No valid URLs found to download across all specified sheets.")
             print("-" * 30)
             print("Download process finished (no tasks executed).")
             return # Exit early if no downloads were submitted

        print(f"Submitted {len(futures)} download tasks across all sheets.")
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
    end_time = time.time() # Record end time
    duration = end_time - start_time
    print(f"Download process finished in {duration:.2f} seconds.")

if __name__ == "__main__":
    main()