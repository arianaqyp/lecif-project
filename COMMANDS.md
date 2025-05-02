# Killing the Process Group
You've hit on a common point of confusion with `nohup` and background processes!

Killing the PID associated directly with the `nohup` command itself, or even the initial PID of the shell script started by `nohup`, usually **will not** terminate the child processes (the individual Python jobs) that the script has launched in the background using `&`.

Here's why and how to properly stop everything:

1.  **Why Killing the `nohup` PID Isn't Enough:**
    *   `nohup` essentially detaches your script (`findAligningBasesJobs.bash`) from the controlling terminal and makes it immune to the HUP (hangup) signal, allowing it to run after you log out.
    *   Your script *then* launches multiple Python processes as *its own children* in the background (`... &`).
    *   When you kill the main script's process, the operating system often reparents these orphaned background children (e.g., to the `init` process, PID 1), allowing them to continue running independently.

2.  **How to Reliably Stop All Jobs:**

    You need a way to signal the *entire group* of processes spawned by your script, or target the child processes directly. Here are the common methods:

    *   **Method 1: Kill the Process Group (Recommended)**
        *   When you run a script, it typically starts in its own process group (PGID). All the children it spawns (unless they change their group) belong to the same PGID. Killing the entire process group is the cleanest way to stop the script and all its direct children.
        *   **Steps:**
            1.  **Find the script's PID:** After starting the script with `nohup`, find its Process ID (PID). Be specific to avoid matching other processes.
                ```bash
                # Use pgrep with -f to match the full command line
                pgrep -f "findAligningBasesJobs.bash"
                ```
                Let's say this gives you PID `12345`.
            2.  **Find the Process Group ID (PGID):** Use the script's PID to find its PGID.
                ```bash
                ps -o pgid= -p 12345
                ```
                This will output just the PGID number (e.g., `12340`). Note that the PGID might be the same as the PID, or it might be different.
            3.  **Kill the entire Process Group:** Use `kill` with a negative sign before the PGID. The `--` prevents `kill` from misinterpreting a PGID starting with a hyphen as an option.
                ```bash
                # Replace <PGID> with the actual PGID number found above
                kill -- -<PGID>
                # Example: kill -- -12340
                ```
                This sends a TERM signal (by default) to every process in that group, including your main script and all the backgrounded Python jobs.

    *   **Method 2: Use `pkill` to Target Child Processes**
        *   This method directly targets the child Python processes based on their name or command line. It might leave the main bash script running until it finishes or errors out, but it stops the actual computational work.
        *   **Steps:**
            1.  **Kill processes matching the Python script name:** Use `pkill` with the `-f` flag to match the full command line, which is more specific than just `python`.
                ```bash
                pkill -f "findAligningBases.py"
                ```
                This will find and send a TERM signal to all running processes whose command line contains `findAligningBases.py`.
            2.  **(Optional) Kill the main script:** If the main script doesn't exit after its children are killed (it might be stuck on `wait`), you can kill it separately using its PID found in step 1 of Method 1: `kill 12345`.

**Recommendation:**

Method 1 (killing the process group) is generally the most robust way to ensure you terminate the parent script *and* all the jobs it launched. Method 2 is often simpler to execute if you only care about stopping the Python workers quickly.

Remember to run your script like this:

# 2. To Find aligning genomic regions [DONE]
nohup bash ./source/findAligningBasesJobs.bash > nohup_job.log 2>&1 &
```

This redirects both standard output and standard error to `nohup_job.log` and puts the initial `nohup` process itself into the background.


# 3. To run aggregateAligningBases [RUNNING]
nohup source/aggregateAligningBases position/aligning_bases_by_chrom/ position/hg19.mm10.basepair.gz > log/aggregateAligningBases.log 2>&1 &

# 4. Sample 50bp non-overlapping windows using samplePairs.py.
nohup bash -c '( echo "PID: $$"; time python source/samplePairs.py -i position/hg19.mm10.basepair.gz -o position/hg19.mm10.50bp )' > log/samplePairs.log 2>&1 &

# 5. Split the pairs based on whether the human region lies on an odd or even chromosome (X chromosome counts as even) for later use.
nohup bash -c '( echo "PID: $$"; bash source/splitChroms.bash )' > log/splitChroms.log 2>&1 &

