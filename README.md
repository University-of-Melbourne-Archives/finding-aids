## 🚀 Usage: Gemini Model (`scr/gemini.py`)

This section provides a step-by-step guide to setting up and running the `gemini.py` script to process your PDF finding aids.

### Step 1: Get Your Google API Key

1.  Go to **Google AI Studio** (https://aistudio.google.com/).
2.  Sign in with your Google account and navigate to the **"Get API key"** section.
3.  Create a new API key.
4.  Copy this key. It is a long string of letters and numbers.

### Step 2: Set Your API Key Environment Variable

Instead of using a `.env` file, this method sets your API key permanently so it's available in all your terminal sessions.

1.  **Find your shell's configuration file.**
    * If you use **`zsh`** (the default on modern macOS), your file is `~/.zshrc`.
    * If you use **`bash`** (common on Linux or older macOS), your file is `~/.bashrc`.

2.  **Open the file in a text editor.** For example, if you use `zsh`:
    ```bash
    nano ~/.zshrc
    ```

3.  **Add the key to the file.**
    Go to the very bottom of the file and add the following line, pasting your key inside the quotes:
    ```bash
    export GOOGLE_API_KEY='YOUR_API_KEY_GOES_HERE'
    ```

4.  **Save and exit the editor.**
    * In `nano`: Press `Ctrl+O` to Write Out, `Enter` to confirm, and `Ctrl+X` to exit.

5.  **Load the changes.**
    Run the `source` command on the file you just edited to apply the changes to your *current* terminal session.
    ```bash
    # If you used .zshrc
    source ~/.zshrc
    
    # If you used .bashrc
    source ~/.bashrc
    ```
    Your API key will now be set automatically in every new terminal you open.
    
   
### Step 3: Create Your Conda Environment

We recommend using `conda` to manage your Python environment and dependencies.

1.  **Create a new `conda` environment:**
    From your terminal, create an environment named `finding-aids` (e.g., with Python 3.10).
    ```bash
    conda create -n finding-aids python=3.10
    ```

2.  **Activate the environment:**
    ```bash
    conda activate finding-aids
    ```
    (Your terminal prompt should now show `(finding-aids)`.)

3.  **Install dependencies:**
    This script requires several Python libraries. Use `pip` to install them into your active `conda` environment.
    ```bash
    pip install google-generativeai pandas pypdf tqdm xlsxwriter
    ```

### Step 4: Run the Script

Since your API key is now set permanently (from Step 2), you just need to make sure you are in your `conda` environment and then run the script.

1.  **Activate your environment (if not already active):**
    ```bash
    conda activate finding-aids
    ```
    (Your terminal prompt should show `(finding-aids)`.)

2.  **Run the script:**
    You can run the script with a basic command or use optional flags to customize its behavior.

    #### Command-Line Arguments

    Here is a breakdown of all the available parameters for `gemini.py`:

    * `--pdf "path/to/file.pdf"`
        **(Required)** The full path to the input finding aid PDF you want to process.
    * `--out_json "path/to/output.json"`
        **(Required)** The full path where you want to save the hierarchical JSON file produced by the model.
    * `--out_xlsx "path/to/output.xlsx"`
        **(Required)** The full path where you want to save the final, flattened Excel file.
    * `--model_name "model-id"`
        **(Optional)** Lets you specify which Gemini model to use.
        * **Default:** `models/gemini-2.5-flash`
        * **To change:** You can use a different model, like `models/gemini-pro`, by adding the flag: `--model_name "models/gemini-pro"`
    * `--temperature 0.5`
        **(Optional)** Controls the "creativity" or randomness of the model's output.
        * **Default:** `0.3`
        * **Impact:** A lower value (e.g., `0.1`) makes the output more deterministic and consistent. A higher value (e.g., `0.7`) makes it more creative but also potentially less accurate. For this task, a low value is recommended.
    * `--pages_per_chunk 5`
        **(Optional)** The number of PDF pages to process in a single API call.
        * **Default:** `5`
        * **Impact:** A smaller number (e.g., `2`) uses less memory and is less likely to hit API token limits, but the overall run will be slower. A larger number (e.g., `10`) is faster but may fail if the chunk is too large.
    * `--pages "N-M"`
        **(Optional)** Processes only a specific range of pages.
        * **Default:** `None` (processes the entire document).
        * **Impact:** This is extremely useful for testing. You can run `--pages "5-10"` to process only pages 5 through 10, saving time and cost.

    ---
    #### 📝 Basic Example (processing the whole PDF with defaults):

    ```bash
    python scr/gemini.py \
        --pdf "path/to/your/document.pdf" \
        --out_json "output/results.json" \
        --out_xlsx "output/results.xlsx"
    ```

    #### 🔬 Advanced Example (testing pages 5-10 with higher temperature):

    ```bash
    python scr/gemini.py \
        --pdf "path/to/your/document.pdf" \
        --out_json "output/results_pages_5-10.json" \
        --out_xlsx "output/results_pages_5-10.xlsx" \
        --pages "5-10" \
        --temperature 0.5 \
        --pages_per_chunk 2
    ```
### Step 5: Post-Process Date Ranges (`postprocess_date_range.py`)

After the AI has created the `results.xlsx` file, the `Dates` column contains raw text (e.g., "1910-1915" or "14-15 Oct 1839").

This script is a crucial second step that reads that Excel file, intelligently parses the raw date text, and adds six new columns for sortable start and end dates.

**This script adds:**
* `Start_Date`
* `End_Date`
* `Start_Date_Sortable`
* `End_Date_Sortable`
* `Start_Date_Complete`
* `End_Date_Complete`

It will overwrite your existing Excel file but **creates a backup** (e.g., `results.xlsx.bak`) by default.

#### How to Run


 1. **Run the script:**
    You only need to point it at the Excel file you created in Step 4.

    ```bash
    python scr/postprocess_date_range.py --xlsx "output/results.xlsx"
    ```
    
    * **To run without a backup:**
        ```bash
        python scr/postprocess_date_range.py --xlsx "output/results.xlsx" --no_backup
        ```
    * **To specify a sheet name (optional):**
        ```bash
        python scr/postprocess_date_range.py --xlsx "output/results.xlsx" --sheet "MySheetName"
        ```
### Addtional: Budget and Cost Estimation 💰

Using the Google Gemini API is **not free** and is billed based on usage.

* **Pricing Model:** Costs are calculated based on the number of "tokens" processed (a token is roughly a word or part of a word). You are billed for both the **input tokens** (the document pages you send) and the **output tokens** (the JSON the model generates).
* **Official Pricing:** For the most up-to-date information, please review the official **[Gemini API Pricing Page](https://ai.google.dev/pricing)**.
* **Monitor Your Costs:** It is **strongly recommended** to set up **billing alerts** and **quotas** in your Google Cloud Project (which is linked to your AI Studio account). This will prevent unexpected charges and help you keep your spending in check, especially when processing large documents.
