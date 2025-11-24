## 🚀 Usage: GenAI Finding Aids Pipeline (Gemini + OpenAI Support)
This guide explains how to set up the environment, configure API keys, run the OCR pipeline, and post-process date ranges for finding aid PDFs.

### Step 1: Create Your Conda Environment

We recommend using `conda` to manage your Python environment and dependencies.

1.  **Create a new `conda` environment:**
    From your terminal, create an environment named `finding-aids` (e.g., with Python 3.10).
    ```bash
    conda env create -f environment.yml
    ```

2.  **Activate the environment:**
    ```bash
    conda activate finding-aids
    ```
    (Your terminal prompt should now show `(finding-aids)`.)

    
### 🔑 Step 2: Obtain Your API Keys
### 2.1 Google Gemini API Key
1.  Go to **Google AI Studio** (https://aistudio.google.com/).
2.  Sign in with your Google account and navigate to the **"Get API key"** section.
3.  Create a new API key.
4.  Copy this key. It is a long string of letters and numbers.

### 2.2 OpenAI API Key (GPT-4o, GPT-5.1, Mini Models)

1. Visit: https://platform.openai.com
2. Generate a new key
3. Copy the key (starts with sk-...)

### Step 3: Set Your API Key Environment Variable

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
    # GEMINI GPT
    export GOOGLE_API_KEY='YOUR_API_KEY_GOES_HERE'
    # OpenAI GPT
    export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
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
    

## 🧠 Step 4: Run the OCR Pipeline (`src.main`)

The main entrypoint is:

```bash
python -m src.main
```
### 4.1 Required Arguments

| Argument      | Description |
|---------------|-------------|
| `--pdf`       | Path to the PDF finding aid |
| `--out_raw`   | Output folder for raw model responses |
| `--out_json`  | Output folder for flattened JSON |
| `--out_csv`   | Output folder for CSV |
| `--out_xlsx`  | Output folder for XLSX |
| `--out_log`   | Logs |

The script automatically creates directory structures like:

```bash
output/<type>/<engine>/<model_tag>/<pdf_stem>/
```

### 4.2 Optional Arguments

| Argument           | Description |
|--------------------|-------------|
| `--engine`         | `{gemini, openai}` — default: `gemini` |
| `--model_name`     | e.g., `models/gemini-2.5-flash`, `gpt-5.1`, `gpt-4o` |
| `--pages_per_chunk`| Default: `5` |
| `--pages`          | e.g. `"1-10"` to limit to page ranges |
| `--temperature`    | Default: `0.3` — recommended for OCR accuracy |
| `--max_retries`    | Default: `3` — retry count for API errors |



###📌 Step 4.3 Examples

▶ Example: Gemini, full PDF
```bash
python -m src.main \
  --pdf "/path/to/document.pdf" \
  --out_raw "data/output/raw" \
  --out_json "data/output/json" \
  --out_csv "data/output/csv" \
  --out_xlsx "data/output/xlsx" \
  --out_log "data/output/logs" \
  --engine gemini \
  --model_name "models/gemini-2.5-flash"
```

▶ Example: OpenAI GPT-5.1, pages 1–10 only
```bash
python -m src.main \
  --pdf "/path/to/document.pdf" \
  --out_raw "data/output/raw" \
  --out_json "data/output/json" \
  --out_csv "data/output/csv" \
  --out_xlsx "data/output/xlsx" \
  --out_log "data/output/logs" \
  --engine openai \
  --model_name "gpt-5.1" \
  --pages "1-10"
```

Example output paths
```bash
data/output/raw/openai/gpt-5_1/<pdf_stem>/
data/output/json/openai/gpt-5_1/<pdf_stem>_gpt-5_1.json
data/output/csv/openai/gpt-5_1/<pdf_stem>_gpt-5_1.csv
data/output/xlsx/openai/gpt-5_1/<pdf_stem>_gpt-5_1.xlsx
data/output/logs/openai/gpt-5_1/<pdf_stem>/
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
* ⚠️ **Important Caveat**. This estimate is based only on the average from the 3-page sample. Please do cost estimation based on your real cases.

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


