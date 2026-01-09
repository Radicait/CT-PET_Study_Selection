# Gradient Data Structure

# Raw data obtained from gradient

They provide a folder with many PET/CT studies. The folder is organized similar to the following:

```
root_folder = '/Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/'
sub_folder = <PatientID>/<AccessionNumber>/studies/<several_sub_folders>/<DICOM_files>
```

For example this is a folder containing a series of dicom files:

```
/Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/29005/54400
```

Each of such folders contains a certain modality (e.g. CT, PET, etc.) or post-processed images from the patient and study. For example the following study contains the following folders and in each folder there will be several dcm files related to that modality or image set series. The dicom metadata files inside the folder contains details about the image set. Here are an example of the subfolders and the dicom tag StudyDescription:

```
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/29005/54400
Series Description: CT IMAGES
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/37184/02316
Series Description: SCOUT
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/18903/31965
Series Description: REFORMATTED
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/91461/96772
Series Description: PET NAC
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/12160/40022
Series Description: PET AC
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/81398/40868
Series Description: MIP
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/94202/04165
Series Description: REFORMATTED
Final folder: /Users/sina/Downloads/sinaradicaitcom-defaultproject-14jan2025-R1/GRDNB4YYQ09ROXZM/GRDN0TZM04W2P34Q/studies/74581/46479/49535/19221
Series Description: REFORMATTED
```

