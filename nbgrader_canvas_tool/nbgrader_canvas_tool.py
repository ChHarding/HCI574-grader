""" This script implements integrating Canvas with nbgrader. """
# pylint:disable=fixme
import argparse as a
import collections as c
import configparser
import csv
import datetime
import io
import os
import os.path as p
import shutil
import sys
import urllib.parse as up
import zipfile

import nbgrader.api as nb_api
import rarfile
import requests as r

ARGS = None  # parsed command line arguments, exposed using a global variable
CONFIG = None  # ConfigParser object exposed using a global variable


def access_token():
    """ Returns the access token for authenticating against canvas. """
    token = CONFIG.get('canvas', 'access-token')
    if not token:
        print("Unable to determine the access token for Canvas.",
              file=sys.stderr)
        sys.exit(1)
    return token


def config_canvas_root_url():
    """ Returns the root URL for Canvas specified in the config file. """
    url = CONFIG.get('canvas', 'root-url')
    if not url:
        print("Unable to determine the Canvas root URL!", file=sys.stderr)
        sys.exit(1)
    return url


def config_course_id():
    """ Returns the Canvas course ID specified in the config file. """
    id_value = CONFIG.get('canvas', 'course-id')
    if not id_value:
        print("Unable to determine the Canvas course id.", file=sys.stderr)
        sys.exit(1)
    return id_value


def config_root_dir():
    """ Returns the nbgrader root directory specified in the config file. """
    root_dir = CONFIG.get('nbgrader', 'root-dir')
    if not root_dir:
        print("Unable to determine the nbgrader root directory.",
              file=sys.stderr)
        sys.exit(1)
    return root_dir


def config_exchange_dir():
    """
    Returns the nbgrader exchange directory path specified in the config file.
    """
    ex_dir = CONFIG.get('nbgrader', 'exchange-dir', fallback=None)
    ex_dir = ex_dir or p.join(config_root_dir(), 'exchange')
    if not ex_dir:
        print("Unable to determine the exchange directory.", file=sys.stderr)
        sys.exit(1)
    return ex_dir


def config_feedback_dir():
    " Returns the nbgrader feedback directory specified in the config file. "
    f_dir = CONFIG.get('nbgrader', 'feedback-dir', fallback=None)
    f_dir = f_dir or p.join(config_root_dir(), 'feedback')
    if not f_dir:
        print("Unable to determine the feedback directory.", file=sys.stderr)
        sys.exit(1)
    return f_dir


def config_nbgrader_course_name():
    """ Returns the exchange course name specified in the config file. """
    course_name = CONFIG.get('nbgrader', 'course-name')
    if not course_name:
        print("Unable to determine the nbgrader course name.", file=sys.stderr)
        sys.exit(1)
    return course_name


def config_gradebook_db():
    """ Returns the path to the gradebook database file used by nbgrader. """
    db_path = CONFIG.get('nbgrader', 'gradebook-db', fallback=None)
    db_path = db_path or p.join(config_root_dir(), 'gradebook.db')
    if not db_path:
        print("Unable to determine the gradebook file path.", file=sys.stderr)
        sys.exit(1)
    return db_path


def nb_normalize_inbound_dir(nb_dir_path, nb_assignment_name):
    """
    Performs 'normalization' of a single 'inbound' leaf directory, so that it
    is suitable for nbgrader.

    This includes locating and renaming the relevant submitted .ipynb file and
    copying at to the directory level where nbgrader expects it. The additional
    files and directories that are located at the same directory tree level as
    the notebook are also copied to the top level.
    """
    print(f"Locating the notebook (i.e., '.ipynb') file in {nb_dir_path}.")

    def find_candidates():
        """ Finds the candidate notebook files. """
        cand_nb_paths = []
        for root, _, filenames in os.walk(nb_dir_path):
            for filename in filenames:
                if (filename.endswith('.ipynb') and
                        # filename.startswith('HW') and
                        '__MACOSX' not in root and
                        'checkpoint' not in filename):
                    cand_nb_paths.append(p.join(root, filename))
        return cand_nb_paths

    cand_nb_paths = find_candidates()
    if not cand_nb_paths:
        print(f"Failed to find any candidate notebook files in {nb_dir_path}.")
        print("Press [Enter] to skip the directory.")
        input()
        return
    if len(cand_nb_paths) == 1:
        cand_nb_path = cand_nb_paths[0]
    else:
        print(f"Found {len(cand_nb_paths)} candidate notebooks:")
        print(f"Please select its index (enter 's' to skip):")
        for idx, cand_nb_path in enumerate(cand_nb_paths):
            print(f"[{idx}] {cand_nb_path}")
        while True:
            sel_idx = input()
            if sel_idx == 's':
                print("Skipping.")
                return
            if sel_idx in [str(idx) for idx in range(len(cand_nb_paths))]:
                cand_nb_path = cand_nb_paths[int(sel_idx)]
                break
            print(f"Need a number between 0 and {len(cand_nb_paths)-1}.")
    assert cand_nb_path
    cand_nb_dir = p.dirname(cand_nb_path)
    if cand_nb_dir != nb_dir_path:
        for filename in os.listdir(cand_nb_dir):
            src = p.join(cand_nb_dir, filename)
            dst = p.join(nb_dir_path, filename)
            if src != cand_nb_path:
                if p.exists(dst):
                    continue
                _ = shutil.copytree if p.isdir(src) else shutil.copyfile
                _(src, dst)

    dst_nb_path = p.join(nb_dir_path, nb_assignment_name + '.ipynb')
    if dst_nb_path != cand_nb_path:
        shutil.copyfile(cand_nb_path, dst_nb_path)
    print(f"Deployed {cand_nb_path} as {dst_nb_path}")


def nb_get_scores(gb_db_path, nb_assignment_name):
    """
    Returns a dictionary that maps user names (i.e., netids) to their scores
    for a given assignment in nbgrader. `None` indicates no score.
    """
    db_sqlite_url = ''.join(['sqlite:///', p.abspath(gb_db_path)])
    scores = dict()
    with nb_api.Gradebook(db_sqlite_url) as gbook:
        for student in gbook.students:
            try:
                submission = gbook.find_submission(nb_assignment_name,
                                                   student.id)
                scores[student.id] = submission.score
            except nb_api.MissingEntry:
                scores[student.id] = None
    
    print(gb_db_path)
    return scores


def store_submitted_file(filename, file_obj, dst_dir):
    """
    Unpacks or copies a subitted file to a subdirectory of nbgrader's inbound
    directory.

    :param filename: filename of the submitted file
    :param file_obj: file-like object for the submitted data
    :param dst_dir: destination directory
    """
    _, ext = p.splitext(filename.lower())
    if ext == '.zip':
        zip_obj = zipfile.ZipFile(file_obj)
        if zip_obj.testzip() is None:
            zip_obj.extractall(dst_dir)
    elif ext == '.rar':
        rar_obj = rarfile.RarFile(file_obj)

        try:
            if rar_obj.testrar() is None:
                rar_obj.extractall(dst_dir)
        except Exception as e:
            print(filename)
            print(e)
    else:
        with open(p.join(dst_dir, filename), 'wb') as fdst:
            shutil.copyfileobj(file_obj, fdst)


class Canvas:
    """
    This class groups the code for working with Canvas using the web API.
    """
    def __init__(self, root_url=None, course_id=None):
        """ Initialize a new Canvas object given the root URL. """
        self.root_url = root_url or config_canvas_root_url()
        self.course_id = course_id or config_course_id()

    def request(self, path, params=None, method='get'):
        """
        Returns a request object for a given path relative to the root URL.
        """
        url = (path if path.startswith('https://') else up.urljoin(
            self.root_url, path))
        headers = dict(Authorization=f"Bearer {access_token()}")
        if method == 'get':
            res = r.get(url, params=params, headers=headers)
        elif method == 'post':
            res = r.post(url, data=params, headers=headers)
        elif method == 'put':
            res = r.put(url, data=params, headers=headers)
        else:
            raise ValueError("unrecognized request type")
        return res

    def json(self, path, params=None, method='get'):
        """
        Returns a JSON object obtained by parsing the Canvas response to an
        API request.

        Raises an error if the request fails.
        """

        # CH bug hunt
        print("*********************************************************")
        print("path", path, "params", params, "method", method)
        ro = self.request(path, params=params, method=method)
        print(ro)
        print("*********************************************************")
        json_obj = self.request(path, params=params, method=method).json()
        if isinstance(json_obj, c.abc.Mapping) and json_obj.get('errors'):
            print(json_obj, file=sys.stderr)
            raise RuntimeError("Canvas JSON request failed")
        return json_obj
        ''' works
        json_obj = self.request(path, params=params, method=method).json()
        if isinstance(json_obj, c.abc.Mapping) and json_obj.get('errors'):
            print(json_obj, file=sys.stderr)
            raise RuntimeError("Canvas JSON request failed")
        return json_obj
        '''

    def list_course_students_in_canvas(self):
        """ Lists all students in the course as Canvas provides them. """
        total_students = self.json(
            f"/api/v1/courses/{self.course_id}",
            params={'include[]': 'total_students'})['total_students']
        course_students_json_list = self.json(
            f"/api/v1/courses/{self.course_id}/users", params={
                'enrollment_type[]': 'student', 'per_page': total_students})
        return course_students_json_list

    def export_students_to_nbgrader_csv(self, csv_filename):
        """
        Lists all students in the course and exports them to a CSV file
        suitable for using with `nbgrader db student import`.
        """
        course_students_json_list = self.list_course_students_in_canvas()
        with open(csv_filename, 'w') as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=['id', 'last_name', 'first_name', 'email'])
            writer.writeheader()
            for cs_json in course_students_json_list:
                # Get the login_id, which should match the netid and which is
                # what we will use as a student id in nbgrader.
                print(f"Exporting the record: {cs_json['name']}, \
Canvas id: {cs_json['id']}.")
                profile_json = self.json(
                    f"/api/v1/users/{cs_json['id']}/profile")
                writer.writerow(dict(
                    id=profile_json['login_id'], last_name=cs_json['name'],
                    first_name='', email=''))

    def isu_netid_from_user_id(self, user_id):
        """
        Gets the ISU netid given the Canvas user ID.

        The code assumes that the the 'login_id' field of the user profile is
        set to the ISU netid.
        """
        profile_json = self.json(f"/api/v1/users/{user_id}/profile")
        return profile_json['login_id']

    def list_submissions(self, assignment_id):
        """ Lists the submissions for an assignment. """
        return self.json(f"/api/v1/courses/{self.course_id}/assignments/\
{assignment_id}/submissions", params={'per_page': '10000000'})

    def list_latest_submissions(self, assignment_id):
        """
        Lists only those submissions for which the field
        .grade_matches_current_submission is true.
        """
        user_sub = dict()
        for sub in self.list_submissions(assignment_id):
            user_id = sub['user_id']
            attempt = sub['attempt']
            last_attempt = (-1 if user_id not in user_sub
                            else user_sub[user_id]['attempt'])
            attempt = int(attempt) if attempt else 0
            last_attempt = int(last_attempt)
            if attempt > last_attempt:
                user_sub[user_id] = sub
        return user_sub.values()

    def xfer_assignment_to_nbgrader(self, assignment_id, nb_assignment_name):
        """
        Unpacks the ZIP files from Canvas to the nbgrader's exchange inbound
        directory.
        """
        def process_attachments(att_json_list, nb_dir_path):
            """
            Processes attachments in a submission, performing various
            fall-backs to capture common but non-conforming submissions.
            """
            for att in att_json_list:
                filename = att.get('filename')
                file_obj = io.BytesIO(self.request(att.get('url')).content)
                store_submitted_file(filename, file_obj, nb_dir_path)

        for sub in self.list_latest_submissions(assignment_id):
            if sub['workflow_state'] == 'unsubmitted':
                continue
            print(sub)
            user_id = sub.get('user_id')
            if not user_id:
                continue
            try:
                sub_at_dt = datetime.datetime.strptime(sub['submitted_at'],
                                                       '%Y-%m-%dT%H:%M:%SZ')
            except (ValueError, TypeError):
                sub_at_dt = datetime.datetime.now()

            _ = sub_at_dt.isoformat('T', timespec='microseconds')
            _ = _.replace(':', '')
            _ = _.replace('-', '')

            if sub.get('attachments'):
                isu_netid = self.isu_netid_from_user_id(user_id)
                nb_dir_name = '+'.join([isu_netid, nb_assignment_name, _])
                nb_dir_path = p.join(config_exchange_dir(),
                                     config_nbgrader_course_name(),
                                     'inbound', nb_dir_name)
                if not p.exists(nb_dir_path):
                    os.makedirs(nb_dir_path)
                process_attachments(sub['attachments'], nb_dir_path)
                nb_normalize_inbound_dir(nb_dir_path, nb_assignment_name)

    def upload_scores_and_feedback(self, nb_assignment_name, assignment_id):
        """
        Stores the scores and feedback for a graded assignment in Canvas.
        """
        def upload_score_for_student(user_id, the_score, f_html_path):
            """ Perform upload for a student. """
            print(f"Uploading the submission feedback file for {isu_netid}.")
            upload_params = dict(name=p.basename(f_html_path),
                                 size=os.stat(f_html_path).st_size,
                                 on_duplicate='overwrite')
            upload_path = f"/api/v1/courses/{self.course_id}/assignments/\
{assignment_id}/submissions/{user_id}/comments/files"
            tag = "Step 1: get the upload URL."
            print(f"[START] {tag}")
            upload_json = self.json(upload_path, params=upload_params,
                                    method='post')
            print(f"[DONE]  {tag}")

            tag = "Step 2: upload the file."
            print(f"[START] {tag}")
            res = r.post(upload_json['upload_url'],
                         files=dict(file=open(f_html_path, 'rb')))
            confirm_json = res.json()
            print(f"[DONE]  {tag}")

            tag = "Uploading score, brief comment, and linking the file."
            path = f"/api/v1/courses/{self.course_id}/assignments/\
{assignment_id}/submissions/{user_id}"
            print(f"[START] {tag}")
            self.json(path, method='put',
                      params={'comment[text_comment]': "Please see the \
attached feedback file.",
                              'comment[file_ids][]': confirm_json['id'],
                              'submission[posted_grade]': the_score})
            print(f"[DONE]  {tag}")

        nb_scores = nb_get_scores(config_gradebook_db(), nb_assignment_name)
        f_dir = config_feedback_dir()
        for cs_json in self.list_course_students_in_canvas():
            user_id = cs_json['id']
            isu_netid = self.isu_netid_from_user_id(user_id)
            the_score = nb_scores.get(isu_netid)
            if the_score is None:
                print(f"Missing grade for {isu_netid}. Proceeding.")
                continue
            print(f"The score for {isu_netid} is {the_score}.")
            f_html_name = ''.join([nb_assignment_name, '.html'])
            f_html_path = p.join(f_dir, isu_netid, nb_assignment_name,
                                 f_html_name)
            if not p.isfile(f_html_path):
                print(f"Missing feedback file \"{f_html_path}\";\
NOT uploading the grade.")
                print(f"Press [Enter] to continue.")
                input()
                continue
            print(f"Ready to submit the grade and feedback for {isu_netid}.")
            print(f"[p]roceed or [s]kip?")
            if input() != 'p':
                print(f"Skipping the grade for {isu_netid}.")
                continue
            upload_score_for_student(user_id, the_score, f_html_path)


def main():
    """ A C-style main() function. """
    global ARGS, CONFIG  # pylint:disable=global-statement

    parser = a.ArgumentParser(description="canvas--nbgrader integration")
    parser.add_argument('verb', choices=['export-student-list',
                                         'download', 'manual-submit',
                                         'upload'])
    parser.add_argument('verb_args', nargs='*')

    ARGS = parser.parse_args()

    CONFIG = configparser.ConfigParser()
    CONFIG.read(['nbcan.cfg', p.expanduser('~/.nbcanrc')])
    print('access token', access_token())
    if ARGS.verb == 'export-student-list':
        csv_filename = ARGS.verb_args[0]
        Canvas().export_students_to_nbgrader_csv(csv_filename)
    elif ARGS.verb == 'download':
        assignment_id = ARGS.verb_args[0]
        nb_assignment_name = ARGS.verb_args[1]
        Canvas().xfer_assignment_to_nbgrader(assignment_id, nb_assignment_name)
    elif ARGS.verb == 'manual-submit':
        nb_assignment_name = ARGS.verb_args[0]
        student_netid = ARGS.verb_args[1]
        submitted_filename = ARGS.verb_args[2]
        tstamp = datetime.datetime.now().isoformat('T',
                                                   timespec='microseconds')
        tstamp = tstamp.replace(':', '')
        tstamp = tstamp.replace('-', '')
        nb_dir_name = '+'.join([student_netid, nb_assignment_name, tstamp])
        nb_dir_path = p.join(config_exchange_dir(),
                             config_nbgrader_course_name(),
                             'inbound', nb_dir_name)
        if not p.exists(nb_dir_path):
            os.makedirs(nb_dir_path)
        with open(submitted_filename, 'rb') as submitted_file_obj:
            store_submitted_file(submitted_filename, submitted_file_obj,
                                 nb_dir_path)
        nb_normalize_inbound_dir(nb_dir_path, nb_assignment_name)
    elif ARGS.verb == 'upload':
        assignment_id = ARGS.verb_args[0]
        nb_assignment_name = ARGS.verb_args[1]
        Canvas().upload_scores_and_feedback(nb_assignment_name, assignment_id)

    return 0


if __name__ == '__main__':
    sys.exit(main())
