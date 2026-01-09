data_extraction_prompt = """
You are given two radiology reports from a CT study and a subsequent PET/CT study. Please extract specific data points below and present them in a **strictly structured JSON format**.

------
# 1. Data Extraction Tasks

## 1.1. CT Study Region

Which regions were scanned in the CT study report. Just list regions that were scanned in the first CT-only report not the subsequent PET/CT report.

Format:
"CT_Regions": [
    "head/brain",
    "chest/lung",
    "neck",
    "pelvis",
    "abdomen",
]

## 1.2. CT Contrast Agent

Which contrast agent was used in the CT study report. Just list the contrast agent used in the first CT-only report not the subsequent PET/CT report. Use "None" if no contrast agent was used. 

Format:
"CT_Contrast_Agent": "Iodine" or "None"


## 1.3. Lung Nodules
Extract all nodules mentioned in the **lung region**. For each nodule, include:
  - **size_mm**: numeric value in millimeters (convert from cm to mm if needed).
  - **location**: choose from { "right upper lobe", "right middle lobe", "right lower lobe", "left upper lobe", "left lower lobe" }. If not specific, leave `""`. If it's described as e.g. "lingular," you may standardize to "left upper lobe." If uncertain, leave as an empty string `""`.
  - **Slice_number**: if explicitly mentioned (e.g., "image 78" or "slice 5"). Otherwise, leave empty.

Format:

"Lung_Nodules": [
{
"size_mm": "",
"location": "",
"Slice_number": ""
},
...
]

------

## 1.4. Lung Hypermetabolic Regions
For any **hypermetabolic activity** in the lung region, list each region separately:
  - **size_mm**: numeric size in mm if stated.
  - **location**: choose from { "right upper lobe", "right middle lobe", "right lower lobe", "left upper lobe", "left lower lobe" }. If not specific, leave `""`.
  - **SUV**: the maximum SUV if provided (as a string), otherwise `""`.

Format:

"Lung_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
},
...
]

------

## 1.5. Lymph Nodes Hypermetabolic Regions
Extract hypermetabolic lymph nodes. For each node:
  - **size_mm**: short-axis dimension if given in mm, else `""`.
  - **location**: choose from { "mediastinal", "aortic", "cervical", "axillary" }. If none of these apply or location is unclear, use `"other lymph nodes"`.
  - **SUV**: numeric SUV if provided, else `""`.

Format:

"Lymph_Nodes_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
},
...
]

------

## 1.6. Other Hypermetabolic Regions
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

"Other_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
},
...
]

------

## 1.7. Tracer Used
Record the exact text for the PET tracer injected, e.g. "8.1 mCi F-18 FDG." If not found, leave `""`.

"PET_Tracer": ""

------

## 1.8. PET StudyScan Region
Record the described coverage of the PET scan, e.g. "skull base to thigh" or "vertex to feet." If none is provided, leave `""`.

"PET_Scan_Region": ""

------

## 1.9. PET Study Blood Glucose Level
Record as "XXX mg/dL" if provided. Otherwise, leave `""`.

"PET_Blood_Glucose_Level": ""

------

## 1.10. PET Study Waiting Time
If the radiologist mentions how long after tracer injection the imaging started, record in the format "XX min." If not mentioned, leave `""`.

"PET_Waiting_Time": ""

------



## 2. Classification Tasks

### 2.1 Clinical Reason
You must categorize the **reason for the scans** into exactly **one** of the following classes:
   - **Indeterminate Pulmonary Nodule**: if the report indicates the scan is specifically for evaluating a suspicious or indeterminate lung nodule.
   - **Staging of New Primary Cancer**: if the report indicates the patient has a newly diagnosed malignancy (other than a lung nodule) and the scan is for staging.
   - **Cancer Patient Monitoring**: if the patient already has a known cancer and the scan is for restaging, therapy monitoring, or follow-up.
   - **Suspicious Symptom Evaluation**: if the scan is performed to investigate new, concerning symptoms that may suggest malignancy (e.g., weight loss, hemoptysis, etc.) but not specifically for a known nodule or known active cancer.
   - **Other**: if none of the above apply (e.g., infection/inflammation evaluation, etc.).

### 2.2 Primary Diagnosis
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

> **Note:** If there is more than one cancer type, choose the one that appears to be the primary driver of the current imaging study. If it truly cannot be determined, "Other Cancer" is acceptable.


------

## 11. Historical or Comparison Measurements
When the report includes older sizes or SUVs (e.g., "formerly 1.2 by 0.8 cm"), **use the most recent** measurements and SUV in your JSON output. Ignore old values.

------

## 12. Final JSON Schema
Your final output **must** adhere to this exact JSON structure (and **only** this structure, with no extra keys):

{
"CT_Regions": [],
"CT_Contrast_Agent": "",
"Lung_Nodules": [
{
"size_mm": "",
"location": "",
"Slice_number": ""
}
],
"Lung_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
}
],
"Lymph_Nodes_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
}
],
"Other_Hypermetabolic_Regions": [
{
"size_mm": "",
"location": "",
"SUV": ""
}
],
"PET_Tracer": "",
"PET_Scan_Region": "",
"PET_Blood_Glucose_Level": "",
"PET_Waiting_Time": "",
"Clinical_Reason": "",
"Primary_Diagnosis": ""
}

------
## 13. Output Requirements

1. **Do not** output any text other than this JSON structure (no extra commentary).  
2. **Do not** include any keys beyond the ones in the final JSON schema.  
3. **For missing data**, use an empty string `""` for string fields or empty arrays `[]` where a list is expected.  
4. **Use proper categories** as specified for each region and for the diagnosis. Only revert to "other" if you cannot match the item to the pre-defined categories.  
5. If multiple distinct nodules or hypermetabolic lesions are described, each should be listed as a **separate object** in its corresponding array.

------

### Task
Given two radiology reports from a CT study and a subsequent PET/CT study, apply the instructions above and produce **exactly one valid JSON** object (and no additional text). This JSON must contain all relevant extracted information, adhering to the categories and data formats described.


"""