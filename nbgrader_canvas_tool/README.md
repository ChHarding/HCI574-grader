# nbgrader_canvas_tool

A python script to simplify integration between nbgrader and Canvas. The script
is a command-line tool. It should be used by changing the shell's working
directory to the directory where the script is located and invoking it
as follows:

```console
$ python3 nbgrader_canvas_tool.py <verb> [verb_args]
```

In this template command, `<verb>` indicates an action that the script can
perform and `[verb_args]` specifies its optional arguments.


## Configuration file

All actions implemented in the tool require communication with the Canvas web
server. Because the server URL does not change frequently, its value is
specified using a configuration file that is loaded by
`nbgrader_canvas_tool.py`. A minimal config file has the following form:

```
[canvas]
access-token=Your_access_token_from_Canvas
root-url=https://canvas.iastate.edu/  # Canvas root URL
course-id=12345  # Your course ID

[nbgrader]
root-dir=/path/to/nbgrader/course/directory
course-name=Course_Name_in_nbgrader
```


## Instructions for generating an access token in Canvas.

To interact with Canvas, the script needs an access token. As of Fall 2019 an
access token can be generated using the "New Access Token" button in the
settings page of the Canvas user profile, which can be access using
<https://canvas.iastate.edu/profile/settings>.

It is advisable to set an expiration date for the access token used by the
script, because an access token grants all user credentials, i.e., it is
impossible to further restrict what the code that uses the access token can or
cannot do in Canvas.

The access token should be set in the config file as the value of the
'access-token' property in the '[canvas]' section.


## Determining the Canvas course ID

The course ID is the numerical part of the Canvas course home page URL, e.g.,
if the home page URL is <https://canvas.iastate.edu/courses/12345>, then the
course id is 12345.

The course ID should be set as the value of the 'course-id' property in the
'[canvas]' section of the configuration file.


## Instructions for setting up the nbgrader environment.

1. Export the list of students using the python script:
```bash
python nbgrader_canvas_tool.py export-student-list /tmp/student_list.csv
```
2. Import the list of students into nbgrader:
```bash
nbgrader db student import /tmp/student_list.csv
```
3. Tie the loose ends:
```bash
rm /tmp/student_list.csv
```

## Miscellaneous Notes

The docs on Canvas API are out of date. As of early 2018, the files attached to
a student submission can be accessed by using the URLs stored in the list in the
`.attachments` field of the JSON object obtained from
`/api/v1/courses/{course_id()}/assignments/{assignment_id}/submissions`.

https://canvas.instructure.com/doc/api/submissions.html currently (as of early
2018) doesn't describe the 'attachments' key and doesn't mention that you get a
URL to download a submitted file from that.


## Verbs

download -- get the submissions from Canvas and store them as incoming
submissions in the exchange directory

manual-submit -- store an explicitly submitted ZIP file (e.g., sent by
email) in the exchange directory as an incoming submission

upload -- send the grades and feedback to Canvas
export-student-list -- generate the student list
