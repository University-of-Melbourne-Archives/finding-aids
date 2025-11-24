# 📤 Output Files & Column Descriptions

After running the OCR pipeline, several output formats are generated. Each output preserves different layers of structure and is used for a different stage of archival processing.

---

## 1. Raw TXT Output — `{raw/}`

Each chunk/page of the PDF produces a `{*.txt}` file containing the *exact* LLM response:

- unstructured extracted text  
- raw field/value predictions  
- confidence strings like `"confidence: 4/5"`  
- any formatting or linebreaks as returned by the model  

**Purpose:** debugging, auditing, understanding what the OCR model actually produced.

---

## 2. Structured JSON Output — `{json/}`

One `{*.json}` file per PDF.  
Contains a list `{items: [ ... ]}` where each element is a single archival record with OCR fields:

Examples of JSON fields:

```bash
{
  "items": [
    {
      "page": {
        "chunk": "1",
        "page_number": "1-5"
      },
      "group": {
        "value": "",
        "confidence": null
      },
      "group_notes": {
        "value": "",
        "confidence": null
      },
      "series": {
        "value": "",
        "confidence": null
      },
      "series_notes": {
        "value": "",
        "confidence": null
      },
      "unit": {
        "value": "",
        "confidence": null
      },
      "finding_aid_reference_raw": {
        "value": "",
        "confidence": null
      },
      "text": {
        "value": "NAME: R. E. LEWIS, ORR & GIBSON.",
        "confidence": "5/5"
      },
      "start_date_original": {
        "value": "",
        "confidence": null
      },
      "end_date_original": {
        "value": "",
        "confidence": null
      },
      "start_date_formatted": {
        "value": "",
        "confidence": null
      },
      "end_date_formatted": {
        "value": "",
        "confidence": null
      },
      "annotations": []
    },...
]
}
```


**Purpose:** structured machine-readable extraction for indexing or pipelines.

---

## 3. Flattened XLSX / CSV Output — `{xlsx/}`, `{csv/}`

Tabular representation of every archival item.  
Each row corresponds to a single described entry in the finding aid.

Contains all OCR fields plus post-processed hierarchy + inheritance columns.

---

# 📑 Column Descriptions

Below is the meaning of each column created by the OCR + post-process pipeline.

---

## 🔹 Core OCR Fields

- **finding_aid_reference_raw_value**  
  Raw reference as printed in the finding aid. Examples: `5.`, `(3)`, `6.(1)`, `2/3/1`.

- **unit_value**  
  Printed Unit/Box number. Useful for collection findings.

- **group_value**  
  Printed Group header (“5”, “7”, etc.).

- **series_value**  
  Printed Series name.

- **series_notes_value**  
  Notes directly associated with a printed Series heading.

- **text_value**  
  Text of the archival entry.

- **date_start_original_value**, **date_end_original_value**

  The raw dates extract by OCR. The dates may not exsit.
  
- **date_start_formatted_value**, **date_end_formatted_value**
  
  Normalized date fields in `YYYY-MM-DD`.

All the filed also continue with another colum `xx_confidence` display the GenAI OCR confidence.

---

# 🌲 Post-Processing Columns  — `{final/}`

These columns are produced by the hierarchy builder and inheritance modules.

---

### **hierarchy_path**  
Numeric tuple representing the archival tree path.

Examples:
- `(5,)`
- `(5, 1)`
- `(10, 4, 7)`
- `(101, 3)`

Created from finding-aid references using:
- numbers (`5.`)
- parentheses (`(3)`)
- composite (`6.(1)`)
- slash paths (`2/1/3`)
- fuzzy parents (`106.?`, `45a`, `25??`)

---

### **unit_value_inherited**  
Forward-filled Unit.  
If a row has no unit, it receives the unit of the closest previous row.

Appears immediately after `unit_value`:`unit_value`, `unit_value_inherited`


---

### **group_notes_inherited**  
Group notes inherited from the *nearest previous ancestor* in the hierarchy.

Appears as: `group_notes_value`, `group_notes_inherited`


Forward-only: no future rows influence earlier ones.

---

### **series_value_inherited**, **series_notes_inherited**  
Inherited Series metadata.

Derived from the nearest previous ancestor in the hierarchy that explicitly defines its own series.

Appears as:
`series_value`, `series_value_inherited`, `series_notes_value`, `series_notes_inherited`

---

# 📦 Final Output Structure Example

A typical XLSX/CSV row ordering:

- page_chunck
- page_number
- group_value
- group_notes_value
- group_notes_inherited
- series_value
- series_value_inherited
- series_notes_value
- series_notes_inherited
- unit_value
- unit_value_inherited
- finding_aid_reference_raw_value
- hierarchy_path
- title_value
- description_value
- date_start_original_value
- date_end_original_value
- date_start_formatted_value
- date_end_formatted_value
- annotations


