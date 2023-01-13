# HCI574-grader
Canvas integrated semi-automatic grading (python based) using nbgrader for grading HCI574 assignments

This captures the file system structure required by nbgrader (folders) __but w/o content!__
Also contains a help folder (HCI574 ReadMe), python source code in nbgarder_canvas_tool and some config type files/

This is only meant as a way to quickly set up a new/empty folder that contains everything except actual nbgrader folder content. Theoretically, after nbgrader is set up, only the source notebooks need to be copied over from the last year and HCI574-grader needs to be renamed HC574_HWXX and used in the config files. 

#### Notes:
- Need to better specify how to get nbgrader installed on Windows, which will always by "my" version for running the create assignment portion of nbgrader
- the requirements.txt has specific version requirements and is probably outdated. It also fails for some packages on Windows
- As the course does no longer use conda, neither should the installation here.



-----------------------------------
##### Old (2020, 2022) Readme first:
HCI574 ReadMe folder contains all the info about how to run things
Start with Readme.md in the HCI574 ReadMe folder

For a new year, autograded, exchange, feedback and release can be emptyied and the gradebook.db database file can be deleted.

Do NOT empty source, as it contains the master code for all HWs!
(hmtl contains html renderings of the with-solution notebooks for the TA)

nbgrader_canvas_tool contains the python code used by the TA for grading.

install.sh, requirements.txt and nbgrader_config.py are used when setting up a new year.
