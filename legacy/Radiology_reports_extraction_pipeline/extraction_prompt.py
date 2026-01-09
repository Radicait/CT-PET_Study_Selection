data_extraction_prompt = """
You are given a radiology report from a PET study. Please extract specific data points and present them in a **strictly structured JSON format**.

------
## 1. Classification Tasks

### 1.1 Clinical Reason
You must categorize the **reason for the scan** into exactly **one** of the following classes:
   - **Indeterminate Pulmonary Nodule**: if the report indicates the scan is specifically for evaluating a suspicious or indeterminate lung nodule.
   - **Staging of New Primary Cancer**: if the report indicates the patient has a newly diagnosed malignancy (other than a lung nodule) and the scan is for staging.
   - **Cancer Patient Monitoring**: if the patient already has a known cancer and the scan is for restaging, therapy monitoring, or follow-up.
   - **Suspicious Symptom Evaluation**: if the scan is performed to investigate new, concerning symptoms that may suggest malignancy (e.g., weight loss, hemoptysis, etc.) but not specifically for a known nodule or known active cancer.
   - **Other**: if none of the above apply (e.g., infection/inflammation evaluation, etc.).

### 1.2 Primary Diagnosis
Based on the final impression and context of the report, select exactly **one** of the following:
   - **Primary Lung Cancer**
   - **Metastatic Lung Cancer** (lung cancer with metastases)
   - **Breast Cancer**
   - **Melanoma**
   - **Lymphoma**
   - **Head and Neck Cancer**
   - **Gastrointestinal Cancer** (e.g., colon, rectum, stomach, esophagus, pancreas)
   - **Genitourinary Cancer** (e.g., prostate, bladder, kidney)
   - **Gynecologic Cancer** (e.g., ovarian, uterine, cervical)
   - **Other Cancer** (any cancer not covered above, or details insufficient)
   - **No Cancer**

> **Note:** If there is more than one cancer type, choose the one that appears to be the primary driver of the current imaging study. If it truly cannot be determined, “Other Cancer” is acceptable.

------

## 2. Lung Nodules
Extract all nodules mentioned in the **lung region**. For each nodule, include:
  - **size_mm**: numeric value in millimeters (convert from cm to mm if needed).
  - **location**: choose from { "right upper lobe", "right middle lobe", "right lower lobe", "left upper lobe", "left lower lobe" }. If not specific, leave `""`. If it’s described as e.g. “lingular,” you may standardize to “left upper lobe.” If uncertain, leave as an empty string `""`.
  - **Slice_number**: if explicitly mentioned (e.g., “image 78” or “slice 5”). Otherwise, leave empty.

Format:

“Lung_Nodules”: [
{
“size_mm”: “”,
“location”: “”,
“Slice_number”: “”
},
…
]

------

## 3. Lung Hypermetabolic Regions
For any **hypermetabolic activity** in the lung region, list each region separately:
  - **size_mm**: numeric size in mm if stated.
  - **location**: choose from { "right upper lobe", "right middle lobe", "right lower lobe", "left upper lobe", "left lower lobe" }. If not specific, leave `""`.
  - **SUV**: the maximum SUV if provided (as a string), otherwise `""`.

Format:

“Lung_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
},
…
]

------

## 4. Lymph Nodes Hypermetabolic Regions
Extract hypermetabolic lymph nodes. For each node:
  - **size_mm**: short-axis dimension if given in mm, else `""`.
  - **location**: choose from { "mediastinal", "aortic", "cervical", "axillary" }. If none of these apply or location is unclear, use `"other lymph nodes"`.
  - **SUV**: numeric SUV if provided, else `""`.

Format:

“Lymph_Nodes_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
},
…
]

------

## 5. Other Hypermetabolic Regions
For **any hypermetabolic region** that is **not** in the lung or lymph nodes, categorize location into **one** of the following if possible:
   - "brain"
   - "liver"
   - "bone"
   - "adrenal glands"
   - "kidney"
   - "colon"
   - "pancreas"
   - "head/neck region"
   - "pelvis"
   - "soft tissue"
   - "other organ locations" (if you cannot map it to the above)

Also include:
  - **size_mm**: numeric size if mentioned, else `""`.
  - **SUV**: numeric SUV if available, else `""`.

Format:

“Other_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
},
…
]

------

## 6. Tracer Used
Record the exact text for the PET tracer injected, e.g. “8.1 mCi F-18 FDG.” If not found, leave `""`.

“Tracer”: “”

------

## 7. Scan Region
Record the described coverage of the PET scan, e.g. “skull base to thigh” or “vertex to feet.” If none is provided, leave `""`.

“Scan_Region”: “”

------

## 8. Blood Glucose Level
Record as “XXX mg/dL” if provided. Otherwise, leave `""`.

“Blood_Glucose_Level”: “”

------

## 9. Waiting Time
If the radiologist mentions how long after tracer injection the imaging started, record in the format “XX min.” If not mentioned, leave `""`.

“Waiting_Time”: “”

------

## 10. Was a CT Scan Also Done
Provide “Yes” if a CT scan was performed (including if mentioned only for attenuation correction). Otherwise, “No.”

“CT_Scan”: “”

------

## 11. Historical or Comparison Measurements
When the report includes older sizes or SUVs (e.g., “formerly 1.2 by 0.8 cm”), **use the most recent** measurements and SUV in your JSON output. Ignore old values.

------

## 12. Final JSON Schema
Your final output **must** adhere to this exact JSON structure (and **only** this structure, with no extra keys):

{
“Clinical_Reason”: “”,
“Primary_Diagnosis”: “”,
“Lung_Nodules”: [
{
“size_mm”: “”,
“Region”: “”,
“Slice_number”: “”
}
],
“Lung_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
}
],
“Lymph_Nodes_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
}
],
“Other_Hypermetabolic_Regions”: [
{
“size_mm”: “”,
“location”: “”,
“SUV”: “”
}
],
“Tracer”: “”,
“Scan_Region”: “”,
“Blood_Glucose_Level”: “”,
“Waiting_Time”: “”,
“CT_Scan”: “”
}

------
## 13. Output Requirements

1. **Do not** output any text other than this JSON structure (no extra commentary).  
2. **Do not** include any keys beyond the ones in the schema.  
3. **For missing data**, use an empty string `""` for string fields or empty arrays `[]` where a list is expected.  
4. **Use proper categories** as specified for each region and for the diagnosis. Only revert to “other” if you cannot match the item to the pre-defined categories.  
5. If multiple distinct nodules or hypermetabolic lesions are described, each should be listed as a **separate object** in its corresponding array.

------

### Task
Given a radiology PET/CT report, apply the instructions above and produce **exactly one valid JSON** object (and no additional text). This JSON must contain all relevant extracted information, adhering to the categories and data formats described.

---

"""