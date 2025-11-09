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

## Additional: 💰 Budget, Cost-Saving & Research Credits

Using the Google Gemini API is **not free** and is billed based on usage. For academic and research projects, it is crucial to understand the costs and take advantage of available programs.

* **Pricing Model:** Costs are calculated based on the number of "tokens" processed (a token is roughly a word or part of a word). You are billed for both the **input tokens** (the document pages you send) and the **output tokens** (the JSON the model generates).
* **Official Pricing:** For the most up-to-date information, please review the official **[Gemini API Pricing Page](https://ai.google.dev/pricing)**.
* **Monitor Your Costs:** It is **strongly recommended** to set up **billing alerts** and **quotas** in your Google Cloud Project (which is linked to your AI Studio account). This will prevent unexpected charges and help you keep your spending in check.

---
#### Example Cost Calculation (for `gemini-2.5-flash`)

Here is a real-world example using a 3-page finding aid (`64131_mueller ferdinand baron von 6112.pdf`).

**1. Token Estimation:**
We estimate tokens using the rule of thumb: **1 token ≈ 4 characters**.
* **Page 1 (Collection Info):** 893 characters ≈ **223 tokens**
* **Page 2 (Biography):** 2,379 characters ≈ **595 tokens**
* **Page 3 (Records List):** 612 characters ≈ **153 tokens**
* **Average:** 323.67 tokens per page

**2. Pricing (gemini-2.5-flash):**
* **Input Price:** $0.30 per 1 million tokens
* **Output Price:** $2.50 per 1 million tokens

**3. Cost Per Page (Assuming 1:1 Input:Output Ratio):**
* **Page 2 (Dense Page):**
    * Input: (595 / 1,000,000) * $0.30 = $0.0001785
    * Output: (595 / 1,000,000) * $2.50 = $0.0014875
    * **Total: $0.00167** (or 0.167 cents)

**Result:**
* The total cost to process this entire 3-page document is approximately **$0.0027** (about 0.27 US cents).
* Based on this sample, processing a **100-page document** would cost approximately **$0.091** (about 9.1 US cents).
* ⚠️ Important Caveat
This estimate is based only on the average from the 3-page sample. Please do cost estimation based on your real cases.

---
#### Cost-Saving & Research Credits

You can significantly reduce or eliminate these costs by using the following programs.

**1. [Google Cloud $300 Free Trial](https://cloud.google.com/free?utm_source=google&utm_medium=cpc&utm_campaign=na-US-all-en-dr-bkws-all-all-trial-e-dr-1710134&utm_content=text-ad-none-any-DEV_c-CRE_772251307851-ADGP_Hybrid+%7C+BKWS+-+EXA+%7C+Txt-Generic+Cloud-Cloud+Generic-Cloud+Generic-KWID_1180531793889-kwd-1180531793889&utm_term=KW_google+cloud+$300+free+trial-ST_google+cloud+$300+free+trial&gclsrc=aw.ds&gad_source=1&gad_campaignid=23058938048&gclid=CjwKCAiAlMHIBhAcEiwAZhZBUi6D-9qvvyjYZqDSPayGs7P5k44o5sjhOI2pkAWFYIeBSjdtzCaUXxoC0UYQAvD_BwE&hl=en)**
This is the best option for getting started.
* **What It Is:** A one-time credit of **$300 for new Google Cloud customers**.
* **How It Works:** The credits are applied to your account when you first sign up for Google Cloud. They are valid for **90 days**.
* **What It Covers:** You can use these credits to pay for most Google Cloud services, including any usage of the Gemini API through Vertex AI.

**2. [Google Cloud Research Credits](https://edu.google.com/intl/ALL_us/programs/credits/research/?modal_active=none) **
This is the most valuable program for your PhD project, as it is designed specifically to support academic research.
* **What It Is:** A grant of Google Cloud credits to support academic projects.
* **Eligibility:** The program is open to faculty, postdoctoral researchers, and **PhD students** at accredited institutions.
* **Credit Amount:**
    * **PhD Students:** You can apply for **$1,000 in Google Cloud credits per year**.
    * **Faculty/Postdocs:** Can apply for a one-time grant of up to $5,000.
* **How to Apply:** You must **apply for the credits** by submitting a short proposal that outlines your research, the tools you plan to use, and your project's goals.

**3. Gemini API Free Tiers**
Even without the programs above, there are free ways to use Gemini.
* **Google AI Studio:** The AI Studio web interface is **free to use** for prototyping and testing your prompts.
* **API Free Tier:** The `gemini-2.5-flash` model has a perpetual **free tier**. You get a free quota of requests **(250 per day)** and tokens **(250,000 per minute)** before you are charged anything. This is ideal for ongoing development and small tests.


